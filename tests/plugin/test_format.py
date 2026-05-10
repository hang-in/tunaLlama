from tunallama_core import RecallResult, RecallSnippet
from plugin._format import format_recall


def test_format_recall_no_matches():
    out = format_recall(RecallResult(query="x", total_matches=0, snippets=()))
    assert "매칭 없음" in out
    assert "x" in out


def test_format_recall_single_match():
    s = RecallSnippet(
        full_id=7,
        timestamp="2026-05-10T01:23:45Z",
        tool_name="generate_code",
        inputs_summary='{"q": "validate email"}',
        output_excerpt="def is_valid_email(): ...",
        score=-1.5,
    )
    out = format_recall(RecallResult(query="email", total_matches=1, snippets=(s,)))
    assert "[7]" in out
    assert "generate_code" in out
    assert "2026-05-10" in out
    assert "validate email" in out
    assert "is_valid_email" in out
    assert "매칭 1건 (상위 1)" in out


def test_format_recall_truncates_to_snippets_only():
    """3 매치 중 1개만 snippet 으로 와도 포맷에서 살아남아야 한다."""
    s = RecallSnippet(
        full_id=1, timestamp="t", tool_name="t",
        inputs_summary="i", output_excerpt="o", score=0.0,
    )
    out = format_recall(RecallResult(query="q", total_matches=3, snippets=(s,)))
    assert "매칭 3건 (상위 1)" in out
