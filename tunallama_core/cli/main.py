"""``tunallama`` 명령 진입점."""

from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tunallama",
        description="tunaLlama — 로컬 LLM delegation 백엔드 + Claude Code 플러그인.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="<command>")

    p_init = sub.add_parser(
        "init", help="대화식으로 config.toml 생성 (provider/모델 자동 발견)"
    )
    p_init.add_argument(
        "--global",
        dest="global_",
        action="store_true",
        help="~/.tunallama/config.toml 에 저장 (기본은 ./.tunallama/config.toml)",
    )
    p_init.add_argument(
        "--force", action="store_true", help="기존 파일 덮어쓰기"
    )

    sub.add_parser("doctor", help="환경 진단 — Python / config / provider / DB / Kiwi")

    return parser


def run(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "init":
        from .init_cmd import run_init

        return run_init(global_=args.global_, force=args.force)
    if args.cmd == "doctor":
        from .doctor_cmd import run_doctor

        return run_doctor()
    return 0


if __name__ == "__main__":
    sys.exit(run())
