---
name: delegate-to-ollama
description: Delegate suitable coding subtasks to a local/cloud LLM (Ollama / Ollama Cloud / LM Studio) via tunaLlama, like an architect delegating to a subagent. The local LLM has a smaller context window than Claude, so before delegating non-trivial work fetch relevant project context (state.md + past calls) and prepend it. Maintain oversight by reviewing the returned output.
---

# When to use tunaLlama tools

`tuna_*` MCP tools delegate coding work to a local/cloud LLM. This is the
Opus-with-Sonnet-subagent pattern: a smaller model handles the actual code
generation, while you stay the architect.

The local LLM's window is smaller than yours, so the architect's job before
delegation is **fetching the context the subagent lacks**. Use them when:

1. **The user asks for code generation** and you have clear requirements.
   Use `tuna_generate_code` instead of generating the code yourself.

2. **The user asks to review or analyze a file**.
   Use `tuna_review_file` (passing the path) instead of reading the file first.
   The file content stays out of your context — major token savings.

3. **The user asks for refactoring or test writing** with a defined scope.
   Use `tuna_refactor_code` or `tuna_write_tests`.

4. **The user asks a question about multiple files**.
   Use `tuna_analyze_files` so file contents bypass your context.

# When NOT to delegate

- Tasks requiring deep judgment about architecture or design — keep these yourself.
- Short snippets (< ~10 lines) — overhead exceeds savings.
- Tasks that require knowledge of recent conversation context the local LLM does not have.
- Anything safety-critical or involving the user's intent interpretation.

# Standard pattern: context-fetch then delegate then verify

1. **Context-fetch** (architect's responsibility for the smaller subagent):
   - If the task is non-trivial, call `tuna_recall` to surface relevant past
     work in this project. The local LLM doesn't share your conversation
     context - relevant snippets help it avoid reinventing or contradicting.
   - Load project rules: the MCP resource `tunallama://memory/state` should
     auto-attach. If not visible, call `tuna_load_memory` once per session.
2. **Decompose** the user's request into clear instructions, including the
   fetched context that the local LLM lacks.
3. Call the appropriate `tuna_*` tool.
4. **Verify** the returned output - catch obvious problems (wrong API,
   missing edge cases, divergence from project conventions in state.md).
5. If wrong, call `tuna_fix_code` with a specific error description.
6. Present the verified result to the user.

# Recall (delegation context fetch)

`tuna_recall` searches past delegation outputs (`tuna_*` calls). Useful
before delegating non-trivial work in a familiar codebase - the local LLM
gets relevant prior decisions and patterns that wouldn't otherwise reach
its context window. Korean queries work (Kiwi morpheme indexing).

Different from `tuna_load_memory`, which returns the curated `state.md`
(conventions + active decisions + constraints + anti-patterns) - the
project's rules of the road. Use both: `state.md` for rules, `tuna_recall`
for relevant past work.

# Project memory (state.md) - CRITICAL: call once per session

`~/.tunallama/projects/<hash>/state.md` holds the project's conventions /
active decisions / constraints / anti-patterns.

**Important (v0.5.1 measurement)**: MCP resource `tunallama://memory/state`
auto-attach does NOT work in current Claude Code or Codex CLI versions. The
SessionStart hook (Phase 8) outputs state content via stdout but is not yet
universally honored.

**Action required**: call `tuna_load_memory` **once at session start** before
any delegation - if you don't, you'll miss the project's
Constraints / Anti-patterns and the local LLM will repeat known mistakes.

Honor `Constraints` and avoid `Anti-patterns observed` in delegation
prompts - the local LLM will only see them if you include them in the
spec or recall_prefix.
