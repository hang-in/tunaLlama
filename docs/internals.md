# tunaLlama 내부 구조

README 본문에서 옮긴 자료. 처음 사용자보다 **기여자 / 깊이 보고 싶은
사용자** 를 위한 자리.

## 아키텍처 (3 layer)

```
plugin/                            # MCP frontend
  mcp_server.py                    # FastMCP 도구 등록
  _state.py                        # config 로드 + .env auto-load
  hooks/                           # optional pre_tool_use
  skills/delegate-to-ollama/SKILL.md

tunallama_core/                    # 백엔드 - frontend 모름
  config/                          # TOML/.env 파싱 + 검증
  llm/                             # OllamaClient / LMStudioClient / from_cloud
  delegation/                      # 10 도구 + 공통 runner + 시스템 프롬프트
  workflow/                        # dev_review_loop / 약점 카탈로그 적용
  memory/                          # SQLite + FTS5 (Kiwi) + 검색 path 들
    store.py                       # 스키마 / 색인 / record_call
    vector.py                      # BGE-M3 / KURE-v1 swap
    search.py                      # recall / recall_hybrid / recall_reranked /
                                   # recall_expanded / recall_normalized /
                                   # recall_hyde / recall_mmr
    normalization.py               # LLM query rewrite (Phase 5-2A)
    hyde.py                        # LLM hypothetical answer (Phase 5-2C)
    mmr.py                         # Maximal Marginal Relevance (Phase 5-2D)
    tiered.py                      # exact / near / hard tier 분류
    adaptive.py                    # 휴리스틱 라우터 (Phase 5-D)
  measurement/                     # ast_smell / token_count
  routing.py                       # auto_recall 정책
  cli/                             # tunallama init / doctor
  __init__.py                      # public API
```

**경계 규칙**: backend (`tunallama_core`) 는 `plugin` 을 import 하지 않는다.

모든 delegation 호출은 SQLite 에 한 줄씩 적재된다.

## 메모리와 검색

### 색인

`record_call` 시점에 `BAAI/bge-m3` (1024-dim, KURE-v1 도 동일 dim) 임베딩을
자동 계산해 `calls.embedding BLOB` 에 저장. 모델 로드는 lazy +
thread-locked. 임베딩 실패해도 record 자체는 BM25 만으로 정상 저장.

```python
EMBEDDING_MODEL = os.environ.get("TUNA_EMBEDDING_MODEL", "BAAI/bge-m3")
# 후보 (dim 1024 호환): BAAI/bge-m3, nlpai-lab/KURE-v1, Qwen/Qwen3-Embedding-0.6B
```

### 검색 path 8 종

- `recall(store, query)` - BM25 (Kiwi 형태소).
- `recall_hybrid(store, query, k=60)` - BM25 + vector RRF.
- `recall_reranked(store, query, candidate_pool=20)` - cross-encoder
  bge-reranker-v2-m3.
- `recall_expanded(store, query, client, mode=...)` - LLM 으로 query 4
  변형 → RRF.
- `recall_normalized(store, query, client, base=...)` - LLM 으로 query →
  standard form → base path.
- `recall_hyde(store, query, client, base=...)` - LLM 으로 가상 답변 텍스트
  → base path (Phase 5 production winner).
- `recall_mmr(store, query, lambda_=0.5)` - Maximal Marginal Relevance
  (anti-pattern, 측정 자산만 보존).
- `recall_adaptive(store, query, cloud_client)` - 휴리스틱 분기 (한국어
  비중 > 30% → HyDE / 그 외 → reranked hybrid).

자세한 우열 / σ 측정은 [measurements/](measurements/).

### 그래프 엣지

call 간 관계를 SQL JOIN 만으로 도출:
- `same_project`: 같은 `project_root`
- `same_day`: 같은 날짜
- `same_tool`: 같은 `tool_name`

`a.id < b.id` 정규화. `rebuild_edges()` + `traverse()` (Python BFS).

`build_semantic_edges(store, client, max_pairs=100)` 는 같은 project
record 페어를 LLM 으로 `RELATED` / `UNRELATED` 분류 (Phase 1.5 stage-2
classifier 검증된 패턴). `rebuild_edges()` 는 rule edges 만 삭제 -
semantic edges 보존.

## Provider 추상화

```
LLMClient (ABC)
  ├─ OllamaClient          # ollama python SDK, 로컬/클라우드 모두 동일 클래스
  └─ LMStudioClient        # OpenAI 호환 /chat/completions, httpx
```

| Provider | host 기본값 | 키 |
|---|---|---|
| ollama | `http://localhost:11434` | 없음 |
| ollama_cloud | `https://ollama.com` | `api_key_env` 가 가리키는 환경변수 |
| lmstudio | `http://localhost:1234/v1` | 더미 |

테스트는 mock 을 쓰지 않고 실 Ollama Cloud + 로컬 LM Studio 에 붙는다.
서비스 미가용 시 `@pytest.mark.integration` 로 자동 skip.

## Workflow - Architect ↔ Developer

### dev_review 루프

```python
def dev_review_loop(
    requirements: str, *, language=None, client, store=None,
    max_iterations: int = 2, review_focus=None, limitations_path=None,
    routing=None,
) -> DevReviewResult:
    full_req = with_limitations(requirements, path=limitations_path)
    gen = generate_code(full_req, ...)
    code = gen.text
    for i in range(1, max_iterations + 1):
        rev = review_code(code, focus=review_focus, ...)
        if not _has_issues(rev.text):
            return DevReviewResult(final_code=code, ..., converged=True)
        if i == max_iterations:
            break
        code = fix_code(code, rev.text, ...).text
```

heuristic: review 응답에 `LGTM`, `이상 없음` 등 종결 키워드가 있으면 수렴
처리. 그렇지 않으면 fix → 재 review.

### Spec 문서 형식

```markdown
# Task: build email validator

## Phase
IMPLEMENT          # DESIGN | IMPLEMENT | VERIFY

## Focus
정규식 검증 로직 먼저

## Requirements
- 정규식으로 1차 검증
- 빈 문자열 거부

## Constraints
- 표준 라이브러리만
- 외부 호출 없음

## Acceptance
- pytest 5 케이스 통과
```

`Constraints` 의 모든 항목은 hard rule. 위반 시 review 단계에서 잡혀 fix
루프로 들어간다.

### 약점 카탈로그

```bash
tuna_log_limitation("한국어 docstring 작성 시 들여쓰기 어긋남")
```

→ `~/.tunallama/limitations.md` 에 기록 → 이후 모든 `tuna_dev_review` 호출
의 prompt 앞에 자동 prepend. 자동 감지는 안 함 (아키텍트 판단).

## Hook (옵션)

`plugin/hooks/pre_tool_use.py` 는 Claude 가 큰 파일을 `Read` 하려 할 때
advisory 메시지를 stderr 로 띄운다. block 하지 않는다.

```json
{
  "hooks": {
    "PreToolUse": [
      {"matcher": "Read", "hooks": [
        {"type": "command",
         "command": "python /Users/me/tunaLlama/plugin/hooks/pre_tool_use.py"}
      ]}
    ]
  }
}
```

threshold 는 `TUNALLAMA_HOOK_THRESHOLD` 환경변수로 조정 (기본 5000 바이트).

## 테스트

```
$ pytest
... 408 passed
... TOTAL coverage 94%
```

- 단위 테스트는 `LLMClient` 의 fake (`StaticClient`) 사용. 응답 캡처 +
  결정적 결과.
- 통합 테스트는 실 Ollama Cloud + 로컬 LM Studio 에 붙는다.
- mock 남발 의도적 회피 - 외부 SDK 의 동작 변경 (스키마, 타입) 이 가려져
  실서비스 회귀를 놓치는 것을 막기 위해.
- `pytest.mark.search_quality` 는 cloud LLM + BGE-M3 + 임베딩 부담 큰
  통합 측정 마커. 일반 회귀에서 deselected.
