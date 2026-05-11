"""ast_smell 단위 테스트."""

from __future__ import annotations

from tunallama_core.measurement.ast_smell import analyze_ast


def test_empty_code_invalid():
    s = analyze_ast("")
    assert s.syntactically_valid is False
    assert s.parse_error == "empty"


def test_simple_function_clean():
    code = "def gcd(a, b):\n    while b:\n        a, b = b, a % b\n    return a\n"
    s = analyze_ast(code, unrelated_keywords=["salt", "hash"])
    assert s.syntactically_valid is True
    assert s.n_imports == 0
    assert s.n_funcs == 1
    assert s.n_classes == 0
    assert s.unrelated_keyword_hits == ()
    assert s.excess_score == 0  # 깨끗


def test_unrelated_keyword_hit():
    code = (
        "import hashlib\n"
        "def gcd(a, b):\n"
        "    salt = b'random'\n"
        "    h = hashlib.sha256(salt).hexdigest()\n"
        "    return h\n"
    )
    s = analyze_ast(code, unrelated_keywords=["salt", "hash", "encryption"])
    assert s.syntactically_valid is True
    assert s.n_imports == 1
    assert "salt" in s.unrelated_keyword_hits
    # excess: import 1 + unrelated_kw "salt" 3 = 4
    assert s.excess_score >= 4


def test_syntax_error_marked():
    s = analyze_ast("def broken(:\n    return")
    assert s.syntactically_valid is False
    assert "SyntaxError" in (s.parse_error or "")
    assert s.excess_score >= 10


def test_code_fence_stripped():
    code = "```python\ndef hello():\n    return 1\n```"
    s = analyze_ast(code)
    assert s.syntactically_valid is True
    assert s.n_funcs == 1


def test_class_count_doubled():
    code = "class A:\n    pass\n\nclass B:\n    pass\n"
    s = analyze_ast(code)
    assert s.n_classes == 2
    assert s.excess_score == 2 * 2  # class 2 = 4


def test_word_boundary_avoids_substring_match():
    """'rate' 가 'aggregate' 안에 있어도 hit X."""
    code = "def aggregate(): return 1\n"
    s = analyze_ast(code, unrelated_keywords=["rate"])
    assert s.unrelated_keyword_hits == ()


def test_async_function_counted():
    code = "async def do_work():\n    return 1\n"
    s = analyze_ast(code)
    assert s.n_funcs == 1


def test_excess_score_func_threshold():
    """함수 1개는 OK, 2개 이상부터 1 점씩 누적."""
    code1 = "def a(): pass\n"
    code3 = "def a(): pass\ndef b(): pass\ndef c(): pass\n"
    s1 = analyze_ast(code1)
    s3 = analyze_ast(code3)
    assert s1.excess_score == 0
    assert s3.excess_score == 2  # 3 - 1 = 2
