"""LLM provider 추상화.

- ``base.LLMClient`` 는 모든 provider 공통 인터페이스.
- ``factory.make_client`` 가 ``LLMConfig`` 보고 알맞은 구현을 만든다.

새로운 provider 추가 시:
1) ``base.LLMClient`` 를 상속한 클래스를 한 파일에 작성.
2) ``factory.make_client`` 에 분기 한 줄 추가.
"""

from .base import ChatResponse, LLMClient
from .factory import make_client

__all__ = ["ChatResponse", "LLMClient", "make_client"]
