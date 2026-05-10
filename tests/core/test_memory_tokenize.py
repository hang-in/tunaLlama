import pytest

from tunallama_core.memory.tokenize import (
    has_korean,
    kiwi_morphemes,
    tokenize_for_index,
)


@pytest.mark.parametrize("s", ["안녕", "이메일 검증", "한국어와 English 혼합", "ㅎㅎ"])
def test_has_korean_true(s):
    assert has_korean(s) is True


@pytest.mark.parametrize("s", ["", "english only", "1234", "code = 'x'"])
def test_has_korean_false(s):
    assert has_korean(s) is False


def test_kiwi_morphemes_extracts_nouns():
    out = kiwi_morphemes("이메일 검증 함수")
    # 적어도 명사 형태소가 나타나야 한다
    assert "이메일" in out
    assert "검증" in out
    # 원문도 포함됨
    assert "이메일 검증 함수" in out


def test_kiwi_morphemes_separates_morphemes_in_concatenated_text():
    """띄어쓰기 없는 한국어도 형태소로 쪼개져야 한다 (FTS 매치 향상)."""
    out = kiwi_morphemes("이메일검증코드")
    assert "이메일" in out
    assert "검증" in out


def test_tokenize_for_index_none_passthrough():
    assert tokenize_for_index("이메일 검증", "none") == "이메일 검증"


def test_tokenize_for_index_kiwi_for_korean():
    out = tokenize_for_index("이메일 검증", "kiwi")
    assert "이메일" in out
    assert out != "이메일 검증"  # 형태소가 추가됨


def test_tokenize_for_index_english_passthrough_even_with_kiwi():
    assert tokenize_for_index("validate email", "kiwi") == "validate email"


def test_tokenize_for_index_konlpy_falls_back_to_kiwi():
    """Phase 1 에서는 konlpy_okt 도 kiwi 로 처리. fallback 경로 검증."""
    a = tokenize_for_index("이메일", "konlpy_okt")
    b = tokenize_for_index("이메일", "kiwi")
    assert a == b


def test_tokenize_for_index_unknown_tokenizer_passthrough():
    """방어선 — config loader 가 차단하지만 직접 호출 시에도 깨지지 않게."""
    assert tokenize_for_index("이메일 검증", "weird") == "이메일 검증"
