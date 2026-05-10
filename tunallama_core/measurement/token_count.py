"""delegation 토큰 절약 측정.

mode N (Native): Claude 단독 conversation - 1 turn 내 코드 작성.
mode D (Delegated): Claude + tunaLlama tool call - tool result 까지 합산.

Anthropic API 직접 호출. ``ANTHROPIC_API_KEY`` 필요. 비용 발생 (사용자 동의
요구).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from ..config.models import OllamaCloudProviderConfig
from ..delegation.code import generate_code
from ..llm.ollama import from_cloud


@dataclass(frozen=True)
class TokenUsage:
    mode: str  # "native" | "delegated"
    task_id: str
    task_size: str  # "small" | "medium" | "large"
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration_ms: int
    code_lines: int

    @property
    def cost_estimate_usd(self) -> float:
        """Sonnet 4.6 기준 추정. input $3 / 1M, output $15 / 1M (변동 가능)."""
        return self.input_tokens * 3e-6 + self.output_tokens * 15e-6


_NATIVE_SYSTEM = (
    "You are a senior Python engineer. Given a coding task, write the "
    "complete Python code. Return only the code in one code block, no "
    "prose, no explanation."
)


def measure_native(
    task: str,
    *,
    anthropic_client,
    model: str,
    task_id: str,
    task_size: str,
) -> TokenUsage:
    """Claude 단독 호출 - delegation 없는 baseline."""
    start = time.monotonic()
    resp = anthropic_client.messages.create(
        model=model,
        max_tokens=4096,
        system=_NATIVE_SYSTEM,
        messages=[{"role": "user", "content": task}],
    )
    duration = int((time.monotonic() - start) * 1000)
    text = "".join(
        b.text for b in resp.content if hasattr(b, "text") and b.text
    )
    return TokenUsage(
        mode="native",
        task_id=task_id,
        task_size=task_size,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
        total_tokens=resp.usage.input_tokens + resp.usage.output_tokens,
        duration_ms=duration,
        code_lines=len(text.splitlines()),
    )


def measure_delegated(
    task: str,
    *,
    anthropic_client,
    model: str,
    task_id: str,
    task_size: str,
) -> TokenUsage:
    """Claude → tool call (tunaLlama) → tool result → Claude 응답.

    모든 turn 의 토큰 합산. tunaLlama 의 cloud call 자체 토큰은 별 비용
    source (Ollama Cloud) 라 본 측정 X - **메인 conversation Anthropic
    토큰만**.
    """
    if not os.environ.get("OLLAMA_CLOUD_API_KEY"):
        raise RuntimeError("OLLAMA_CLOUD_API_KEY 미설정 - delegated mode 불가")

    cloud_cfg = OllamaCloudProviderConfig(
        host="https://ollama.com",
        api_key_env="OLLAMA_CLOUD_API_KEY",
        model="glm-4.7",
    )
    cloud_client = from_cloud(cloud_cfg, temperature=0.3, timeout=600)

    tool_def = {
        "name": "tuna_generate_code",
        "description": (
            "Delegate code generation to a local LLM (Ollama Cloud). "
            "Returns the generated code as a string."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "language": {"type": "string"},
            },
            "required": ["task"],
        },
    }
    system = (
        "You are an architect. For coding tasks, delegate generation to "
        "tuna_generate_code. After receiving the result, return only the "
        "final code in one code block."
    )

    total_input = 0
    total_output = 0
    final_text = ""
    start = time.monotonic()

    # Turn 1: Claude → tool call
    resp1 = anthropic_client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        tools=[tool_def],
        messages=[{"role": "user", "content": task}],
    )
    total_input += resp1.usage.input_tokens
    total_output += resp1.usage.output_tokens

    # tool_use block 추출
    tool_use_block = None
    for b in resp1.content:
        if getattr(b, "type", None) == "tool_use":
            tool_use_block = b
            break

    if tool_use_block is None:
        # delegation 없이 Claude 가 직접 답한 경우
        final_text = "".join(
            b.text for b in resp1.content if hasattr(b, "text") and b.text
        )
    else:
        # tool 실행 - tunaLlama 의 generate_code 흐름
        delegated_task = tool_use_block.input.get("task", task)
        gen = generate_code(
            delegated_task, language="python", client=cloud_client
        )
        tool_result_text = gen.text

        # Turn 2: tool result 반환
        resp2 = anthropic_client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            tools=[tool_def],
            messages=[
                {"role": "user", "content": task},
                {"role": "assistant", "content": resp1.content},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_block.id,
                            "content": tool_result_text,
                        }
                    ],
                },
            ],
        )
        total_input += resp2.usage.input_tokens
        total_output += resp2.usage.output_tokens
        final_text = "".join(
            b.text for b in resp2.content if hasattr(b, "text") and b.text
        )

    duration = int((time.monotonic() - start) * 1000)
    return TokenUsage(
        mode="delegated",
        task_id=task_id,
        task_size=task_size,
        input_tokens=total_input,
        output_tokens=total_output,
        total_tokens=total_input + total_output,
        duration_ms=duration,
        code_lines=len(final_text.splitlines()),
    )
