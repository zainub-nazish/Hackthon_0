# Gold Tier Autonomous Employee — Architecture

> Version 1.0 · 2026-05-01

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component Map](#2-component-map)
3. [Orchestrator → Skills → MCP Servers](#3-orchestrator--skills--mcp-servers)
4. [Social Posting Flow](#4-social-posting-flow)
5. [Weekly Audit Flow](#5-weekly-audit-flow)
6. [Ralph Wiggum Loop](#6-ralph-wiggum-loop)
7. [Error Recovery Strategy](#7-error-recovery-strategy)
8. [Data Flows & Storage](#8-data-flows--storage)
9. [Security & Credentials](#9-security--credentials)
10. [Lessons Learned](#10-lessons-learned)

---

## 1. System Overview

The Gold Tier Autonomous Employee is a fully autonomous AI agent system that handles:

- **Social Media**: automated posting and engagement analytics across Facebook, Instagram, and X (Twitter)
- **Business Auditing**: weekly accounting review using local SQLite/CSV (no Odoo dependency)
- **CEO Briefings**: auto-generated markdown + JSON reports delivered on a schedule
- **Task Management**: cross-domain personal + business task tracking with priority scoring
- **Self-Healing**: circuit breakers, exponential back-off, and registered fallbacks

The system is built around three principles:

| Principle | Implementation |
|---|---|
| **Modularity** | Every capability is a standalone `AgentSkill` with a clean async API |
| **Resilience** | All external calls go through `RecoverySkill` (retry + circuit breaker + fallback) |
| **Observability** | Every action, decision, and error is recorded as structured JSON |

---

## 2. Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Gold Tier Autonomous Employee                    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │               main_orchestrator.py                          │   │
│  │  GoldTierOrchestrator · APScheduler · Ralph Wiggum Loop     │   │
│  └──────────┬──────────────────────────────────────────────────┘   │
│             │ uses                                                  │
│   ┌─────────▼──────────────────────────────────────────────┐       │
│   │                  agent_skills/                          │       │
│   │  ┌──────────┐ ┌────────┐ ┌──────────┐ ┌────────────┐  │       │
│   │  │ social   │ │ audit  │ │ recovery │ │ personal_  │  │       │
│   │  │ .py      │ │ .py    │ │ .py      │ │ business   │  │       │
│   │  └──────────┘ └────────┘ └──────────┘ └────────────┘  │       │
│   │  ┌─────────────────────────────────────────────────┐   │       │
│   │  │              audit_logger.py                    │   │       │
│   │  └─────────────────────────────────────────────────┘   │       │
│   └────────────────────────────┬───────────────────────────┘       │
│                                │ exposed via                        │
│   ┌────────────────────────────▼───────────────────────────┐       │
│   │                   mcp_servers/                          │       │
│   │   ┌──────────────┐ ┌──────────────┐ ┌───────────────┐  │       │
│   │   │ social_mcp   │ │ audit_mcp    │ │ recovery_mcp  │  │       │
│   │   │ (stdio)      │ │ (stdio)      │ │ (stdio)       │  │       │
│   │   └──────────────┘ └──────────────┘ └───────────────┘  │       │
│   └────────────────────────────────────────────────────────┘       │
│                                                                     │
│   ┌────────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐  │
│   │ config/    │  │ logs/        │  │ data/      │  │ docs/    │  │
│   │ .env       │  │ *.jsonl      │  │ *.db *.csv │  │ ARCH...  │  │
│   └────────────┘  └──────────────┘  └────────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Orchestrator → Skills → MCP Servers

```mermaid
graph TD
    subgraph Orchestrator["main_orchestrator.py"]
        O[GoldTierOrchestrator]
        S[APScheduler]
        L[Ralph Wiggum Loop]
        O --> S
        O --> L
    end

    subgraph Skills["agent_skills/"]
        SOC[SocialMediaSkill]
        AUD[AuditSkill]
        REC[RecoverySkill]
        PB[PersonalBusinessSkill]
        LOG[AuditLogger]
    end

    subgraph MCP["mcp_servers/ (stdio JSON-RPC 2.0)"]
        SMCP[social_mcp.py]
        AMCP[audit_mcp.py]
        RMCP[recovery_mcp.py]
    end

    subgraph External["External APIs"]
        TW[X / Twitter API v2]
        FB[Facebook Graph API]
        IG[Instagram Graph API]
    end

    subgraph Storage["Local Storage"]
        DB[(SQLite: audit.db / tasks.db)]
        CSV[CSV exports]
        LOGS[JSONL logs]
        BR[Markdown briefings]
    end

    O --> SOC
    O --> AUD
    O --> PB
    O --> REC

    SOC --> SMCP
    AUD --> AMCP
    REC --> RMCP

    SMCP -->|tools/call| TW
    SMCP -->|tools/call| FB
    SMCP -->|tools/call| IG

    AUD --> DB
    PB --> DB
    AUD --> CSV
    AUD --> BR
    LOG --> LOGS

    SOC -.->|all calls wrapped| REC
    AUD -.->|all calls wrapped| REC
    PB  -.->|all calls wrapped| REC
```

---

## 4. Social Posting Flow

```mermaid
sequenceDiagram
    participant Orch as Orchestrator
    participant SOC as SocialMediaSkill
    participant REC as RecoverySkill
    participant CB as CircuitBreaker
    participant API as Platform API
    participant LOG as AuditLogger

    Orch->>SOC: cross_post(text, platforms)
    loop for each platform
        SOC->>REC: execute_with_recovery(skill, action, fn)
        REC->>CB: allow_request()?
        alt Circuit CLOSED or HALF_OPEN
            CB-->>REC: true
            REC->>API: HTTP POST (tweet / fb feed / ig media)
            alt Success
                API-->>REC: 200 OK + post_id
                REC->>CB: record_success()
                REC-->>SOC: RecoveryResult(success=True)
            else Failure
                API-->>REC: error
                REC->>CB: record_failure()
                alt retries remain
                    REC->>REC: exponential backoff sleep
                    REC->>API: retry
                else retries exhausted / circuit OPEN
                    REC->>SOC: try_fallback (queue for retry)
                end
            end
        else Circuit OPEN
            CB-->>REC: false (fast fail)
            REC->>SOC: try_fallback
        end
        SOC->>LOG: log_action(skill, action, result)
        SOC->>SOC: delay between platforms (2s)
    end
    SOC-->>Orch: dict[platform → PostResult]
```

---

## 5. Weekly Audit Flow

```mermaid
flowchart TD
    SCHED["APScheduler\n(every Monday 08:00)"]
    TRIGGER["_weekly_audit_job()"]
    LOOP["Ralph Wiggum Loop\ngoal: 'Weekly business audit'"]

    SOCIAL_FETCH["SocialMediaSkill\ngenerate_all_summaries(7 days)"]
    TASK_ANALYSIS["PersonalBusinessSkill\ncross_domain_analysis()"]
    COMPUTE["AuditSkill\n_compute_metrics(start, end)"]
    DB_QUERY[("SQLite\nSELECT transactions\nWHERE date BETWEEN ...")]
    BRIEFING["AuditSkill\n_generate_briefing()"]
    ALERTS["Alert detection\n• expense ratio > 80%\n• error rate > 5%\n• no data warning"]

    SAVE_MD["Write markdown\ndata/briefings/briefing_YYYYMMDD.md"]
    SAVE_JSON["Write JSON\ndata/briefings/briefing_YYYYMMDD.json"]
    LOG["AuditLogger\nlog_audit_event(weekly_audit_complete)"]
    NOTIFY["(Optional) Email/Slack\nCEO briefing delivery"]

    SCHED --> TRIGGER --> LOOP
    LOOP --> SOCIAL_FETCH
    LOOP --> TASK_ANALYSIS
    SOCIAL_FETCH --> COMPUTE
    TASK_ANALYSIS --> COMPUTE
    COMPUTE --> DB_QUERY
    DB_QUERY --> COMPUTE
    COMPUTE --> ALERTS
    ALERTS --> BRIEFING
    BRIEFING --> SAVE_MD
    BRIEFING --> SAVE_JSON
    SAVE_MD --> LOG
    SAVE_JSON --> LOG
    LOG --> NOTIFY
```

---

## 6. Ralph Wiggum Loop

The autonomous multi-step loop is named after Homer Simpson's observation:
> *"I'm Ralph Wiggum — I'm not sure what I'm doing but I keep doing it anyway."*

The loop keeps iterating (observe → reason → act) until the goal is achieved or a maximum iteration cap is hit.

```mermaid
stateDiagram-v2
    [*] --> IDLE

    IDLE --> RUNNING : run_autonomous_loop(goal, plan)

    state RUNNING {
        [*] --> OBSERVE
        OBSERVE --> REASON : gather state snapshot
        REASON --> ACT : select next step from plan
        ACT --> EVALUATE : execute skill handler
        EVALUATE --> OBSERVE : step done, not finished
        EVALUATE --> [*] : goal_check() == True
        REASON --> [*] : plan exhausted
    }

    RUNNING --> SUCCEEDED : goal_check passed or plan done
    RUNNING --> MAX_ITER : iteration >= max_iterations
    RUNNING --> FAILED : unrecoverable error

    SUCCEEDED --> [*]
    MAX_ITER --> [*]
    FAILED --> [*]
```

### Loop phases in detail

| Phase | What happens |
|---|---|
| **OBSERVE** | Snapshot: open circuits, pending critical tasks, last error |
| **REASON** | Select the next unexecuted step from the plan; return `None` if done |
| **ACT** | Dispatch to skill handler; record duration and result |
| **EVALUATE** | Check goal condition; if step failed, log and continue (recovery already tried) |
| **LOOP** | Sleep `loop_sleep_seconds`; increment iteration counter |

### Built-in safeguards

- **Max iterations** (`app.max_iterations = 25`) — hard ceiling, no infinite loops
- **Per-step recovery** — every `_act()` call goes through `RecoverySkill`
- **Checkpoint logging** — every step result written to `logs/actions.jsonl`
- **Goal check callback** — caller can supply custom completion predicate

---

## 7. Error Recovery Strategy

```mermaid
flowchart LR
    CALL["skill.action()"]
    CB_CHECK{"Circuit\nBREAKER\ncheck"}
    EXEC["Execute\nfn()"]
    SUCCESS{Success?}
    RECORD_OK["record_success()\ndecrease failure count"]
    RECORD_FAIL["record_failure()\nincrement count"]
    RETRY{"retries\nremain?"}
    BACKOFF["exponential\nbackoff sleep\n1s · 2s · 4s ..."]
    CB_OPEN{"threshold\nhit?"}
    OPEN_CB["circuit → OPEN\nfast-fail future calls"]
    FALLBACK{"fallback\nregistered?"}
    RUN_FB["run fallback fn\n(queue / mock / cached)"]
    FAIL["RecoveryResult\nsuccess=False"]
    DONE["RecoveryResult\nsuccess=True"]

    CALL --> CB_CHECK
    CB_CHECK -->|CLOSED / HALF_OPEN| EXEC
    CB_CHECK -->|OPEN| FALLBACK

    EXEC --> SUCCESS
    SUCCESS -->|yes| RECORD_OK --> DONE
    SUCCESS -->|no| RECORD_FAIL
    RECORD_FAIL --> CB_OPEN
    CB_OPEN -->|yes| OPEN_CB --> FALLBACK
    CB_OPEN -->|no| RETRY
    RETRY -->|yes| BACKOFF --> EXEC
    RETRY -->|no| FALLBACK
    FALLBACK -->|yes| RUN_FB --> DONE
    FALLBACK -->|no| FAIL
```

### Circuit breaker states

```
  CLOSED ──[failures >= threshold]──► OPEN
     ▲                                  │
     │                                  │ recovery_timeout elapsed
     │                                  ▼
     └──[2 probes succeed]──── HALF_OPEN
```

| State | Behaviour |
|---|---|
| **CLOSED** | All requests pass through normally |
| **OPEN** | All requests fast-fail → fallback immediately |
| **HALF_OPEN** | 1 probe request; success → CLOSED, failure → OPEN |

### Fallback hierarchy

1. **Registered fallback** (e.g., queue post for later)
2. **Cached/mock response** (e.g., return last known social summary)
3. **Graceful degradation** (log + continue loop without that capability)
4. **Alert** (log CRITICAL + surface in next CEO briefing under Risks)

---

## 8. Data Flows & Storage

```
data/
├── audit.db          — SQLite: financial transactions (double-entry rows)
├── tasks.db          — SQLite: personal + business tasks
├── exports/          — CSV snapshots exported on demand
│   └── transactions_YYYY-MM-DD_YYYY-MM-DD.csv
└── briefings/        — CEO briefings
    ├── briefing_YYYYMMDD.md   (Jinja2 rendered markdown)
    └── briefing_YYYYMMDD.json (machine-readable)

logs/
├── actions.jsonl     — every skill action (rotating, 10 MB)
├── errors.jsonl      — every error with severity + recoverable flag
└── audit.jsonl       — decisions, state changes, audit events
```

---

## 9. Security & Credentials

| Rule | Implementation |
|---|---|
| No secrets in code | All credentials loaded from `.env` via `pydantic-settings` |
| `SecretStr` wrapper | `get_secret_value()` required to unwrap; prevents accidental logging |
| `.env` not committed | `.gitignore` includes `.env` |
| Cached credential objects | `@lru_cache(maxsize=1)` — credentials loaded once per process |
| Token rotation | Swap `.env` values and restart; no code changes needed |

---

## 10. Lessons Learned

### What worked well

1. **RecoverySkill as a shared infrastructure layer** — wrapping every external call through one place made it trivial to add circuit breakers post-hoc without touching skill code.

2. **Async-first design** — using `asyncio.gather` for cross-platform posting and summary generation cut wall-clock time significantly vs. sequential calls.

3. **SQLite over Odoo for accounting** — removing the Odoo dependency eliminated a whole class of network failure modes during hackathon testing. The local DB is fast, zero-config, and trivially exportable to CSV.

4. **Jinja2 for CEO briefings** — separating the template from the data made it easy to iterate the report format without touching business logic.

5. **Structured JSON logging (JSONL)** — `jq`-queryable logs made post-run debugging dramatically faster than grepping plain text.

### Tradeoffs & known limitations

| Area | Tradeoff |
|---|---|
| Social APIs | Instagram Graph API requires a Business account + Facebook Page linkage; `instagrapi` is a fallback but violates ToS for production |
| MCP transport | Stdio transport is simple but limits parallelism; upgrade to SSE/HTTP for multi-client scenarios |
| Accounting | Local SQLite works for single-operator use; multi-user or multi-entity accounting needs a proper ledger (e.g., hledger, Actual Budget) |
| Loop reasoning | `_reason()` currently just executes a static plan list; upgrading to LLM-based planning (Claude tool-use loop) would enable truly dynamic step selection |
| Scheduling | APScheduler in-process is fine for a single node; distributed scheduling (Celery Beat, Modal cron) needed for HA deployments |

### Recommended next steps

1. **Wire in Claude API** for dynamic plan generation inside `_reason()` — turn the static plan list into a live reasoning loop.
2. **Add SSE transport** to MCP servers so they can be registered in Claude Code desktop and used interactively.
3. **Email/Slack delivery** for CEO briefings — `NotificationCreds` is already wired; just needs a `send_briefing()` method.
4. **Add `hledger` or `beancount` adapter** as a drop-in replacement for the SQLite accounting layer.
