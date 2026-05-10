"""Phase 5-3 - cross-task pollution (adversarial recall prefix).

Phase 4-4 측정에서 5 probe 모두 saturate (모든 axis 만점). 외부 Codex 5.5
사전 진단 그대로. 본 측정은:
- 6 isolated probe (단순 함수)
- mode "never": recall prefix 없음
- mode "always_adv": **의도적으로 무관한 recall prefix** prepend (e.g. GCD
  task 에 password_hashing record prepend)
- AST smell deterministic 평가 (judge LLM 회피)

목표: always_adv 의 코드에 unrelated keyword (`hashlib`, `bcrypt`, `salt`
등) 가 출현하면 컨텍스트 오염 정량 증거.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict

import pytest

from tunallama_core.config.models import OllamaCloudProviderConfig
from tunallama_core.delegation.code import generate_code
from tunallama_core.errors import LLMError
from tunallama_core.llm.ollama import from_cloud
from tunallama_core.measurement.ast_smell import analyze_ast

pytestmark = pytest.mark.search_quality


# ---------------- Probe 정의 ----------------

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


# (probe_id, spec, adversarial_recall_phrases, unrelated_keywords)
_PROBES: list[tuple[str, str, list[str], list[str]]] = [
    (
        "P1_gcd",
        "두 정수 a, b 를 인자로 받아 GCD (최대공약수) 를 반환하는 Python 함수 "
        "`gcd(a: int, b: int) -> int` 를 작성. 외부 라이브러리 X. 함수 정의만.",
        # adversarial: password_hashing 의 paraphrase
        [
            "비밀번호 해시 with bcrypt", "credential 단방향 암호화",
            "salt 추가한 hash", "password hashing", "credential one-way hashing",
        ],
        ["hashlib", "bcrypt", "salt", "password", "sha256", "sha512"],
    ),
    (
        "P2_mean",
        "숫자 list 의 평균 (mean) 을 float 로 반환하는 Python 함수 "
        "`mean(values: list[float]) -> float`. 빈 리스트는 0.0. 외부 라이브러리 X.",
        # adversarial: rate_limit
        [
            "API rate limit 구현", "throttling 미들웨어", "토큰 버킷 알고리즘",
            "초당 호출 제한", "leaky bucket implementation",
        ],
        ["rate_limit", "throttle", "throttling", "bucket", "token_bucket", "leaky"],
    ),
    (
        "P3_fizzbuzz",
        "1 부터 100 까지 fizzbuzz 결과를 list[str] 로 반환하는 Python 함수 "
        "`fizzbuzz() -> list[str]`. 3 의 배수: 'Fizz', 5 의 배수: 'Buzz', "
        "둘 다: 'FizzBuzz', 그 외: str(n).",
        # adversarial: async/asyncio
        [
            "비동기 처리", "async/await 사용", "코루틴 작성",
            "asyncio event loop", "non-blocking I/O",
        ],
        ["async", "await", "asyncio", "coroutine", "loop.run_until_complete"],
    ),
    (
        "P4_count_vowels",
        "영문 문자열 s 에서 모음 (a/e/i/o/u 대소문자 무관) 갯수를 int 로 "
        "반환하는 Python 함수 `count_vowels(s: str) -> int`. 외부 라이브러리 X.",
        # adversarial: docker/k8s
        [
            "docker compose 작성", "k8s 배포 설정", "컨테이너 오케스트레이션",
            "kubernetes deployment", "쿠버네티스 배포 전략",
        ],
        ["docker", "kubernetes", "k8s", "container", "compose", "kubectl", "yaml"],
    ),
    (
        "P5_deep_merge",
        "두 dict a, b 를 깊게 머지한 새 dict 반환하는 Python 함수 "
        "`deep_merge(a: dict, b: dict) -> dict`. 양쪽이 dict 면 재귀 머지, "
        "아니면 b 우선. 입력 dict 변경 X.",
        # adversarial: TLS/crypto
        [
            "TLS 핸드셰이크 처리", "암호화 연결 설정", "secure socket layer setup",
            "TLS 인증 과정", "establish encrypted session",
        ],
        ["ssl", "tls", "certificate", "handshake", "encrypted", "x509"],
    ),
    (
        "P6_reverse_string",
        "문자열 s 를 뒤집어 반환하는 Python 함수 `reverse(s: str) -> str`. "
        "외부 라이브러리 X.",
        # adversarial: logging
        [
            "logging 구조 설계", "structured logging with loguru",
            "loguru 사용", "로그 포맷 지정", "구조화 로그",
        ],
        ["logging", "logger", "loguru", "structlog", "log_format"],
    ),
]

_RUNS_PER_CELL = 3


# ---------------- Helpers ----------------

def _build_recall_prefix(phrases: list[str]) -> str:
    """recall block 형식 모방. 실제 routing 의 to_prompt_block() 와 같은 톤."""
    lines = ["<recall_context>"]
    lines.extend(f"  - {p}" for p in phrases)
    lines.append("</recall_context>\n")
    return "\n".join(lines) + "\n"


def _retry(fn, *, attempts: int = 3, label: str = "", capsys):
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except LLMError as e:
            last = e
            with capsys.disabled():
                print(f"  [retry {i + 1}/{attempts}] {label}: {e}")
            time.sleep(5)
    raise last  # type: ignore[misc]


# ---------------- Main test ----------------

def test_crosstask_pollution_ast(dev_client, capsys, tmp_path):
    """6 probe × 2 mode × 3 run = 36 generate_code + 36 AST smell."""
    artifacts: list[dict] = []
    by_cell: dict[tuple[str, str], list] = {}

    for probe_id, spec, adv_phrases, unrelated_kw in _PROBES:
        for mode in ("never", "always_adv"):
            cell_smells = []
            for run_idx in range(_RUNS_PER_CELL):
                if mode == "never":
                    prefix = None
                else:
                    prefix = _build_recall_prefix(adv_phrases)
                gen = _retry(
                    lambda: generate_code(
                        spec, language="python", client=dev_client,
                        recall_prefix=prefix,
                    ),
                    label=f"gen {probe_id}/{mode}/{run_idx}",
                    capsys=capsys,
                )
                code = gen.text
                smell = analyze_ast(code, unrelated_keywords=unrelated_kw)
                cell_smells.append(smell)
                artifacts.append({
                    "probe": probe_id, "mode": mode, "run": run_idx,
                    "code": code,
                    "recall_prefix": prefix,
                    "smell": asdict(smell),
                })
            by_cell[(probe_id, mode)] = cell_smells

    # artifact 저장
    art_path = tmp_path / "phase5_3_artifacts.json"
    art_path.write_text(json.dumps(artifacts, ensure_ascii=False, indent=2))

    # per-mode aggregate
    def _stats(smells: list) -> dict[str, float]:
        n = len(smells)
        if n == 0:
            return dict(n=0, valid=0.0, kw_hit_rate=0.0, avg_excess=0.0)
        valid = sum(1 for s in smells if s.syntactically_valid) / n
        kw_hit_rate = sum(
            1 for s in smells if s.unrelated_keyword_hits
        ) / n
        avg_excess = sum(s.excess_score for s in smells) / n
        return dict(n=n, valid=valid, kw_hit_rate=kw_hit_rate, avg_excess=avg_excess)

    never_all = [s for (_, m), ss in by_cell.items() if m == "never" for s in ss]
    always_all = [
        s for (_, m), ss in by_cell.items() if m == "always_adv" for s in ss
    ]
    n_stats = _stats(never_all)
    a_stats = _stats(always_all)

    with capsys.disabled():
        print(f"\n\n=== Phase 5-3 cross-task pollution (artifacts: {art_path}) ===")
        print(f"{'mode':<14}{'n':>5}{'valid':>8}{'kw_hit%':>10}{'excess':>10}")
        print("-" * 50)
        for label, st in (("never", n_stats), ("always_adv", a_stats)):
            print(
                f"{label:<14}{st['n']:>5}"
                f"{st['valid']:>8.2f}"
                f"{st['kw_hit_rate'] * 100:>9.1f}%"
                f"{st['avg_excess']:>10.2f}"
            )
        print()

        # per-probe kw_hit
        print("--- per-probe unrelated keyword hit rate ---")
        print(f"{'probe':<18}{'never':>10}{'always_adv':>14}")
        for probe_id, _, _, _ in _PROBES:
            n_smells = by_cell[(probe_id, "never")]
            a_smells = by_cell[(probe_id, "always_adv")]
            n_rate = sum(1 for s in n_smells if s.unrelated_keyword_hits) / len(n_smells)
            a_rate = sum(1 for s in a_smells if s.unrelated_keyword_hits) / len(a_smells)
            print(f"{probe_id:<18}{n_rate * 100:>9.1f}%{a_rate * 100:>13.1f}%")
        print()

        kw_diff = a_stats["kw_hit_rate"] - n_stats["kw_hit_rate"]
        excess_diff = a_stats["avg_excess"] - n_stats["avg_excess"]
        print(
            f"kw_hit difference (always_adv - never) = {kw_diff * 100:+.1f}%, "
            f"excess_score diff = {excess_diff:+.2f}"
        )
        if kw_diff >= 0.30:
            print(">>> README 경고 강화 권장 (auto_recall=always 가 명백 오염 신호)")
        elif kw_diff >= 0.10:
            print(">>> 약한 오염 시그널 - 모니터링 권장")
        else:
            print(">>> 차이 미미 - 현재 README 경고 수준 유지")
