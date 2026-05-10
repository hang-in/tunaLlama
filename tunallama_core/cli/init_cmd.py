"""``tunallama init`` — 대화식 config.toml 생성기.

각 단계는 기본값을 제공해 엔터만 누르면 진행되도록 한다. provider 가 가용하면
설치/로드된 모델을 자동 발견해 번호 선택으로 바로 고르게 해 준다.
"""

from __future__ import annotations

import os
from pathlib import Path

_PROVIDERS = [
    ("ollama", "로컬 Ollama 데몬 (http://localhost:11434)"),
    ("ollama_cloud", "Ollama Cloud (API 키 필요)"),
    ("lmstudio", "LM Studio (http://localhost:1234/v1)"),
]


def _ask(question: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{question}{suffix}: ").strip()
    return raw or (default or "")


def _ask_yes(question: str, default: bool = True) -> bool:
    d = "y" if default else "n"
    raw = _ask(question, d).lower()
    return raw.startswith("y")


def _select_provider() -> str:
    print("\n사용할 LLM provider 를 고르세요:")
    for i, (_, desc) in enumerate(_PROVIDERS, 1):
        print(f"  {i}) {desc}")
    while True:
        c = _ask("선택 (1/2/3)", "1")
        if c.isdigit() and 1 <= int(c) <= len(_PROVIDERS):
            return _PROVIDERS[int(c) - 1][0]
        print("  → 1, 2, 3 중 하나를 입력하세요.")


def _discover_ollama_models(host: str) -> list[str]:
    try:
        from ollama import Client

        resp = Client(host=host, timeout=3).list()
    except Exception:
        return []
    items = getattr(resp, "models", None) or (
        resp.get("models", []) if isinstance(resp, dict) else []
    )
    names: list[str] = []
    for m in items:
        n = (
            getattr(m, "model", None)
            or (m.get("model") if isinstance(m, dict) else None)
            or (m.get("name") if isinstance(m, dict) else None)
        )
        if n:
            names.append(n)
    return names


def _discover_lmstudio_models(host: str) -> list[str]:
    try:
        import httpx

        r = httpx.get(host.rstrip("/") + "/models", timeout=3)
        r.raise_for_status()
        return [x["id"] for x in r.json().get("data", []) if x.get("id")]
    except Exception:
        return []


def _pick_or_type(label: str, candidates: list[str], fallback_default: str) -> str:
    if not candidates:
        return _ask(f"{label} 모델 이름 (직접 입력)", fallback_default)
    print(f"\n{label} 에서 발견된 모델 ({len(candidates)}개):")
    for i, m in enumerate(candidates, 1):
        print(f"  {i}) {m}")
    print(f"  (이름 직접 입력도 가능)")
    raw = _ask("모델 번호 또는 이름", "1")
    if raw.isdigit() and 1 <= int(raw) <= len(candidates):
        return candidates[int(raw) - 1]
    return raw or candidates[0]


def _ollama_block() -> tuple[str, str, dict]:
    host = _ask("Ollama host", "http://localhost:11434")
    models = _discover_ollama_models(host)
    if not models:
        print("  [!] Ollama 데몬에 접근할 수 없습니다 — `ollama serve` 가 켜져있는지 확인.")
    model = _pick_or_type("Ollama", models, "qwen2.5:32b")
    return host, model, {"num_ctx": 8192}


def _ollama_cloud_block() -> tuple[str, str, dict]:
    host = _ask("Ollama Cloud host", "https://ollama.com")
    print("\nAPI 키는 환경변수로 받습니다. (`.env` 또는 셸에 export)")
    env_name = _ask("API 키 환경변수 이름", "OLLAMA_CLOUD_API_KEY")
    if not os.environ.get(env_name):
        print(f"  [!] 환경변수 {env_name} 가 비어있습니다 — 나중에 .env 에 추가하세요.")
    model = _ask("모델 (cloud catalog)", "devstral-small-2:24b")
    return host, model, {"api_key_env": env_name}


def _lmstudio_block() -> tuple[str, str, dict]:
    host = _ask("LM Studio host", "http://localhost:1234/v1")
    models = _discover_lmstudio_models(host)
    if not models:
        print("  [!] LM Studio 에 접근할 수 없습니다 — 앱의 Server 가 켜져있는지 확인.")
    model = _pick_or_type("LM Studio", models, "qwen2.5-coder-32b-instruct")
    return host, model, {"api_key": "lm-studio"}


def _render(
    *,
    provider: str,
    host: str,
    model: str,
    extra: dict,
    enable_logging: bool,
    enable_recall: bool,
    auto_recall: str,
) -> str:
    lines = [
        "[llm]",
        f'provider = "{provider}"',
        "temperature = 0.3",
        "timeout_seconds = 300",
        "",
    ]
    if provider == "ollama":
        lines += [
            "[llm.ollama]",
            f'host = "{host}"',
            f'model = "{model}"',
            f"num_ctx = {extra['num_ctx']}",
            "",
        ]
    elif provider == "ollama_cloud":
        lines += [
            "[llm.ollama_cloud]",
            f'host = "{host}"',
            f'api_key_env = "{extra["api_key_env"]}"',
            f'model = "{model}"',
            "",
        ]
    elif provider == "lmstudio":
        lines += [
            "[llm.lmstudio]",
            f'host = "{host}"',
            f'model = "{model}"',
            f'api_key = "{extra["api_key"]}"',
            "",
        ]
    lines += [
        "[memory]",
        'db_path = "~/.tunallama/memory.db"',
        'korean_tokenizer = "kiwi"',
        f"enable_logging = {str(enable_logging).lower()}",
        f"enable_recall = {str(enable_recall).lower()}",
        "",
        "[routing]",
        f'auto_recall = "{auto_recall}"',
        "recall_limit = 5",
        "",
        "[logging]",
        'level = "INFO"',
    ]
    return "\n".join(lines) + "\n"


def run_init(*, global_: bool = False, force: bool = False) -> int:
    print("===== tunaLlama init =====")
    print("config.toml 을 단계별로 만듭니다. 엔터로 기본값 사용.")

    target_dir = (Path.home() / ".tunallama") if global_ else (Path.cwd() / ".tunallama")
    target_path = target_dir / "config.toml"

    if target_path.exists() and not force:
        print(f"\n[FAIL] 이미 {target_path} 가 있습니다.")
        print("       덮어쓰려면 `--force` 를 추가하세요.")
        return 1

    provider = _select_provider()
    if provider == "ollama":
        host, model, extra = _ollama_block()
    elif provider == "ollama_cloud":
        host, model, extra = _ollama_cloud_block()
    else:
        host, model, extra = _lmstudio_block()

    enable_logging = _ask_yes("\n호출 기록(SQLite) 사용?", True)
    enable_recall = (
        _ask_yes("리콜(검색) 사용?", True) if enable_logging else False
    )
    auto_recall = (
        _ask("auto_recall 모드 (always / on_request / never)", "on_request")
        if enable_recall
        else "never"
    )

    body = _render(
        provider=provider,
        host=host,
        model=model,
        extra=extra,
        enable_logging=enable_logging,
        enable_recall=enable_recall,
        auto_recall=auto_recall,
    )

    target_dir.mkdir(parents=True, exist_ok=True)
    target_path.write_text(body, encoding="utf-8")

    print(f"\n[OK]  {target_path} 생성 완료.")
    print("      다음:")
    print("        - tunallama doctor  로 환경 점검")
    print("        - claude --plugin-dir ./plugin  으로 플러그인 시작")
    return 0
