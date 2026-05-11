"""Phase 7-2 - mid-size LLM context-boost effect 측정.

새 framing: 검색의 진짜 가치 = Architect 가 위임 전 mid-size LLM 의
컨텍스트 한계 보완. cloud-served mid-size 모델 (gemma3:27b 등) 으로 측정.

6 probe × 4 mode (none/relevant/mixed/adversarial) × 1 model (default gemma3:27b)
× 1 run = 24 cloud calls / model. quota 부담 작게.

추가 모델 (gemma4:31b, qwen3-coder-next, kimi-k2.6) 은 별 trigger (env
TUNA_PHASE7_MODEL).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict

import pytest

from tests.integration.seeds.phase7_probes import PROBES
from tunallama_core.config.models import OllamaCloudProviderConfig
from tunallama_core.delegation.code import generate_code
from tunallama_core.errors import LLMError
from tunallama_core.llm.ollama import from_cloud
from tunallama_core.measurement.ast_smell import analyze_ast

pytestmark = pytest.mark.search_quality

_DEFAULT_MODEL = os.environ.get("TUNA_PHASE7_MODEL", "gemma4:31b")


@pytest.fixture(scope="module")
def cloud_client():
    if not os.environ.get("OLLAMA_CLOUD_API_KEY"):
        pytest.skip("OLLAMA_CLOUD_API_KEY 미설정")
    cfg = OllamaCloudProviderConfig(
        host="https://ollama.com",
        api_key_env="OLLAMA_CLOUD_API_KEY",
        model=_DEFAULT_MODEL,
    )
    return from_cloud(cfg, temperature=0.3, timeout=600)


def _build_relevant_prefix(probe: dict) -> str:
    return (
        "<project_context>\n"
        f"{probe['prior_context']}\n"
        "</project_context>\n"
    )


def _build_mixed_prefix(probe: dict, all_probes: list[dict]) -> str:
    """relevant + 다른 probe 의 무관 context 3개 = R@5 0.5 시뮬."""
    lines = ["<project_context>"]
    lines.append(probe["prior_context"])
    others = [p for p in all_probes if p["id"] != probe["id"]]
    for other in others[:3]:
        lines.append(other["prior_context"])
    lines.append("</project_context>\n")
    return "\n".join(lines) + "\n"


def _build_adversarial_prefix(probe: dict, all_probes: list[dict]) -> str:
    """무관 probe 5개 만 - relevant 0."""
    lines = ["<project_context>"]
    others = [p for p in all_probes if p["id"] != probe["id"]]
    for other in others[:5]:
        lines.append(other["prior_context"])
    lines.append("</project_context>\n")
    return "\n".join(lines) + "\n"


def _correct_id_hit_rate(code: str, identifiers: list[str]) -> float:
    if not identifiers:
        return 0.0
    hits = sum(1 for ident in identifiers if ident in code)
    return hits / len(identifiers)


def _retry(fn, *, attempts: int = 3, label: str, capsys):
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


def test_context_boost_per_mode(cloud_client, capsys, tmp_path):
    """6 probe × 4 mode × 1 run × 1 model = 24 cloud calls."""
    modes = ["none", "relevant", "mixed", "adversarial"]
    artifacts: list[dict] = []
    by_cell: dict[tuple[str, str], dict] = {}

    for probe in PROBES:
        for mode in modes:
            if mode == "none":
                prefix = None
            elif mode == "relevant":
                prefix = _build_relevant_prefix(probe)
            elif mode == "mixed":
                prefix = _build_mixed_prefix(probe, PROBES)
            else:
                prefix = _build_adversarial_prefix(probe, PROBES)

            gen = _retry(
                lambda: generate_code(
                    probe["task"], language="python",
                    client=cloud_client, recall_prefix=prefix,
                ),
                label=f"gen {probe['id']}/{mode}",
                capsys=capsys,
            )
            code = gen.text
            id_hit = _correct_id_hit_rate(code, probe["correct_identifiers"])
            smell = analyze_ast(code, unrelated_keywords=probe["irrelevant_kw"])
            cell = {
                "probe": probe["id"],
                "mode": mode,
                "code": code,
                "correct_id_hit_rate": id_hit,
                "unrelated_kw_hits": list(smell.unrelated_keyword_hits),
                "n_imports": smell.n_imports,
                "n_funcs": smell.n_funcs,
                "n_lines": smell.n_lines,
                "syntactically_valid": smell.syntactically_valid,
                "excess_score": smell.excess_score,
            }
            artifacts.append(cell)
            by_cell[(probe["id"], mode)] = cell

    art_path = tmp_path / "phase7_2_artifacts.json"
    art_path.write_text(json.dumps(artifacts, ensure_ascii=False, indent=2))

    # per-mode aggregate
    def _agg(mode: str) -> dict:
        cells = [c for c in artifacts if c["mode"] == mode]
        n = len(cells)
        if n == 0:
            return {"n": 0, "id_hit": 0.0, "kw_hits": 0.0, "excess": 0.0, "valid": 0.0}
        return {
            "n": n,
            "id_hit": sum(c["correct_id_hit_rate"] for c in cells) / n,
            "kw_hits": sum(len(c["unrelated_kw_hits"]) for c in cells) / n,
            "excess": sum(c["excess_score"] for c in cells) / n,
            "valid": sum(1 for c in cells if c["syntactically_valid"]) / n,
        }

    with capsys.disabled():
        print(
            f"\n\n=== Phase 7-2 context-boost ({_DEFAULT_MODEL}, "
            f"{len(artifacts)} calls, artifacts: {art_path}) ==="
        )
        print(
            f"{'mode':<14}{'n':>4}{'id_hit':>10}{'kw_hits':>10}"
            f"{'excess':>10}{'valid':>8}"
        )
        print("-" * 56)
        for mode in modes:
            a = _agg(mode)
            print(
                f"{mode:<14}{a['n']:>4}"
                f"{a['id_hit']:>10.2f}"
                f"{a['kw_hits']:>10.2f}"
                f"{a['excess']:>10.2f}"
                f"{a['valid']:>8.2f}"
            )
        print()

        # per-probe id_hit by mode
        print("--- per-probe id_hit rate (relevant vs none diff) ---")
        print(f"{'probe':<22}{'none':>8}{'relevant':>10}{'mixed':>8}{'adv':>8}")
        for probe in PROBES:
            row = [probe["id"]]
            cells_n = by_cell.get((probe["id"], "none"), {})
            cells_r = by_cell.get((probe["id"], "relevant"), {})
            cells_m = by_cell.get((probe["id"], "mixed"), {})
            cells_a = by_cell.get((probe["id"], "adversarial"), {})
            print(
                f"{probe['id']:<22}"
                f"{cells_n.get('correct_id_hit_rate', 0):>8.2f}"
                f"{cells_r.get('correct_id_hit_rate', 0):>10.2f}"
                f"{cells_m.get('correct_id_hit_rate', 0):>8.2f}"
                f"{cells_a.get('correct_id_hit_rate', 0):>8.2f}"
            )
        print()

        boost = _agg("relevant")["id_hit"] - _agg("none")["id_hit"]
        adv_damage = _agg("adversarial")["id_hit"] - _agg("none")["id_hit"]
        print(f"context boost (relevant - none) = {boost:+.2f}")
        print(f"adversarial damage (adv - none) = {adv_damage:+.2f}")
