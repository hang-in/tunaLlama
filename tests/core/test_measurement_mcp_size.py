"""Phase 7-1 mcp_size 단위 테스트."""

from __future__ import annotations


from tunallama_core.measurement.mcp_size import (
    ToolSize,
    format_size_table,
    measure_tools,
    total_estimated_tokens,
)


def test_measure_tools_on_empty_mcp():
    class _Empty:
        _tool_manager = type("M", (), {"_tools": {}})()
    sizes = measure_tools(_Empty())
    assert sizes == []


def test_measure_tools_on_no_manager():
    class _NoMgr:
        pass
    sizes = measure_tools(_NoMgr())
    assert sizes == []


def test_measure_tools_real_mcp_server():
    """실제 plugin.mcp_server 의 등록된 도구들 size 측정 sanity."""
    from plugin.mcp_server import mcp
    sizes = measure_tools(mcp)
    # 13 도구 (review_code+file 통합, explain_code+file 통합 후).
    assert len(sizes) >= 10
    # 모든 도구가 양수 size.
    assert all(s.total_chars > 0 for s in sizes)
    assert all(s.estimated_tokens > 0 for s in sizes)
    # 내림차순 정렬.
    for i in range(len(sizes) - 1):
        assert sizes[i].total_chars >= sizes[i + 1].total_chars


def test_total_estimated_tokens():
    sizes = [
        ToolSize(name="a", description_chars=100, schema_chars=200, total_chars=310, estimated_tokens=88),
        ToolSize(name="b", description_chars=50, schema_chars=100, total_chars=160, estimated_tokens=45),
    ]
    assert total_estimated_tokens(sizes) == 133


def test_format_size_table():
    sizes = [
        ToolSize(name="tuna_x", description_chars=10, schema_chars=20, total_chars=30, estimated_tokens=8),
    ]
    txt = format_size_table(sizes)
    assert "tuna_x" in txt
    assert "TOTAL (1 tools)" in txt


def test_real_mcp_total_under_budget():
    """13 도구 system prompt 의 total 추정 토큰이 합리 범위 (< 3000) 안에.

    Claude Code 의 system prompt 크기 자체가 큰데 (~5000+ 토큰), 우리 도구
    추가분이 그 위에 얹히는 만큼 작아야. 3000 미만 = 추가 비용 우리 control 가능 범위.
    """
    from plugin.mcp_server import mcp
    sizes = measure_tools(mcp)
    total = total_estimated_tokens(sizes)
    assert total < 3000, f"MCP 도구 system prompt 총 토큰 {total} - budget 초과"
    # 너무 작아도 의심 (도구 description 미작성).
    assert total > 500, f"MCP 도구 system prompt 총 토큰 {total} - 의외로 작음"
