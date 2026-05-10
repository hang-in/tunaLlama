# tunaLlama

Claude Code 의 메인 세션(아키텍트)이 무거운 코드 생성을 로컬 LLM(Ollama / LM Studio)에 위임하고, 분해와 검증만 유료 모델에 남겨두기 위한 백엔드 + 플러그인.

**버전**: v0.1.0 출시 · v0.2.0 대기 (Phase 2 통합 완료, Phase 3 진행 중)
**라이선스**: MIT.
**English**: [README.en.md](README.en.md).

---

## 1. 무엇이고 왜 만들었나

Claude Code 로 코딩하다 보면 **출력이 긴 단계** - 코드 생성, 파일 리뷰, 리팩터 - 가 메인 conversation 컨텍스트를 가장 많이 먹는다. 그런데 이 단계는 보통 결정적이고 모델 품질의 차이가 작다. 반대로 분해(요구사항 → 작업 목록)와 검증(돌려받은 결과가 요구사항을 만족하는지)은 짧은 입출력이지만 모델 품질 차이가 크다.

> **delegation 의 가치 정정** (Phase 5-4 측정 결정, 2026-05-11)
>
> 초기 가설은 "토큰 절약" 이었지만, Phase 4-4 + 5-3 측정에서 isolated task
> 의 코드 품질은 native (Claude 직접) 와 cloud LLM 위임이 유사 (kw_hit 0%).
> delegation 의 진짜 가치는 토큰 절약이 아니라:
> - **메인 conversation 컨텍스트 격리** (긴 코드/리뷰 텍스트가 메인 대화에
>   안 들어옴)
> - **무거운 작업의 cloud 분리** (대형 분석, large refactor, batch 작업)
> - **로컬 모델 활용** (개인 정보 / 외부 송신 회피)
>
> 토큰 절약 정량 측정은 사용자 환경의 Anthropic API 미보유로 보류
> (`docs/specs/phase5_4_token_measurement.md` 참조).

tunaLlama 는 이 비대칭을 그대로 코드 흐름으로 굳혀 둔다. 도메인 패턴은 `OllamaClaude` (Jadael/OllamaClaude) 와 같지만, Python 으로 처음부터 다시 짰고 한국어 검색·문서 기반 워크플로우·약점 카탈로그가 추가됐다. 코드 복사는 없다.

| 역할 | 모델 | 책임 |
|---|---|---|
| Architect | Claude Code (유료) | 분해 / 사양 작성 / 검증 / 통합 |
| Developer | 로컬 LLM (Ollama / Cloud / LM Studio) | 코드 생성 / 자체 리뷰 / 자체 수정 |
| Reviewer | Claude Code (유료, 같은 세션) | 최종 판정 |

토큰 헤비 단계만 로컬로 빠지고, 짧은 분해·검증 단계는 그대로 Claude 에 남는다.

## 2. 동작 원리

전형적인 호출 흐름:

1. 사용자가 한국어/영어로 task 를 말함.
2. Claude(아키텍트)가 task 를 분해. 짧으면 `tuna_dev_review(requirements, language)` 한 번 호출, 길면 markdown spec 문서를 `docs/specs/<name>.md` 에 작성한 뒤 `tuna_dev_review_from_spec(path)` 호출.
3. backend 가 generate → review → (이슈 있으면) fix → 다시 review 를 `max_iterations` 까지 자동 반복. 모든 호출은 SQLite 에 기록되고 한국어 형태소로 색인된다.
4. backend 가 최종 코드 + iteration 로그를 반환.
5. Claude 가 그 결과를 읽고 자체 검증. 의심스러우면 사용자에게 조각 단위로 보여주거나 `tuna_log_limitation()` 으로 약점을 카탈로그에 추가한다 (다음 호출의 prompt 앞에 자동 prepend).

핵심은 backend 가 도구 호출을 **메모리 + recall 까지 한 호출에서 모두 처리** 한다는 점이다. Claude 가 file 내용·중간 코드·review 텍스트를 자기 컨텍스트로 끌어들이지 않아도 된다.

## 3. 아키텍처

```
tunallama_core/                  # 백엔드 - 재사용 가능, MCP-agnostic
  config/                        # TOML 로드 + 검증 + frozen dataclass
  llm/                           # Provider 추상화 (ollama / lmstudio / factory)
  memory/                        # SQLite + FTS5 + Kiwi (BM25) + BGE-M3 (벡터) + RRF + graph
  delegation/                    # 10 도구 + 공통 runner + 시스템 프롬프트
  workflow/                      # dev_review_loop / spec / limitations
  routing.py                     # auto_recall 정책
  errors.py                      # 도메인 예외
  cli/                           # tunallama init / doctor

plugin/                          # Claude Code 플러그인 - backend 소비
  .claude-plugin/plugin.json
  .mcp.json
  mcp_server.py                  # FastMCP 서버, 14 tuna_* 도구 노출
  _state.py                      # lazy 싱글톤 + .env 자동 로드
  _format.py                     # recall 결과 직렬화
  hooks/pre_tool_use.py          # 큰 파일 Read 시 권유 (off by default)
  skills/delegate-to-ollama/SKILL.md
  agents/tuna-developer.md

tests/
  core/                          # 단위 + 통합 (실 Ollama Cloud / LM Studio)
  plugin/                        # MCP 도구 + 매니페스트 + state + hook
```

**불변 규칙**: `tunallama_core` 는 `plugin` 을 절대 import 하지 않는다. Phase 4 에서 Codex 프론트엔드를 추가할 때 backend 를 그대로 가져다 쓸 수 있게 하려는 것이다.

## 4. 메모리와 검색

모든 delegation 호출은 SQLite 에 한 줄씩 적재된다.

```sql
CREATE TABLE calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    inputs_json TEXT NOT NULL,
    output TEXT NOT NULL,
    model TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    tokens_estimated INTEGER,
    project_root TEXT,
    session_id TEXT,
    tags TEXT NOT NULL DEFAULT '[]'
);
CREATE VIRTUAL TABLE calls_fts USING fts5(
    inputs_text, output_text,
    tokenize='unicode61 remove_diacritics 2'
);
```

FTS5 의 `unicode61` 토크나이저는 한국어를 음절/자모로만 자르기 때문에 한국어 검색 리콜이 나쁘다. 그래서 **write 시점에 Python 에서 Kiwi 로 형태소 분리** 한 결과를 원문과 함께 색인한다. "이메일검증" 처럼 띄어쓰기 없는 입력에 대해 "이메일" 로 검색해도 매칭된다.

```python
# tunallama_core/memory/tokenize.py
_KEEP_TAGS = {"NNG", "NNP", "NNB", "VV", "VA", "MAG", "MAJ", "SL"}

def kiwi_morphemes(text: str) -> str:
    tokens = _get_kiwi().tokenize(text)
    morph = " ".join(t.form for t in tokens if t.tag in _KEEP_TAGS)
    return f"{morph} {text}".strip()
```

NNB(의존명사)는 `seCall` 프로젝트의 토크나이저 패턴을 참고해 추가했다. 트리거를 두지 않고 application 레이어에서 `calls` 와 `calls_fts` 에 명시적으로 INSERT 한다 - 한국어 사전 토큰화가 트리거 안에 들어가지 않기 때문에, 이중 INSERT 가 더 단순하고 디버깅 가능하다.

리콜은 `tuna_recall(query, limit)` 으로 호출. 응답은 항상 요약 + 발췌 형식이라 컨텍스트를 폭발시키지 않는다.

### 4.1. 의미 기반 검색 - 벡터 임베딩 (Phase 2)

`record_call` 시점에 `BAAI/bge-m3` (1024-dim) 임베딩을 자동 계산해 `calls.embedding BLOB` 에 저장한다. 모델 로드는 lazy + thread-locked. 임베딩 파이프라인이 실패해도(모델 미설치, OOM 등) record 자체는 BM25 만으로 정상 저장 - 옵션 기능이므로 BM25 path 는 영향 없음.

```python
# tunallama_core/memory/vector.py
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024

def embed(text: str) -> np.ndarray:
    model = _get_model()
    return model.encode(text, convert_to_numpy=True, normalize_embeddings=True).astype(np.float32)
```

`MemoryStore.search_vectors(query, limit, project_root)` 는 cosine 유사도 brute-force (numpy dot - 1만 record 까지는 충분). NULL/corrupt blob 자동 skip.

### 4.2. 하이브리드 검색 - RRF (Phase 2)

`recall_hybrid(store, query, limit, k=60)` 가 BM25 + 벡터 결과를 Reciprocal Rank Fusion 으로 병합. 각 결과 list 의 1-based rank 로 `score = 1/(k+rank)` 부여하고 같은 record id 가 양쪽에 잡히면 score 합산. 벡터 결과 비어도 BM25 만으로 정상 동작 - 옛 db / 모델 미가용 환경 호환.

### 4.3. 검색 품질 (실측, 2026-05-10)

두 시드로 정량 측정:

**Phase 2 - 키워드 일치 시드** (12 record, P@3):

| 경로 | P@3 평균 |
|---|---:|
| BM25 (Kiwi) | **1.00** |
| vector (BGE-M3) | 0.67 |
| hybrid (RRF) | 0.67 |

**Phase 3 - paraphrase 시드** (36 record, R@5):

| 경로 | R@5 평균 |
|---|---:|
| BM25 | 0.25 |
| vector | 0.67 |
| hybrid (RRF) | 0.67 |
| **expanded BM25** (LLM query expansion) | **0.50** |
| expanded hybrid | 0.67 |
| reranked hybrid (cross-encoder bge-reranker-v2-m3) | 0.69 |
| reranked BM25 | 0.25 |

**Phase 5-2C - HyDE 가 새 production-RAG winner** (524 record, 24 group leader sample)

| 경로 | P@1 | R@5 | MRR | NDCG@5 | σR@5 |
|---|---:|---:|---:|---:|---:|
| hybrid baseline | 0.33 | 0.30 | 0.50 | 0.31 | 0.28 |
| reranked (pool=50) | 0.54 | 0.38 | 0.71 | 0.43 | 0.24 |
| normalized hybrid | 0.71 | 0.42 | 0.79 | 0.48 | 0.22 |
| **HyDE hybrid** | **0.92** | **0.50** | **0.95** | **0.60** | **0.16** |

- HyDE (arXiv:2212.10496): LLM 으로 query 를 가상 답변 텍스트로 변환 후 검색.
- **P@1 0.92, MRR 0.95** - 거의 항상 첫 결과가 정답.
- σR@5 0.16 - 외부 권고 목표 0.15 거의 도달.
- LLM 1회 (normalized 와 동급 비용, expanded 보다 절반).
- 함수: `recall_hyde(store, query, *, client, base="hybrid", limit=5)`.
- **caveat**: 시드 record 가 "task description" 형식이라 hypothetical answer 와 매칭 매우 강함. 실 사용에서 record 가 도구 호출 dump 등 다른 형식이면 효과 편차 가능.

**Phase 5-2A - normalized hybrid (이전 winner, 비교용)**

- LLM 으로 query 를 standard form 으로 재작성 후 hybrid 검색.
- P@1 0.71, σR@5 0.22 - HyDE 이전의 best path. 가성비 still good.
- 함수: `recall_normalized(store, query, *, client, base="hybrid"|"bm25"|"rerank", limit=5)`.

**Phase 5-1 - 524 record 시드 LOPO (102 → 524 corpus 확장 효과)**

| 경로 | P@1 | R@5 | MRR | σR@5 |
|---|---:|---:|---:|---:|
| BM25 | 0.40 | 0.23 | 0.52 | 0.21 |
| vector | 0.65 | 0.42 | 0.75 | 0.24 |
| hybrid | 0.51 | 0.34 | 0.65 | 0.23 |
| reranked hybrid | 0.66 | 0.43 | 0.75 | 0.26 |
| expanded hybrid | 0.67 | 0.44 | 0.78 | 0.23 |

- corpus 102 → 524 로 키우면 σR@5 -0.04 ~ -0.06 ↓ (외부 검토 가설 H1 ✓).
- rerank P@1 +0.04 (외부 H2 ✓ - 큰 noisy corpus 일수록 reranker 가치 ↑).
- R@5 일괄 -0.04 ~ -0.11 - candidate_pool=20 한도가 발목. limit 확대로 보완.

**Phase 4 - 확장 시드** (102 record = 12 task × 6 paraphrase + 30 noise; 12 query × 6 paraphrase = 72 query):

| 경로 | P@5 | R@5 |
|---|---:|---:|
| BM25 | 0.73 | 0.29 |
| vector | 0.61 | 0.51 |
| hybrid | 0.60 | 0.50 |
| reranked hybrid | 0.65 | 0.54 |
| expanded BM25 (mode=bm25) | 0.74 | 0.45 |
| **expanded hybrid (mode=hybrid, glm-4.7/kimi-k2-thinking)** | **0.75** | **0.62** |

- query 표현마다 R@5 0.30-0.75 범위 흔들림 (σ 0.14-0.23) - paraphrase 가 표면 토큰 거의 안 겹치는 hard mode.
- expansion 모델 비교 (12 query × leader): glm-4.7 = kimi-k2-thinking (R@5 0.62) > qwen3-coder:480b (0.57). **코드 특화 모델은 자연어 paraphrase 생성에 불리**.
- self-match (query=record) 라 P@1/MRR 모든 path 1.00 → LOPO (아래) 로 변별력 회복.

**Phase 4-3b - LOPO (leave-one-paraphrase-out, 72 query)**

corpus = 그 task 의 5 paraphrase + 다른 task 의 모든 paraphrase + 30 noise. query = 빠진 1 paraphrase. 6 paraphrase 회전.

| 경로 | P@1 | R@5 | MRR | NDCG@5 |
|---|---:|---:|---:|---:|
| BM25 | 0.38 | 0.16 | 0.44 | 0.21 |
| vector | 0.65 | 0.46 | 0.74 | 0.51 |
| hybrid | 0.51 | 0.45 | 0.67 | 0.47 |
| reranked hybrid | 0.62 | 0.51 | 0.74 | 0.54 |
| **expanded hybrid** | **0.74** | **0.52** | **0.81** | **0.57** |

- **P@1 변별력 회복**: 이전 self-match 시드 (모든 path 1.00) 에선 죽은 메트릭. LOPO 에서는 0.38-0.74 로 path 우열 명확.
- **expanded hybrid 가 모든 metric 1위**. MRR 0.81 = 평균 첫 relevant rank 1.23 - **거의 항상 첫 결과가 정답**.
- BM25 R@5 0.16 - LOPO 환경 (key paraphrase 누락) 에서 키워드 매칭 한계 명확.
- σP@1 0.44-0.50 - query 마다 hit/miss 강하게 분리. paraphrase 표현이 검색 품질의 dominant 변수.

**해석**:
- BM25 는 키워드 일치 시드에서 완벽, paraphrase 시드에서 R=0.25 (놓침 많음).
- vector 는 paraphrase 에서 R **2.7배 우세** - 의미 매칭의 정량 가치.
- hybrid 는 두 환경 모두 vector 와 동일 - RRF 의 "더 좋아짐" 은 안 보였지만
  "보수적 안정" 가치 (양쪽 환경 모두에서 안 떨어짐).
- **LLM query expansion** (`recall_expanded`, mode="bm25") 이 BM25 paraphrase
  recall 을 **2배 향상** (0.25 → 0.50). vector 가 이미 강한 환경(0.67)
  에서는 expansion 한계 효용 X. 검색당 LLM 1 회 비용.
- **Cross-encoder reranker** (`recall_reranked`, base="hybrid") 의 R@5 향상
  은 36 record 시드에서 미미 (0.67 → 0.69) 였지만 **102 record 시드에서는
  0.50 → 0.54** 로 +0.04, candidate 경쟁이 커진 환경에서 가치 회복.
- **expanded hybrid (Phase 4)** 가 R@5 0.62 / P@5 0.75 로 **모든 path 중 1위**.
  vector/rerank 도 능가. cloud LLM 호출 비용 있는 대신 강한 paraphrase 환경에
  서 명확한 gain.

**의사결정**:
- 키워드 일치 환경: BM25 (Kiwi) 만으로 충분 (P@3 = 1.00).
- 가벼운 paraphrase: rerank 또는 vec (cloud 호출 0).
- 강한 paraphrase + cloud 가용: **expanded hybrid** (mode="hybrid", glm-4.7
  또는 kimi-k2-thinking).

> **검색 품질 - production RAG 진행 상황** (Phase 5 측정 종합)
>
> | 사용 시나리오 | path | P@1 | σR@5 | 가성비 |
> |---|---|---:|---:|---|
> | 키워드 일치 | BM25 (Kiwi) | 0.40 | 0.21 | cloud 0, 빠름 |
> | 가벼운 paraphrase | reranked hybrid | 0.66 | 0.26 | cloud 0 |
> | 강한 paraphrase | expanded hybrid | 0.67 | 0.23 | cloud 2회 |
> | normalized hybrid | normalized hybrid | 0.71 | 0.22 | cloud 1회 |
> | **production RAG** | **HyDE hybrid** | **0.92** | **0.16** | **cloud 1회** |
>
> - **normalized hybrid 가 P@1 / σ / 비용 모두 winner**. 524 record LOPO 측정.
> - σR@5 0.22 - 외부 권고 목표 0.15 에 점진 접근. 시드 확장 + normalization 효과.
> - **`auto_recall=always` 의 risk** : Phase 4-4 + 5-3 측정 모두 cloud LLM
>   (glm-4.7) 이 무관 recall prefix 강하게 무시 (kw_hit 0%). 즉 **자동 prepend
>   는 도움도 해도 작음**. 결론: 자동 prepend 자체에 큰 가치 없음. 기본값
>   `on_request` (사용자 명시 `tuna_recall` 호출) 유지가 정합.
> - **recall 의 진짜 가치** = 사용자가 명시 호출 → 5 후보 surface → 사람이
>   판단. P@5 0.73-0.75 / MRR 0.78-0.81 으로 이 UX 에 충분.

자세한 내역: `tests/integration/test_search_quality{,_synonym}.py`,
`docs/dogfooding-log.md` 의 검색 품질 섹션.

### 4.4. 그래프 엣지 - rule-based (Phase 2)

call 간 관계를 LLM 호출 없이 SQL JOIN 만으로 도출:
- `same_project`: 같은 `project_root`
- `same_day`: 같은 날짜 (`timestamp[:10]`)
- `same_tool`: 같은 `tool_name`

`a.id < b.id` 로 정규화 (양방향 중복 + self-loop 차단). `rebuild_edges(store)` + `traverse(store, start_id, max_hops, relations)` (Python BFS).

### 4.5. Query expansion - LLM 으로 검색률 향상 (Phase 3)

`recall_expanded(store, query, *, client, mode="bm25"|"hybrid", max_expansions=4)`
가 LLM 으로 query 를 동의어/paraphrase 4 개로 확장한 뒤 각 표현으로 검색해
RRF 로 합산. 모드:
- `mode="bm25"`: BM25 만 + expansion. paraphrase 약점 직접 공략. **R@5 가
  2배 (0.25 → 0.50)** 로 측정됨.
- `mode="hybrid"`: hybrid + expansion. vector 가 이미 우세한 환경에서는 한계
  효용 X.

LLM 호출 실패 / 응답 형식 깨짐 시 원 query 만으로 fallback - 안전성 보장.

### 4.6. Semantic edges - LLM 분류 (Phase 3)

`build_semantic_edges(store, client, max_pairs=100, project_root=...)` 가 같은 project 안 record 페어를 LLM 으로 분류 - `RELATED` / `UNRELATED` binary single-token (Phase 1.5 stage-2 classifier 와 동일 검증된 패턴). `RELATED` 페어는 `graph_edges.relation = 'semantic_related'` 로 INSERT.

비용 방어: `max_pairs` 한도, 이미 분류된 페어 skip (idempotent), `project_root` 좁힘. `rebuild_edges()` 는 rule edges 만 삭제 - semantic edges 보존.

## 5. Provider 추상화

```
LLMClient (ABC)
  ├─ OllamaClient          # ollama python SDK, 로컬/클라우드 모두 동일 클래스
  └─ LMStudioClient        # OpenAI 호환 /chat/completions, httpx
```

`LLMConfig` 의 `provider` 필드 한 줄로 선택. `ollama_cloud` 만 API 키가 환경변수로 필요하고, 나머지는 host/port 만 본다.

| Provider | host 기본값 | 키 |
|---|---|---|
| ollama | `http://localhost:11434` | 없음 |
| ollama_cloud | `https://ollama.com` | `api_key_env` 가 가리키는 환경변수 |
| lmstudio | `http://localhost:1234/v1` | 더미 |

테스트는 mock 을 쓰지 않고 실 Ollama Cloud + 로컬 LM Studio 에 붙는다. 서비스 미가용 시 `@pytest.mark.integration` 로 자동 skip.

## 6. Workflow - Architect ↔ Developer

### dev_review 루프

```python
def dev_review_loop(
    requirements: str, *, language=None, client, store=None,
    max_iterations: int = 2, review_focus=None, limitations_path=None,
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
    ...
```

heuristic: review 응답에 `LGTM`, `이상 없음` 등 종결 키워드가 있으면 수렴 처리. 그렇지 않으면 fix → 재 review.

### Spec 문서 형식

`docs/specs/<name>.md` 같은 곳에 markdown 으로 적는다. 헤더는 모두 옵션이지만 작은 모델일수록 명시할수록 안정적이다 - `gemento` 의 phase-driven decomposition + prioritized focus 패턴을 가져와 검증된 효과를 옮긴 것.

```markdown
# Task: build email validator

## Phase
IMPLEMENT          # DESIGN | IMPLEMENT | VERIFY

## Focus
정규식 검증 로직 먼저   # 한 줄 우선순위

## Requirements
- 정규식으로 1차 검증
- 빈 문자열 거부

## Constraints
- 표준 라이브러리만
- 외부 호출 없음

## Acceptance
- pytest 5 케이스 통과
```

`Constraints` 의 모든 항목은 hard rule 로 처리되며 위반 시 review 단계에서 잡혀 fix 루프로 들어간다.

### 약점 카탈로그

```bash
# Architect 가 패턴을 인지하면
tuna_log_limitation("한국어 docstring 작성 시 들여쓰기 어긋남")
```

→ `~/.tunallama/limitations.md` 에 기록되고, 이후 모든 `tuna_dev_review` 호출의 prompt 앞에 자동 prepend 되어 같은 실수를 줄인다. 자동 감지는 하지 않는다(아키텍트 판단).

## 7. Hook (옵션)

`plugin/hooks/pre_tool_use.py` 는 Claude 가 큰 파일을 `Read` 하려 할 때 advisory 메시지를 stderr 로 띄운다. block 하지 않는다. 활성화는 `~/.claude/settings.json` 또는 프로젝트 settings 의 `hooks.PreToolUse` 에 등록.

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

## 8. 설치

### 사용자 - 5 분 가이드

```bash
git clone https://github.com/hang-in/tunaLlama
cd tunaLlama

pip install -e .                # 또는 `uv pip install -e .`

tunallama init                  # 대화식 - provider/모델 자동 발견
tunallama doctor                # Python / config / provider / DB / Kiwi 검사

# Ollama Cloud 쓸 경우
echo "OLLAMA_CLOUD_API_KEY=발급받은_키" >> .env

# 영구 등록 - ~/.claude/settings.json 의 mcpServers 에:
# {
#   "mcpServers": {
#     "tunallama": {
#       "command": "/Users/me/tunaLlama/.venv/bin/python",
#       "args": ["-m", "plugin.mcp_server"],
#       "cwd": "/Users/me/tunaLlama"
#     }
#   }
# }
```

`cwd` 가 프로젝트 루트라면 plugin 이 시작 시 `.env` 와 `./.tunallama/config.toml` 을 자동 발견한다.

### 기여자

```bash
mise install                    # python 3.11 + uv
mise trust                      # mise.toml 신뢰 (보안)
mise run install                # editable + dev 의존성
mise run test                   # pytest
```

## 9. 테스트와 커버리지

```
$ pytest
... 249 passed in 8.65s
... TOTAL coverage 94%
```

- 단위 테스트는 `LLMClient` 의 fake (`StaticClient`) 를 사용. 응답 캡처 + 결정적 결과.
- 통합 테스트는 실 Ollama Cloud (`gemma4:31b`) + 로컬 LM Studio (`nvidia/nemotron-3-nano-4b`) 에 붙는다. 서비스 미가용 시 자동 skip.
- mock 남발은 의도적으로 회피했다. 외부 SDK 의 동작 변경(스키마, 타입)이 가려져 실서비스 회귀를 놓치는 것을 막기 위해.

## 10. 무엇이 아닌가

- tunaFlow 의 멀티 에이전트 라운드테이블 아님 - 그건 다른 프로젝트의 일.
- OllamaClaude 포크 아님 - 패턴 참고.
- Codex CLI 통합 아님 - Phase 4 별도 핸드오프.
- 단일 모델 데모 / 연구 노트북 아님.
- 자동 weakness 감지 / 동적 tool 작성 아님 - 아키텍트 판단으로 `tuna_log_limitation` 호출 (Phase 2 후보).

## 11. Phase 2 후보

`docs/handoff-tunallama-phase1.md` §0 의 reality-wins 정책에 따라, Phase 1 에서 의도적으로 미뤄둔 것:

- 벡터 임베딩(BGE-M3 등) + HNSW 시맨틱 검색
- RRF(Reciprocal Rank Fusion) 로 BM25 + 벡터 병합
- Rule-based 그래프 엣지 (`same_project`, `same_day`)
- LLM-derived 시맨틱 엣지 (`fixes_bug`, `modifies_file`)
- 자동 hook 라우팅 (Read → tuna_review_file 강제)
- Codex App Server 클라이언트
- 비대화식 `tunallama init --provider ... --model ...` 옵션
- gemento 의 remediation_hint 구조화 응답 (LLM 응답 파싱 fragility 때문에 보류)

## 12. 디렉토리에 있는 다른 문서

- `docs/handoff-tunallama-phase1.md` - 구현 진실 원천. 변경분은 `CHANGELOG.md` 에 기록.
- `docs/workflow.md` - Architect ↔ Subagent 워크플로우 한국어 가이드.
- `CHANGELOG.md` - Phase 1 / 1.5 변경 이력 + 핸드오프 대비 spec 변경분.
- `config.example.toml` - config 전체 필드 + 주석.
- `.env.example` - 환경변수 예시.

## 13. 라이선스 / 기여

MIT. 이슈/PR 환영. 한국어/영어 모두 가능. 영문 README 는 [README.en.md](README.en.md) 를 함께 동기화 유지.
