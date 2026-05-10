---
name: delegate-to-ollama
description: Delegate token-heavy coding work to a local LLM (Ollama / LM Studio) via tunaLlama. Use this when the user asks for code generation, file review, refactoring, or any task where the output would be long. Saves tokens by running heavy generation locally while you maintain oversight.
---

# When to use tunaLlama tools

You have access to `tuna_*` MCP tools backed by a local LLM. Use them when:

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

# Standard pattern: delegate then verify

1. Decompose the user's request into clear instructions for the local LLM.
2. Call the appropriate `tuna_*` tool.
3. Review the returned output. Catch obvious problems.
4. If the output looks wrong, call `tuna_fix_code` with the error description.
5. Present the verified result to the user.

# Recall

Before starting non-trivial work in a familiar codebase, consider calling
`tuna_recall` with keywords from the current request. Past delegations on the
same codebase often surface useful prior decisions. Korean queries work — the
backend uses Kiwi morpheme indexing.

# Project memory (state.md)

At session start, the MCP resource `tunallama://memory/state` may auto-attach
this project's conventions, active decisions, constraints, and observed
anti-patterns. If that resource is not visible in your context, call
`tuna_load_memory` once to load the same content as a tool response. The file
lives at `~/.tunallama/projects/<hash>/state.md` and is preserved across
sessions. Manual edits are kept; auto-extracted entries (Phase 6-2+) are
tagged. Honor `Constraints` and avoid `Anti-patterns observed`.
