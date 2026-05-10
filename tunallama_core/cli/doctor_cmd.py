"""``tunallama doctor`` — 환경 진단.

각 항목은 ``CheckResult`` 로 표준화. 실패 시 사용자가 조치할 수 있는 단서를 detail
에 담는다.
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from ..config import Config, load_config
from ..errors import ConfigError


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def check_python() -> CheckResult:
    v = sys.version_info
    return CheckResult(
        name="Python 3.11+",
        ok=v >= (3, 11),
        detail=f"current: {v.major}.{v.minor}.{v.micro}",
    )


def check_config() -> tuple[CheckResult, Config | None]:
    try:
        cfg = load_config()
    except ConfigError as e:
        return CheckResult("config.toml", False, str(e)), None
    return CheckResult("config.toml", True, str(cfg.source_path)), cfg


def check_provider(cfg: Config) -> CheckResult:
    p = cfg.llm.provider
    active = cfg.llm.active()

    if p == "ollama":
        try:
            from ollama import Client

            Client(host=active.host, timeout=3).list()  # type: ignore[union-attr]
            return CheckResult(f"Ollama @ {active.host}", True, "데몬 응답 OK")  # type: ignore[union-attr]
        except Exception as e:  # noqa: BLE001
            return CheckResult(
                f"Ollama @ {active.host}",  # type: ignore[union-attr]
                False,
                f"{type(e).__name__}: {e} — `ollama serve` 실행 여부 확인",
            )

    if p == "ollama_cloud":
        try:
            active.resolve_api_key()  # type: ignore[union-attr]
        except ConfigError as e:
            return CheckResult("Ollama Cloud key", False, str(e))
        return CheckResult(
            "Ollama Cloud key",
            True,
            f"환경변수 {active.api_key_env} 설정됨",  # type: ignore[union-attr]
        )

    # lmstudio
    try:
        import httpx

        r = httpx.get(active.host.rstrip("/") + "/models", timeout=3)  # type: ignore[union-attr]
        r.raise_for_status()
        return CheckResult(f"LM Studio @ {active.host}", True, "models endpoint OK")  # type: ignore[union-attr]
    except Exception as e:  # noqa: BLE001
        return CheckResult(
            f"LM Studio @ {active.host}",  # type: ignore[union-attr]
            False,
            f"{type(e).__name__}: {e} — LM Studio Server 켜져있는지 확인",
        )


def check_memory_db(cfg: Config) -> CheckResult:
    db = cfg.memory.db_path
    try:
        db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE IF NOT EXISTS _doctor_check (x INT)")
        conn.execute("DROP TABLE _doctor_check")
        conn.close()
    except Exception as e:  # noqa: BLE001
        return CheckResult("Memory DB", False, f"{type(e).__name__}: {e}")
    return CheckResult("Memory DB", True, str(db))


def check_kiwi() -> CheckResult:
    try:
        from kiwipiepy import Kiwi

        Kiwi()  # 초기화 비용 검증
    except Exception as e:  # noqa: BLE001
        return CheckResult(
            "Kiwi 한국어 토크나이저",
            False,
            f"{type(e).__name__}: {e} — `pip install kiwipiepy` 확인",
        )
    return CheckResult("Kiwi 한국어 토크나이저", True, "import + init OK")


def _print_report(results: list[CheckResult]) -> int:
    for r in results:
        mark = "[OK]  " if r.ok else "[FAIL]"
        print(f"  {mark}  {r.name}")
        print(f"          {r.detail}")
    failed = sum(1 for r in results if not r.ok)
    print()
    if failed == 0:
        print(f"모든 검사 통과 ({len(results)}/{len(results)}).")
        return 0
    print(f"{failed}개 실패. 위 detail 을 참고해 조치하세요.")
    return 1


def run_doctor() -> int:
    print("===== tunaLlama doctor =====\n")
    results: list[CheckResult] = [check_python()]

    cfg_result, cfg = check_config()
    results.append(cfg_result)

    if cfg is not None:
        results.append(check_provider(cfg))
        results.append(check_memory_db(cfg))

    results.append(check_kiwi())
    return _print_report(results)
