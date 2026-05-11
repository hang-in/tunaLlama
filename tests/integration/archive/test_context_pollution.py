"""Phase 4-4 - context pollution A/B (auto_recall=always vs never).

5 probe task × 2 mode × 3 run = **30 dev_review 호출** + 30 judge 호출.
컨텍스트 오염 (auto_recall=always 가 무관 record 를 prepend 해 코드 품질 저하)
을 정량 측정.

dev: glm-4.7 / judge: kimi-k2-thinking. judge 는 4 axis (correctness / focus /
minimality / code_smell) 0-2 정수 점수.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import dataclass

import pytest

from tunallama_core.config.models import (
    OllamaCloudProviderConfig,
    RoutingConfig,
)
from tunallama_core.delegation.code import generate_code
from tunallama_core.errors import LLMError
from tunallama_core.llm.ollama import from_cloud
from tunallama_core.memory.store import MemoryStore
from tunallama_core.routing import recall_for_delegation

pytestmark = pytest.mark.search_quality


# ---------------- Probe specs ----------------

_PROBES: list[tuple[str, str]] = [
    (
        "P1_gcd",
        "두 정수 a, b 를 인자로 받아 GCD (최대공약수) 를 반환하는 Python 함수 "
        "`gcd(a: int, b: int) -> int` 를 작성. 외부 라이브러리 X. "
        "파일/print 부수효과 없음 - 함수 정의만.",
    ),
    (
        "P2_count_vowels",
        "영문 문자열 s 에서 모음 (a/e/i/o/u, 대소문자 무관) 갯수를 세어 int 로 "
        "반환하는 Python 함수 `count_vowels(s: str) -> int` 를 작성. 외부 "
        "라이브러리 X.",
    ),
    (
        "P3_mean",
        "숫자 list 의 평균 (mean) 을 float 로 반환하는 Python 함수 "
        "`mean(values: list[float]) -> float` 를 작성. 빈 리스트는 0.0. "
        "외부 라이브러리 X.",
    ),
    (
        "P4_fizzbuzz",
        "1 부터 100 까지 fizzbuzz 결과를 list[str] 로 반환하는 Python 함수 "
        "`fizzbuzz() -> list[str]` 를 작성. 3 의 배수: 'Fizz', 5 의 배수: "
        "'Buzz', 둘 다: 'FizzBuzz', 그 외: str(n).",
    ),
    (
        "P5_deep_merge",
        "두 dict a, b 를 깊게 머지 (deep merge) 한 새 dict 를 반환하는 Python "
        "함수 `deep_merge(a: dict, b: dict) -> dict` 를 작성. 양쪽이 dict 면 "
        "재귀 머지, 아니면 b 우선. 입력 dict 는 변경 X.",
    ),
]

_RUNS_PER_CELL = 3  # mode × probe 당 반복


# ---------------- Seed (102 record - extended_store 와 동일) ----------------

_ORIGINAL_GROUPS: list[list[str]] = [
    ["메모리 누수 탐지", "memory leak detection", "할당 해제 안 된 객체 찾기",
     "GC 가 안 돌아가는 문제", "garbage collection 디버깅", "OOM 발생 추적"],
    ["이메일 검증 로직", "validate email format", "메일 주소 유효성 체크",
     "RFC 5322 준수 검사", "정규식으로 메일 거름", "email format check function"],
    ["파일 압축", "compress file size", "용량 줄이기",
     "gzip 적용", "데이터 사이즈 다이어트", "binary 작게 만들기"],
    ["JSON 파싱 함수", "parse JSON safely", "JSON 디코딩 처리",
     "json.loads 호출", "역직렬화 구현", "deserialize JSON document"],
    ["비밀번호 해시", "password hashing with bcrypt", "credential 단방향 암호화",
     "단방향 hash 함수", "salt 추가한 hash", "credential one-way hashing"],
    ["API rate limit 구현", "요청 빈도 제한", "throttling 미들웨어",
     "토큰 버킷 알고리즘", "초당 호출 제한", "leaky bucket implementation"],
]
_NEW_GROUPS: list[list[str]] = [
    ["logging 구조 설계", "log 출력 포맷", "구조화 로그",
     "structured logging with loguru", "loguru 사용", "로그 포맷 지정"],
    ["캐싱 전략", "메모리 캐시 구현", "LRU cache",
     "Redis 캐시 적용", "캐시 무효화", "cache TTL 설정"],
    ["비동기 처리", "async/await 사용", "동시성 코드",
     "코루틴 작성", "asyncio event loop", "non-blocking I/O"],
    ["DB 마이그레이션", "schema 변경 스크립트", "Alembic 사용",
     "다운타임 없는 마이그레이션", "rollback 전략", "컬럼 추가 migration"],
    ["직렬화 처리", "객체 → JSON dump", "pickle 사용",
     "msgpack 직렬화", "역직렬화 deserialize", "binary serialization"],
    ["정렬 알고리즘", "quicksort 구현", "merge sort",
     "안정 정렬", "부분 정렬", "in-place sort"],
]
_NOISE: list[str] = [
    "matplotlib 차트 그리기", "ANSI 컬러 출력", "argparse 사용법",
    "flask route 설정", "pygame window 생성", "pandas dataframe merge",
    "requests timeout 설정", "yaml 파일 파싱", "re 정규표현식 그룹",
    "tkinter 버튼 이벤트", "selenium headless 모드", "pytest fixture scope",
    "docker compose build", "kubernetes pod status", "git rebase interactive",
    "ssh key 생성", "vim mapping 설정", "bash script loop",
    "json path query", "xml parser setup", "sql join optimization",
    "redis pubsub", "rabbitmq exchange", "kafka consumer group",
    "grpc service definition", "protobuf field numbering", "aws s3 upload",
    "azure blob storage", "gcp cloud functions", "terraform state lock",
]


# ---------------- Fixtures ----------------

@pytest.fixture(scope="module")
def polluted_store(tmp_path_factory):
    """Phase 4-3 와 동일 102 record 시드. 무관한 메모리로 컨텍스트 오염 시뮬."""
    db = tmp_path_factory.mktemp("pollute") / "ext.db"
    store = MemoryStore(db, korean_tokenizer="kiwi", enable_embeddings=True).open()
    for group in _ORIGINAL_GROUPS + _NEW_GROUPS:
        for p in group:
            store.record_call(
                tool_name="seed", inputs={"q": p}, output=f"out for {p}",
                model="seed", duration_ms=1,
            )
    for n in _NOISE:
        store.record_call(
            tool_name="seed", inputs={"q": n}, output=f"out for {n}",
            model="seed", duration_ms=1,
        )
    yield store
    store.close()


@pytest.fixture(scope="module")
def dev_client():
    if not os.environ.get("OLLAMA_CLOUD_API_KEY"):
        pytest.skip("OLLAMA_CLOUD_API_KEY 미설정")
    cfg = OllamaCloudProviderConfig(
        host="https://ollama.com",
        api_key_env="OLLAMA_CLOUD_API_KEY",
        model="glm-4.7",
    )
    return from_cloud(cfg, temperature=0.3, timeout=600)


@pytest.fixture(scope="module")
def judge_client():
    if not os.environ.get("OLLAMA_CLOUD_API_KEY"):
        pytest.skip("OLLAMA_CLOUD_API_KEY 미설정")
    cfg = OllamaCloudProviderConfig(
        host="https://ollama.com",
        api_key_env="OLLAMA_CLOUD_API_KEY",
        model="kimi-k2-thinking",
    )
    return from_cloud(cfg, temperature=0.0, timeout=600)


# ---------------- Helpers ----------------

@dataclass
class JudgeScore:
    correctness: int
    focus: int
    minimality: int
    code_smell: int
    comment: str

    @property
    def total(self) -> int:
        return self.correctness + self.focus + self.minimality + self.code_smell


_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "correctness": {"type": "integer", "minimum": 0, "maximum": 2},
        "focus": {"type": "integer", "minimum": 0, "maximum": 2},
        "minimality": {"type": "integer", "minimum": 0, "maximum": 2},
        "code_smell": {"type": "integer", "minimum": 0, "maximum": 2},
        "comment": {"type": "string"},
    },
    "required": ["correctness", "focus", "minimality", "code_smell", "comment"],
}

_JUDGE_SYSTEM = (
    "당신은 코드 리뷰어. 주어진 spec 과 생성 코드를 보고 4 axis 를 0-2 정수로 점수.\n"
    "- correctness: spec 의 의도 동작 일치 (0=실패, 1=부분, 2=완벽)\n"
    "- focus: spec 외 무관 코드/주석/import 가 없는지 (0=많음, 1=일부, 2=없음)\n"
    "- minimality: 스펙 이상의 abstraction/추가 함수/클래스가 없는지 (0=과다, 2=최소)\n"
    "- code_smell: 불필요 import / dead code / 잘못된 type annotation 없는지 "
    "(0=많음, 2=깨끗)\n"
    "JSON 만 출력. 설명 X."
)


def _strip_code_fence(s: str) -> str:
    """``` ```json ... ``` ``` wrap 제거 - kimi-k2-thinking 가 schema 강제에도 wrap 종종."""
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[: -3]
    return s.strip()


def _judge(spec: str, code: str, *, judge_client) -> JudgeScore:
    user = f"Spec:\n{spec}\n\nGenerated code:\n```python\n{code}\n```"
    resp = judge_client.chat(
        system=_JUDGE_SYSTEM,
        prompt=user,
        response_schema=_JUDGE_SCHEMA,
    )
    data = json.loads(_strip_code_fence(resp.text))
    return JudgeScore(
        correctness=int(data["correctness"]),
        focus=int(data["focus"]),
        minimality=int(data["minimality"]),
        code_smell=int(data["code_smell"]),
        comment=str(data.get("comment", "")),
    )


# ---------------- Main test ----------------

def test_context_pollution_ab(
    polluted_store, dev_client, judge_client, capsys, tmp_path
):
    """5 probe × 2 mode × 3 run = 30 dev_review + 30 judge."""
    modes = [
        ("never", RoutingConfig(auto_recall="never", recall_limit=5)),
        ("always", RoutingConfig(auto_recall="always", recall_limit=5)),
    ]
    artifacts: list[dict] = []
    by_cell: dict[tuple[str, str], list[JudgeScore]] = {}

    def _retry(fn, *, attempts: int = 3, label: str = ""):
        last: Exception | None = None
        for i in range(attempts):
            try:
                return fn()
            except (LLMError, json.JSONDecodeError, KeyError, ValueError) as e:
                last = e
                with capsys.disabled():
                    print(f"  [retry {i + 1}/{attempts}] {label}: {type(e).__name__}: {e}")
                time.sleep(5)
        raise last  # type: ignore[misc]

    for probe_id, spec_text in _PROBES:
        for mode_name, routing in modes:
            cell_scores: list[JudgeScore] = []
            for run_idx in range(_RUNS_PER_CELL):
                rec = recall_for_delegation(
                    routing, polluted_store,
                    explicit_query=None, fallback_query=spec_text,
                )
                prefix = rec.to_prompt_block() if rec else None
                if prefix == "":
                    prefix = None
                gen = _retry(
                    lambda: generate_code(
                        spec_text, language="python",
                        client=dev_client, store=polluted_store,
                        recall_prefix=prefix,
                    ),
                    label=f"gen {probe_id}/{mode_name}/{run_idx}",
                )
                code = gen.text
                score = _retry(
                    lambda: _judge(spec_text, code, judge_client=judge_client),
                    label=f"judge {probe_id}/{mode_name}/{run_idx}",
                )
                cell_scores.append(score)
                artifacts.append({
                    "probe": probe_id, "mode": mode_name, "run": run_idx,
                    "code": code,
                    "score": {
                        "correctness": score.correctness, "focus": score.focus,
                        "minimality": score.minimality, "code_smell": score.code_smell,
                        "comment": score.comment,
                    },
                })
            by_cell[(probe_id, mode_name)] = cell_scores

    # artifacts 보존 (정직 보고용).
    art_path = tmp_path / "context_pollution_artifacts.json"
    art_path.write_text(json.dumps(artifacts, ensure_ascii=False, indent=2))

    # per-mode AVG.
    def _avg_per_axis(scores: list[JudgeScore]) -> dict[str, float]:
        if not scores:
            return {"correctness": 0.0, "focus": 0.0, "minimality": 0.0, "code_smell": 0.0}
        return {
            "correctness": statistics.mean(s.correctness for s in scores),
            "focus": statistics.mean(s.focus for s in scores),
            "minimality": statistics.mean(s.minimality for s in scores),
            "code_smell": statistics.mean(s.code_smell for s in scores),
        }

    never_all = [s for (_, m), ss in by_cell.items() if m == "never" for s in ss]
    always_all = [s for (_, m), ss in by_cell.items() if m == "always" for s in ss]
    never_avg = _avg_per_axis(never_all)
    always_avg = _avg_per_axis(always_all)

    with capsys.disabled():
        print(f"\n\n=== Phase 4-4 context pollution A/B (artifacts: {art_path}) ===")
        print(f"{'mode':<10}{'corr':>8}{'focus':>8}{'minim':>8}{'smell':>8}{'total':>8}")
        print("-" * 50)
        for label, avg in (("never", never_avg), ("always", always_avg)):
            tot = sum(avg.values())
            print(
                f"{label:<10}{avg['correctness']:>8.2f}{avg['focus']:>8.2f}"
                f"{avg['minimality']:>8.2f}{avg['code_smell']:>8.2f}{tot:>8.2f}"
            )
        print()
        print("--- per-probe focus / minimality ---")
        print(f"{'probe':<16}{'never_f':>10}{'always_f':>10}{'never_m':>10}{'always_m':>10}")
        for probe_id, _ in _PROBES:
            n = by_cell[(probe_id, "never")]
            a = by_cell[(probe_id, "always")]
            print(
                f"{probe_id:<16}"
                f"{statistics.mean(s.focus for s in n):>10.2f}"
                f"{statistics.mean(s.focus for s in a):>10.2f}"
                f"{statistics.mean(s.minimality for s in n):>10.2f}"
                f"{statistics.mean(s.minimality for s in a):>10.2f}"
            )
        print()

    # 가설: always 가 never 대비 focus 또는 minimality 평균이 ≥ 0.3 떨어지면
    # README 경고 강화 트리거. 측정만 하고 fail 처리 X (정직 보고 우선).
    focus_drop = never_avg["focus"] - always_avg["focus"]
    minim_drop = never_avg["minimality"] - always_avg["minimality"]
    with capsys.disabled():
        print(
            f"focus drop (never - always) = {focus_drop:+.2f}, "
            f"minimality drop = {minim_drop:+.2f}"
        )
        if focus_drop >= 0.3 or minim_drop >= 0.3:
            print(">>> README 경고 강화 권장 (`auto_recall=always` 비권장 강조)")
        else:
            print(">>> 차이 미미 - 현재 README 경고 수준 유지")
