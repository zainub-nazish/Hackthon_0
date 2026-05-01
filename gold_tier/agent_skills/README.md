# Agent Skills System

A production-ready autonomous agent framework with comprehensive audit logging, error recovery, and MCP integration.

## Architecture

```
agent_skills/
├── base.py                  # Core decorator, registry, and BaseSkill ABC
├── audit_logger.py          # Structured JSONL logging (actions, errors, audit)
├── recovery.py              # Retry, circuit breaker, fallback mechanisms
├── autonomous_agent.py      # Ralph Wiggum loop executor
├── audit.py                 # Weekly audit & CEO briefing skill
├── personal_business.py     # Cross-domain task management skill
└── social.py                # Social media posting skill
```

## Key Features

### 1. Decorator-Based Skill Registration

```python
from agent_skills import BaseSkill, agent_skill

class MySkill(BaseSkill):
    SKILL_NAME = "my_skill"

    @agent_skill(
        name="do_something",
        description="Does something useful",
        domain=["business", "personal"]
    )
    async def do_something(self, param: str) -> dict:
        return {"result": f"processed {param}"}
```

**What the decorator does:**
- Auto-registers the skill in `SkillRegistry`
- Infers JSON Schema from type hints
- Wraps execution with timing and structured logging
- Converts exceptions to `SkillResult(success=False)`
- Exposes as MCP tool automatically

### 2. Comprehensive Audit Logging

Every skill call is logged to structured JSONL files:

```python
from agent_skills import AuditLogger

logger = AuditLogger("my_app", log_dir="logs/")

# Logs to logs/actions.jsonl
logger.log_action("skill", "action", {"param": "value"}, "result", duration_ms=123.45)

# Logs to logs/errors.jsonl
logger.log_error("skill", "action", exception, severity="ERROR", recoverable=True)

# Logs to logs/audit.jsonl
logger.log_decision("context", "decision", "rationale", ["alt1", "alt2"])
logger.log_state_change("component", "old_state", "new_state", "reason")
```

**Log format:**
```json
{
  "ts": "2026-05-01T22:32:11.698Z",
  "level": "INFO",
  "event_type": "action",
  "skill": "social",
  "action": "post_twitter",
  "params": {"text": "Hello world"},
  "result_summary": "PostResult(success=True, post_id='123')",
  "duration_ms": 234.56
}
```

### 3. Error Recovery & Graceful Degradation

```python
from agent_skills import RecoverySkill

recovery = RecoverySkill(
    max_retries=3,
    backoff_base=1.0,
    backoff_multiplier=2.0,
    circuit_failure_threshold=5,
    circuit_recovery_timeout=60.0
)

# Register fallback
async def fallback_post():
    return {"queued": True}

recovery.register_fallback("social.post_twitter", fallback_post)

# Execute with automatic retry + circuit breaker + fallback
result = await recovery.execute_with_recovery(
    "social", "post_twitter", post_fn, text="Hello"
)

if result.success:
    print(f"Posted (fallback={result.fallback_used})")
else:
    print(f"Failed after {result.attempts} attempts: {result.last_error}")
```

**Recovery features:**
- **Exponential backoff**: 1s, 2s, 4s delays between retries
- **Circuit breaker**: Opens after N failures, prevents cascading failures
- **Fallback**: Graceful degradation when primary fails
- **State tracking**: Monitor circuit status via `recovery.circuit_status()`

### 4. Autonomous Agent with Ralph Wiggum Loop

```python
from agent_skills import AutonomousAgent, SocialMediaSkill, AuditSkill

agent = AutonomousAgent(
    skills=[SocialMediaSkill(), AuditSkill()],
    recovery=recovery,
    logger=logger
)

# Single task execution
result = await agent.execute_task({
    "skill": "social",
    "action": "post_twitter",
    "params": {"text": "Hello world"}
})

# Ralph Wiggum loop: Plan → Execute → Verify → Fix → Log
report = await agent.run_ralph_wiggum_loop(
    task_description="Run weekly audit and post summary",
    max_iterations=20,
    exit_criteria="briefing_path"
)

print(f"Goal achieved: {report.goal_achieved}")
print(f"Iterations: {report.total_iterations}")
print(f"Progress file: {report.progress_file}")
```

**Loop design:**
- Fresh context each iteration (no prompt bloat)
- Compact progress summary injected as context
- Automatic verification and fix attempts
- Persists progress to `data/progress/progress_*.json`
- Exits when goal met or max iterations hit

### 5. MCP Integration

All decorated skills are automatically exposed as MCP tools:

```python
from agent_skills import SkillRegistry

# Get all registered skills
skills = SkillRegistry.names()
# ['post_twitter', 'post_facebook', 'run_weekly_audit', ...]

# Get MCP tool schemas
tools = SkillRegistry.mcp_tool_list()
# [{"name": "post_twitter", "description": "...", "inputSchema": {...}}, ...]

# Filter by domain
business_tools = SkillRegistry.by_domain("business")
```

**MCP servers** (stdio JSON-RPC):
- `mcp_servers/social_mcp.py` - Social media tools
- `mcp_servers/audit_mcp.py` - Audit and task management tools
- `mcp_servers/recovery_mcp.py` - Circuit breaker status and health checks

Run standalone:
```bash
python -m mcp_servers.social_mcp
python -m mcp_servers.audit_mcp
python -m mcp_servers.recovery_mcp
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the demo

```bash
python main_orchestrator.py
```

### 3. Run tests

```bash
python test_agent_skills.py
```

## Creating a New Skill

```python
from agent_skills import BaseSkill, agent_skill, SkillResult
from agent_skills import AuditLogger, RecoverySkill

class WeatherSkill(BaseSkill):
    SKILL_NAME = "weather"

    def __init__(self, recovery=None, logger=None):
        super().__init__(recovery=recovery, logger=logger)
        # Your initialization here

    @agent_skill(
        name="get_forecast",
        description="Get weather forecast for a location",
        domain=["personal", "business"]
    )
    async def get_forecast(self, location: str, days: int = 3) -> dict:
        # Your implementation here
        return {
            "location": location,
            "forecast": ["sunny", "cloudy", "rainy"][:days]
        }

    @agent_skill(
        name="get_alerts",
        description="Get weather alerts for a location",
        domain=["personal"]
    )
    async def get_alerts(self, location: str) -> list[str]:
        # Your implementation here
        return ["No active alerts"]
```

**Register with the agent:**

```python
weather = WeatherSkill(recovery=recovery, logger=logger)
agent = AutonomousAgent(
    skills=[weather, social, audit],
    recovery=recovery,
    logger=logger
)
```

The skill is now:
- Registered in `SkillRegistry`
- Exposed via MCP
- Available to the Ralph Wiggum loop
- Wrapped with audit logging and error recovery

## Configuration

Edit `config/settings.yaml`:

```yaml
app:
  max_iterations: 25
  retry_attempts: 3
  retry_backoff_multiplier: 2

recovery:
  max_retries: 3
  circuit_breaker_threshold: 5
  circuit_breaker_timeout: 60

logging:
  dir: "logs/"
  rotation_max_bytes: 10485760
  rotation_backup_count: 5
```

## Monitoring

### View logs

```bash
# Actions log
tail -f logs/actions.jsonl | jq

# Errors log
tail -f logs/errors.jsonl | jq

# Audit log
tail -f logs/audit.jsonl | jq
```

### Check circuit breaker status

```python
status = recovery.circuit_status()
# {"social.post_twitter": "closed", "audit.run_weekly_audit": "open"}

errors = recovery.error_summary()
# {"social.post_twitter": 3, "audit.run_weekly_audit": 12}
```

### View progress files

```bash
cat data/progress/progress_*.json | jq
```

## Production Deployment

1. **Enable persistent logging**: Set `log_dir` to a persistent volume
2. **Configure circuit breakers**: Tune thresholds based on your SLOs
3. **Register fallbacks**: Ensure critical paths have fallback handlers
4. **Monitor logs**: Set up alerts on error rates and circuit opens
5. **Backup progress files**: Archive `data/progress/` for audit trail

## Testing

Run the comprehensive test suite:

```bash
python test_agent_skills.py
```

Tests cover:
- Skill registration and MCP schema exposure
- Audit logging to JSONL files
- Retry with exponential backoff
- Circuit breaker state transitions
- Fallback execution
- Single task execution
- Ralph Wiggum loop with verification

## License

Proprietary - Gold Tier Autonomous Employee System
