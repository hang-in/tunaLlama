"""로컬 LLM 약점 카탈로그.

목표: architect 가 작업 중 알게 된 로컬 모델의 약점을 카탈로그에 기록 →
다음 번 delegation 호출의 prompt 앞에 자동 첨부 → 모델이 같은 실수를 반복하지
않도록 한다.

기본 위치: ``~/.tunallama/limitations.md``. delegation 직전에 ``with_limitations()``
가 markdown 본문을 가져와 prompt 위에 prepend.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LIMITATIONS_PATH = Path.home() / ".tunallama" / "limitations.md"


def load_limitations(path: Path | str | None = None) -> str:
    """카탈로그 markdown 본문 그대로 반환. 파일 없으면 빈 문자열."""
    p = Path(path) if path else DEFAULT_LIMITATIONS_PATH
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def with_limitations(prompt: str, *, path: Path | str | None = None) -> str:
    """prompt 위에 limitations 섹션을 prepend. 카탈로그 비어있으면 그대로."""
    body = load_limitations(path).strip()
    if not body:
        return prompt
    return (
        "# Known limitations of this model — avoid the patterns listed below.\n"
        f"{body}\n\n"
        "# Task\n"
        f"{prompt}"
    )


def log_limitation(
    description: str, *, path: Path | str | None = None
) -> Path:
    """새 약점을 카탈로그에 추가. 파일 없으면 생성."""
    p = Path(path) if path else DEFAULT_LIMITATIONS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    line = f"- [{today}] {description.strip()}\n"
    if not p.exists():
        p.write_text(f"# Limitations\n\n{line}", encoding="utf-8")
    else:
        body = p.read_text(encoding="utf-8")
        if not body.endswith("\n"):
            body += "\n"
        p.write_text(body + line, encoding="utf-8")
    return p
