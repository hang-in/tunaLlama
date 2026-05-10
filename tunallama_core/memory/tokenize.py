"""한국어 형태소 사전 토큰화.

FTS5 의 unicode61 토크나이저는 한국어를 단순 음절/자모로만 다뤄 의미 단위 검색이
약하다. write 시점에 Kiwi 로 형태소를 분리해 함께 색인하면 한국어 리콜 정확도가
크게 올라간다. 영어/숫자는 그대로 두고 한국어 부분만 보강한다.
"""

from __future__ import annotations

import re

# 한글 음절 + 자모 + 호환 자모.
_HANGUL_RE = re.compile(r"[가-힣ㄱ-ㆎ]")

# Kiwi 형태소 태그 중 검색에 의미 있는 것만 유지 (조사/어미/구두점 제거).
# NNG 일반명사, NNP 고유명사, NNB 의존명사, VV 동사, VA 형용사,
# MAG 일반부사, MAJ 접속부사, SL 외국어/영문.
# NNB 추가는 seCall(Rust) 의 토큰화 패턴 참고.
_KEEP_TAGS = {"NNG", "NNP", "NNB", "VV", "VA", "MAG", "MAJ", "SL"}

_kiwi = None  # lazy: Kiwi() 초기화 비용을 import 시점에서 지연.


def has_korean(text: str) -> bool:
    return bool(_HANGUL_RE.search(text))


def _get_kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi

        _kiwi = Kiwi()
    return _kiwi


def kiwi_morphemes(text: str) -> str:
    """한국어 부분에서 의미 형태소를 추출, 원문 뒤에 붙여 반환.

    원문을 함께 두는 이유: FTS5 가 영문/숫자 토큰 매치를 그대로 받을 수 있도록.
    """
    kw = _get_kiwi()
    tokens = kw.tokenize(text)
    morph = " ".join(t.form for t in tokens if t.tag in _KEEP_TAGS)
    return f"{morph} {text}".strip()


def tokenize_for_index(text: str, tokenizer: str) -> str:
    """write-time tokenization. 한국어 없거나 tokenizer="none" 이면 원문 그대로."""
    if tokenizer == "none" or not has_korean(text):
        return text
    if tokenizer == "kiwi" or tokenizer == "konlpy_okt":
        # konlpy_okt 는 Phase 1 미구현 — kiwi 로 처리. config.loader 가 이미
        # 알려진 값만 통과시키므로 다른 입력은 들어오지 않는다.
        return kiwi_morphemes(text)
    return text
