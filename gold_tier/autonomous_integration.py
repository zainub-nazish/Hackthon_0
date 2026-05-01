"""
Autonomous Integration System
Connects MCP server, audit skills, and autonomous decision-making.

This system:
1. Runs weekly audits automatically
2. Analyzes CEO briefings for actionable insights
3. Takes autonomous actions based on business metrics
4. Posts social updates about performance
5. Logs all decisions and actions
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agent_skills.audit import AuditSkill
from agent_skills.social import SocialSkill
from agent_skills.recovery import RecoverySkill
from agent_skills.audit_logger import AuditLogger


class AutonomousIntegration:
    """Autonomous system that integrates all components."""

    def __init__(self, log_dir: str = "logs/autonomous"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize logger
        self.logger = AuditLogger(
            log_dir=str(self.log_dir),
            session_name="autonomous_integration"
        )

        # Initialize skills
        self.recovery = RecoverySkill(logger=self.logger)
        self.audit_skill = AuditSkill(recovery=self.recovery, logger=self.logger)
        self.social_skill = SocialSkill(recovery=self.recovery, logger=self.logger)

        # Decision state
        self.last_audit_date = None
        self.decision_history = []

    async def run_weekly_cycle(self) -> dict[str, Any]:
        """Run complete weekly business cycle."""
        self.logger.log_info("Starting weekly autonomous cycle")

        # 1. Generate CEO briefing
        briefing_result = await self.audit_skill.generate_ceo_briefing(days=7, format="json")
        briefing_data = briefing_result.data if hasattr(briefing_result, 'data') else briefing_result
        briefing = json.loads(briefing_data)

        self.logger.log_info(f"Generated briefing for period: {briefing['period']}")

        # 2. Analyze and make decisions
        decisions = await self._analyze_and_decide(briefing)

        # 3. Execute actions
        actions_taken = await self._execute_decisions(decisions)

        # 4. Post social update about performance
        social_update = await self._post_performance_update(briefing)

        # 5. Save cycle report
        cycle_report = {
            "timestamp": datetime.now().isoformat(),
            "briefing_period": briefing["period"],
            "decisions_made": len(decisions),
            "actions_taken": len(actions_taken),
            "social_posted": social_update is not None,
            "decisions": decisions,
            "actions": actions_taken
        }

        self._save_cycle_report(cycle_report)

        self.logger.log_info(f"Weekly cycle complete: {len(decisions)} decisions, {len(actions_taken)} actions")

        return cycle_report

    async def _analyze_and_decide(self, briefing: dict[str, Any]) -> list[dict[str, Any]]:
        """Analyze briefing and make autonomous decisions."""
        decisions = []

        business = briefing["business_metrics"]
        key_metrics = briefing["key_metrics"]

        # Decision 1: Profit margin analysis
        profit_margin = business["profit_margin"]
        if profit_margin < 20:
            decisions.append({
                "type": "cost_optimization",
                "priority": "high",
                "reason": f"Profit margin at {profit_margin:.1f}% (target: >20%)",
                "action": "review_expenses",
                "target": "reduce expenses by 10%"
            })
        elif profit_margin > 80:
            decisions.append({
                "type": "growth_investment",
                "priority": "medium",
                "reason": f"Strong margin at {profit_margin:.1f}% - opportunity to invest",
                "action": "increase_marketing",
                "target": "allocate 10% of profit to growth"
            })

        # Decision 2: Social engagement analysis
        avg_engagement = business.get("avg_engagement_per_post", 0)
        if avg_engagement < 50:
            decisions.append({
                "type": "content_strategy",
                "priority": "medium",
                "reason": f"Low engagement at {avg_engagement:.1f} per post (target: >50)",
                "action": "improve_content_quality",
                "target": "test new content formats, post at optimal times"
            })
        elif avg_engagement > 100:
            decisions.append({
                "type": "content_scaling",
                "priority": "low",
                "reason": f"High engagement at {avg_engagement:.1f} - scale successful content",
                "action": "increase_posting_frequency",
                "target": "double posting frequency while maintaining quality"
            })

        # Decision 3: Task efficiency analysis
        tasks_completed = business.get("tasks_completed", 0)
        if tasks_completed < 5:
            decisions.append({
                "type": "productivity",
                "priority": "high",
                "reason": f"Low task completion at {tasks_completed} (target: >10/week)",
                "action": "identify_bottlenecks",
                "target": "analyze task logs, remove blockers"
            })

        # Decision 4: Revenue diversification
        revenue_by_cat = business.get("revenue_by_category", {})
        if len(revenue_by_cat) == 1:
            decisions.append({
                "type": "risk_mitigation",
                "priority": "high",
                "reason": "Single revenue source - concentration risk",
                "action": "diversify_revenue",
                "target": "develop 2 additional revenue streams"
            })

        self.logger.log_info(f"Made {len(decisions)} autonomous decisions")

        return decisions

    async def _execute_decisions(self, decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Execute autonomous actions based on decisions."""
        actions = []

        for decision in decisions:
            action_type = decision["type"]

            # For now, log decisions and create action items
            # In production, this would trigger actual system changes
            action = {
                "decision_type": action_type,
                "priority": decision["priority"],
                "status": "logged",
                "timestamp": datetime.now().isoformat(),
                "next_steps": decision["target"]
            }

            # Simulate some actions
            if action_type == "content_strategy":
                # Could trigger content generation or scheduling
                action["status"] = "scheduled"
                action["details"] = "Content review scheduled for next cycle"

            elif action_type == "cost_optimization":
                # Could trigger expense analysis
                action["status"] = "analysis_queued"
                action["details"] = "Expense breakdown analysis queued"

            actions.append(action)
            self.logger.log_info(f"Executed action: {action_type} - {action['status']}")

        return actions

    async def _post_performance_update(self, briefing: dict[str, Any]) -> dict[str, Any] | None:
        """Post social media update about business performance."""
        business = briefing["business_metrics"]

        # Only post if metrics are positive
        if business["net_profit"] <= 0:
            self.logger.log_info("Skipping social post - negative profit")
            return None

        # Craft performance update
        profit_margin = business["profit_margin"]
        tasks = business["tasks_completed"]
        engagement = business.get("total_engagement", 0)

        # Create engaging post text
        post_text = f"📊 Weekly Performance Update:\n\n"
        post_text += f"✅ {tasks} tasks completed\n"
        post_text += f"💰 {profit_margin:.1f}% profit margin\n"
        post_text += f"📈 {engagement} social engagements\n\n"
        post_text += f"Continuous improvement in action! 🚀\n\n"
        post_text += f"#BusinessMetrics #Productivity #Growth"

        # Post to Twitter (dry-run mode)
        try:
            result = await self.social_skill.post_twitter(
                text=post_text,
                media_path=None,
                dry_run=True
            )

            post_result = result.data if hasattr(result, 'data') else result

            self.logger.log_info(f"Posted performance update: {post_result.post_id}")

            return {
                "platform": "twitter",
                "post_id": post_result.post_id,
                "url": post_result.url,
                "text": post_text
            }
        except Exception as e:
            self.logger.log_error(f"Failed to post update: {e}")
            return None

    def _save_cycle_report(self, report: dict[str, Any]) -> None:
        """Save cycle report to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.log_dir / f"cycle_report_{timestamp}.json"

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        # Also save as "latest"
        latest_path = self.log_dir / "cycle_report_latest.json"
        with open(latest_path, "w") as f:
            json.dump(report, f, indent=2)

        self.logger.log_info(f"Saved cycle report: {report_path}")

    async def run_continuous(self, interval_hours: int = 168) -> None:
        """Run continuous autonomous loop (default: weekly = 168 hours)."""
        self.logger.log_info(f"Starting continuous autonomous loop (interval: {interval_hours}h)")

        while True:
            try:
                # Run weekly cycle
                await self.run_weekly_cycle()

                # Wait for next cycle
                self.logger.log_info(f"Sleeping for {interval_hours} hours until next cycle")
                await asyncio.sleep(interval_hours * 3600)

            except KeyboardInterrupt:
                self.logger.log_info("Autonomous loop interrupted by user")
                break
            except Exception as e:
                self.logger.log_error(f"Error in autonomous loop: {e}")
                # Wait 1 hour before retry on error
                await asyncio.sleep(3600)


async def main():
    """Run autonomous integration system."""
    integration = AutonomousIntegration()

    print("=" * 60)
    print("AUTONOMOUS INTEGRATION SYSTEM")
    print("=" * 60)
    print()
    print("Running weekly business cycle...")
    print()

    # Run one cycle
    report = await integration.run_weekly_cycle()

    print()
    print("=" * 60)
    print("CYCLE COMPLETE")
    print("=" * 60)
    print()
    print(f"Period: {report['briefing_period']}")
    print(f"Decisions Made: {report['decisions_made']}")
    print(f"Actions Taken: {report['actions_taken']}")
    print(f"Social Posted: {report['social_posted']}")
    print()

    if report['decisions']:
        print("DECISIONS:")
        for i, decision in enumerate(report['decisions'], 1):
            print(f"  {i}. [{decision['priority'].upper()}] {decision['type']}")
            print(f"     Reason: {decision['reason']}")
            print(f"     Action: {decision['action']}")
            print(f"     Target: {decision['target']}")
            print()

    print(f"Full report saved to: logs/autonomous/cycle_report_latest.json")
    print()


if __name__ == "__main__":
    asyncio.run(main())
