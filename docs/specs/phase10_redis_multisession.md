# Phase 10 — Redis 멀티세션 컨텍스트 레이어 (설계 스파이크)

> 상태: **설계 스파이크**. 아래 "tunaRound 실측 결론" 이후 **권고 = 지금은 도입 보류**.

## tunaRound 실측 결론 (2026-07-03)

tunaRound `src/session_bus.rs` 헤더: *"Redis 기반 세션 버스 프리미티브(멀티세션
런타임 조율). **memory.db 대체 아님, hot 미러**."* SessionBus trait =
`submit_command_json` / `publish_event_json` / `snapshot_json`. Redis 키 per session:
owner / commands(stream) / command_cursor / events(stream) / event_channel /
presence / hot_snapshot. Redis Streams(xadd/xread) + pub/sub + presence + snapshot.

→ **tunaRound 는 본질적으로 멀티세션 런타임**(REPL/runtime 이 세션별 command/event
스트림을 조율, "observe session"). Redis 는 그 프로세스 간 조율 버스라서 필수.
tunaRound 내부 codex 크리틱조차 *"단일 세션에 Redis 필수 의존은 원칙적 문제,
SQLite 가 핵심 영속 경로"* 라고 명시.

**tunaLlama 는 단일 세션 위임 런타임**이다. 세션 간 실시간 조율/observe 모델이
없고, delegation 기록·state.md 는 요청 세션 안에서 소비된다. → **tunaRound 와
같은 need 가 구조적으로 없다.** Redis 는 "문제 없는 곳의 해법" 이 된다. 게다가
tunaLlama 의 가치는 "Ollama 만 있으면 오프라인 동작" — Redis 의존은 이와 상충.

### 권고

1. **지금은 Redis 도입 보류.** SQLite 유지. tunaRound 가 Redis 를 쓴다는 이유만
   으로 미러링하지 않는다 (용도가 다름).
2. 향후 멀티세션 조율이 실제로 필요해지면 — tunaLlama 가 **자체 Redis 를 띄우지
   말고 tunaRound 의 기존 session bus 에 delegation 이벤트를 publish** 하는 방향이
   합리적 (인프라 재사용, SQLite SoT 유지). 아래 설계는 그때의 참고안.

---

> (참고 설계 — 도입 결정 시)

## 동기

- tunaRound / tunaSalon 은 서로 다른 세션의 에이전트들이 **컨텍스트를 실시간
  공유**하는 멀티세션 레이어로 Redis 를 쓴다.
- tunallama 의 메모리는 현재 **로컬 SQLite**(`~/.tunallama/memory.db`) + 파일
  `state.md`. 장점은 "Ollama 만 있으면 오프라인 동작". 단점은 **동시에 도는 여러
  에이전트 세션(Claude Code + Codex + 서브에이전트) 간 즉시 공유가 안 됨** — 각자
  같은 SQLite 를 열지만 실시간 pub/sub·조율은 없다.

## 핵심 원칙

**SQLite 가 기본, Redis 는 옵셔널 백엔드.** 오프라인·제로인프라 기본값을 절대
깨지 않는다. Redis 미설정 시 현재와 100% 동일 동작.

## 무엇을 세션 간 공유하는가 (범위 정의 — 열린 질문 1)

tunallama 의 공유 후보 3종:

| 데이터 | 현재 저장 | 멀티세션 공유 가치 |
|---|---|---|
| **delegation 기록** (tuna_* 호출 in/out) | memory.db (SQLite) | 중 — 다른 세션이 방금 위임한 결과를 recall. 하지만 SQLite 도 파일 공유로 가능 |
| **project `state.md`** (규약/결정/안티패턴) | 파일 | 중 — 한 세션의 결정이 다른 세션에 즉시 반영 |
| **live 세션 조율** (누가 무슨 파일 작업 중, 진행 락) | 없음 | **상** — Redis 가 진짜 이기는 지점. pub/sub, 분산 락, presence |

→ delegation/state 는 SQLite+파일로도 "결국" 공유된다(폴링). Redis 의 고유 가치는
**실시간 조율(presence, pub/sub, 락)** 이다. 이 레이어를 새로 정의하는 게 핵심.

## 설계 (제안)

### 백엔드 추상화

```
ContextBackend (interface)
  - publish(channel, event)         # 세션 이벤트 브로드캐스트
  - subscribe(channel) -> stream    # 다른 세션 이벤트 수신
  - kv_set/get(key, ttl)            # presence, 진행 상태
  - lock(resource) / unlock         # 분산 락 (파일/작업 단위)

구현:
  - NullBackend (기본): 전부 no-op. 현재 동작 그대로.
  - RedisBackend (옵셔널): redis-py. `[multisession]` extra.
```

- `memory.db` 는 **그대로 유지** (SoT). Redis 는 **휘발성 조율 레이어**만.
  Redis 다운 → NullBackend 로 graceful degrade (recall/생성은 계속 됨).

### 설정

```toml
[multisession]
enabled = false                      # 기본 off
backend = "redis"                    # redis | none
redis_url = "redis://localhost:6379/0"
session_id_env = "TUNA_SESSION_ID"   # 세션 식별 (agent+pid+ts)
namespace = "tunallama"              # 키 prefix (프로젝트 hash 로 스코프)
```

### 이벤트 스키마 (초안)

```
{ "session": "<id>", "agent": "claude-code|codex",
  "kind": "delegation_done|state_updated|working_on|lock",
  "project": "<hash>", "ts": "...", "payload": {...} }
```

### MCP 표면 (선택)

- `tuna_session_presence()` — 현재 이 프로젝트에서 활성인 세션 목록.
- delegation 완료 시 자동 publish → 다른 세션이 `tuna_recall` 시 fresh 반영.
- (남용 방지: pub/sub 스팸이 상위 모델 컨텍스트를 오염시키지 않도록 opt-in pull.)

## 마이그레이션 / 호환

- 코드 없이 켜고 끔 (`enabled=false` 기본). 기존 사용자 영향 0.
- `redis` 는 `[multisession]` extra — 기본 설치에 미포함.

## 열린 질문 (구현 전 결정 필요)

1. **범위**: 실시간 조율(presence/lock/pub-sub)만? 아니면 delegation/state 미러링까지?
   (권장: 조율 레이어부터 — Redis 고유 가치. 미러링은 SQLite 로 충분할 수 있음)
2. **스코프 경계**: 프로젝트 hash 단위? 머신 단위? 여러 머신 걸쳐 공유?
3. **tunaRound/tunaSalon 과 Redis 인스턴스/네임스페이스 공유**? 아니면 tunallama 전용 db?
4. **이벤트 무엇을 자동 push** 할지 — 컨텍스트 오염 위험 vs 유용성 균형.
5. Codex 세션도 같은 백엔드 참여? (MCP 는 공유되나 hook 메커니즘 상이 — Phase 8 참조)

## 다음 단계

열린 질문 1~2 합의 → `ContextBackend` 인터페이스 + `NullBackend` 먼저 머지(무해)
→ `RedisBackend` 프로토타입 → tunaRound 와 상호운용 테스트.
