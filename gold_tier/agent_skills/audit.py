"""
Audit Skill - Comprehensive Business and Personal Analytics

Generates professional reports combining:
- Financial data (revenue, expenses)
- Task completion metrics
- Social media performance
- Personal activities (fitness, learning)
- Recommendations and risk analysis
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .audit_logger import AuditLogger
from .base import BaseSkill, agent_skill
from .recovery import RecoverySkill


@dataclass
class BusinessMetrics:
    period_start: str
    period_end: str
    total_revenue: float
    total_expenses: float
    net_profit: float
    profit_margin: float
    revenue_by_category: dict[str, float]
    expense_by_category: dict[str, float]
    tasks_completed: int
    avg_task_duration_ms: float
    social_posts: int
    total_engagement: int
    avg_engagement_per_post: float
    top_platform: str


@dataclass
class PersonalMetrics:
    period_start: str
    period_end: str
    fitness_sessions: int
    total_fitness_time: float
    learning_hours: float
    activities_by_category: dict[str, int]


@dataclass
class CEOBriefing:
    generated_at: str
    period: str
    executive_summary: list[str]
    key_metrics: dict[str, Any]
    recommendations: list[str]
    risks: list[str]
    business_metrics: BusinessMetrics
    personal_metrics: PersonalMetrics


class AuditSkill(BaseSkill):
    """Comprehensive audit and reporting skill."""

    SKILL_NAME = "audit"

    def __init__(
        self,
        recovery: RecoverySkill | None = None,
        logger: AuditLogger | None = None,
        db_path: str = "data/accounting.db",
    ) -> None:
        super().__init__(recovery=recovery, logger=logger)
        self.db_path = db_path

    def _get_db_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    @agent_skill(
        name="generate_weekly_business_audit",
        description="Generate comprehensive weekly business audit with revenue, expenses, tasks, and social performance.",
        domain=["business"],
        input_schema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Number of days to analyze", "default": 7}
            },
        },
    )
    async def generate_weekly_business_audit(self, days: int = 7) -> BusinessMetrics:
        """Generate weekly business audit."""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        conn = self._get_db_connection()
        cursor = conn.cursor()

        # Revenue and expenses
        cursor.execute(
            """
            SELECT type, category, SUM(amount) as total
            FROM transactions
            WHERE date >= ? AND date <= ?
            GROUP BY type, category
            """,
            (str(start_date), str(end_date))
        )

        revenue_by_cat = {}
        expense_by_cat = {}
        total_revenue = 0.0
        total_expenses = 0.0

        for row in cursor.fetchall():
            type_, category, total = row
            if type_ == "revenue":
                revenue_by_cat[category] = total
                total_revenue += total
            else:
                expense_by_cat[category] = total
                total_expenses += total

        net_profit = total_revenue - total_expenses
        profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0.0

        # Tasks
        cursor.execute(
            """
            SELECT COUNT(*), AVG(duration_ms)
            FROM tasks
            WHERE date >= ? AND date <= ? AND status = 'completed'
            """,
            (str(start_date), str(end_date))
        )
        tasks_completed, avg_duration = cursor.fetchone()
        tasks_completed = tasks_completed or 0
        avg_duration = avg_duration or 0.0

        # Social posts
        cursor.execute(
            """
            SELECT platform, COUNT(*), SUM(likes + comments + shares) as engagement
            FROM social_posts
            WHERE date >= ? AND date <= ?
            GROUP BY platform
            """,
            (str(start_date), str(end_date))
        )

        social_data = cursor.fetchall()
        total_posts = sum(row[1] for row in social_data)
        total_engagement = sum(row[2] for row in social_data)
        avg_engagement = (total_engagement / total_posts) if total_posts > 0 else 0.0

        top_platform = max(social_data, key=lambda x: x[2])[0] if social_data else "none"

        conn.close()

        return BusinessMetrics(
            period_start=str(start_date),
            period_end=str(end_date),
            total_revenue=total_revenue,
            total_expenses=total_expenses,
            net_profit=net_profit,
            profit_margin=profit_margin,
            revenue_by_category=revenue_by_cat,
            expense_by_category=expense_by_cat,
            tasks_completed=tasks_completed,
            avg_task_duration_ms=avg_duration,
            social_posts=total_posts,
            total_engagement=total_engagement,
            avg_engagement_per_post=avg_engagement,
            top_platform=top_platform,
        )

    @agent_skill(
        name="generate_ceo_briefing",
        description="Generate professional CEO briefing with executive summary, key metrics, recommendations, and risks.",
        domain=["business"],
        input_schema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Number of days to analyze", "default": 7},
                "format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"}
            },
        },
    )
    async def generate_ceo_briefing(self, days: int = 7, format: str = "markdown") -> str:
        """Generate CEO briefing."""
        business_wrapper = await self.generate_weekly_business_audit(days)
        business = business_wrapper.data if hasattr(business_wrapper, 'data') else business_wrapper
        personal = await self._get_personal_metrics(days)
        summary = self._generate_executive_summary(business, personal)
        recommendations = self._generate_recommendations(business, personal)
        risks = self._identify_risks(business, personal)
        briefing = CEOBriefing(
            generated_at=datetime.now(timezone.utc).isoformat(),
            period=f"{business.period_start} to {business.period_end}",
            executive_summary=summary,
            key_metrics=self._extract_key_metrics(business, personal),
            recommendations=recommendations,
            risks=risks,
            business_metrics=business,
            personal_metrics=personal,
        )
        if format == "json":
            return json.dumps(self._briefing_to_dict(briefing), indent=2)
        else:
            return self._format_briefing_markdown(briefing)

    @agent_skill(
        name="cross_domain_summary",
        description="Generate cross-domain summary combining personal and business metrics.",
        domain=["business", "personal"],
        input_schema={"type": "object", "properties": {"days": {"type": "integer", "description": "Number of days to analyze", "default": 7}}},
    )
    async def cross_domain_summary(self, days: int = 7) -> dict[str, Any]:
        """Generate cross-domain summary."""
        business_wrapper = await self.generate_weekly_business_audit(days)
        business = business_wrapper.data if hasattr(business_wrapper, 'data') else business_wrapper
        personal = await self._get_personal_metrics(days)
        return {
            "period": f"{business.period_start} to {business.period_end}",
            "business": {"revenue": business.total_revenue, "profit": business.net_profit, "profit_margin": f"{business.profit_margin:.1f}%", "tasks_completed": business.tasks_completed, "social_engagement": business.total_engagement},
            "personal": {"fitness_sessions": personal.fitness_sessions, "learning_hours": personal.learning_hours, "total_activities": sum(personal.activities_by_category.values())},
            "balance_score": self._calculate_balance_score(business, personal),
            "insights": self._generate_cross_domain_insights(business, personal),
        }

    async def _get_personal_metrics(self, days: int) -> PersonalMetrics:
        """Get personal activity metrics."""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        conn = self._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT category, activity, metric, value FROM personal_activities WHERE date >= ? AND date <= ?", (str(start_date), str(end_date)))
        fitness_sessions = 0
        total_fitness_time = 0.0
        learning_hours = 0.0
        activities_by_cat = {}
        for row in cursor.fetchall():
            category, activity, metric, value = row
            activities_by_cat[category] = activities_by_cat.get(category, 0) + 1
            if category == "fitness":
                fitness_sessions += 1
                if metric == "duration_min":
                    total_fitness_time += value
            elif category == "learning" and metric == "hours":
                learning_hours += value
        conn.close()
        return PersonalMetrics(period_start=str(start_date), period_end=str(end_date), fitness_sessions=fitness_sessions, total_fitness_time=total_fitness_time, learning_hours=learning_hours, activities_by_category=activities_by_cat)

    def _generate_executive_summary(self, business: BusinessMetrics, personal: PersonalMetrics) -> list[str]:
        """Generate executive summary bullets."""
        summary = []
        if business.net_profit > 0:
            summary.append(f"Strong financial performance with ${business.net_profit:,.2f} net profit ({business.profit_margin:.1f}% margin)")
        else:
            summary.append(f"Net loss of ${abs(business.net_profit):,.2f} this period - revenue optimization needed")
        summary.append(f"Completed {business.tasks_completed} tasks with average execution time of {business.avg_task_duration_ms:.1f}ms")
        if business.social_posts > 0:
            summary.append(f"Published {business.social_posts} social posts generating {business.total_engagement} total engagements (avg {business.avg_engagement_per_post:.1f} per post)")
        if personal.learning_hours > 0:
            summary.append(f"Invested {personal.learning_hours:.1f} hours in learning and {personal.fitness_sessions} fitness sessions")
        return summary

    def _generate_recommendations(self, business: BusinessMetrics, personal: PersonalMetrics) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []
        if business.profit_margin < 20:
            recommendations.append("Increase profit margin: Current margin is below 20%. Consider raising prices or reducing operational costs.")
        if business.total_expenses > business.total_revenue * 0.7:
            recommendations.append("High expense ratio: Expenses are >70% of revenue. Review and optimize spending in top expense categories.")
        if business.avg_engagement_per_post < 50:
            recommendations.append("Improve social engagement: Average engagement is low. Focus on content quality and posting times.")
        if personal.fitness_sessions < 3:
            recommendations.append(f"Increase physical activity: Only {personal.fitness_sessions} sessions this week. Target 3-5 sessions for optimal health.")
        if personal.learning_hours < 5:
            recommendations.append("Invest more in learning: Aim for 5-10 hours per week to stay competitive and grow skills.")
        if not recommendations:
            recommendations.append("All metrics are healthy. Continue current strategies.")
        return recommendations

    def _identify_risks(self, business: BusinessMetrics, personal: PersonalMetrics) -> list[str]:
        """Identify potential risks."""
        risks = []
        if business.net_profit < 0:
            risks.append("CRITICAL: Negative cash flow. Immediate action required to reduce expenses or increase revenue.")
        if len(business.revenue_by_category) == 1:
            risks.append("Revenue concentration risk: All revenue from single source. Diversify income streams.")
        if business.tasks_completed < 5:
            risks.append("Low productivity: Few tasks completed. May indicate bottlenecks or resource constraints.")
        if personal.fitness_sessions == 0 and personal.learning_hours > 20:
            risks.append("Burnout risk: High work/learning hours with no physical activity. Balance needed.")
        if not risks:
            risks.append("No significant risks identified.")
        return risks

    def _extract_key_metrics(self, business: BusinessMetrics, personal: PersonalMetrics) -> dict[str, Any]:
        """Extract key metrics for dashboard."""
        return {"revenue": f"${business.total_revenue:,.2f}", "profit": f"${business.net_profit:,.2f}", "profit_margin": f"{business.profit_margin:.1f}%", "tasks_completed": business.tasks_completed, "social_posts": business.social_posts, "social_engagement": business.total_engagement, "fitness_sessions": personal.fitness_sessions, "learning_hours": f"{personal.learning_hours:.1f}h"}

    def _calculate_balance_score(self, business: BusinessMetrics, personal: PersonalMetrics) -> float:
        """Calculate work-life balance score (0-100)."""
        score = 50.0
        if personal.fitness_sessions >= 3:
            score += 15
        if personal.learning_hours >= 5:
            score += 15
        if business.profit_margin > 20:
            score += 10
        if business.avg_engagement_per_post > 50:
            score += 10
        if personal.fitness_sessions == 0:
            score -= 20
        if business.net_profit < 0:
            score -= 15
        return max(0, min(100, score))

    def _generate_cross_domain_insights(self, business: BusinessMetrics, personal: PersonalMetrics) -> list[str]:
        """Generate insights across domains."""
        insights = []
        balance_score = self._calculate_balance_score(business, personal)
        if balance_score >= 80:
            insights.append("Excellent work-life balance maintained")
        elif balance_score >= 60:
            insights.append("Good balance, minor adjustments recommended")
        else:
            insights.append("Balance needs attention - prioritize personal wellness")
        if business.net_profit > 0 and personal.learning_hours > 5:
            insights.append("Strong performance with continued skill development")
        if business.tasks_completed > 10 and personal.fitness_sessions >= 3:
            insights.append("High productivity paired with healthy lifestyle")
        return insights

    def _format_briefing_markdown(self, briefing: CEOBriefing) -> str:
        """Format briefing as markdown."""
        md = f"# CEO Briefing\n**Period:** {briefing.period}\n**Generated:** {briefing.generated_at}\n\n---\n\n## Executive Summary\n\n"
        for item in briefing.executive_summary:
            md += f"- {item}\n"
        md += "\n## Key Metrics\n\n"
        for key, value in briefing.key_metrics.items():
            md += f"- **{key.replace('_', ' ').title()}:** {value}\n"
        md += "\n## Recommendations\n\n"
        for i, rec in enumerate(briefing.recommendations, 1):
            md += f"{i}. {rec}\n"
        md += "\n## Risks & Concerns\n\n"
        for i, risk in enumerate(briefing.risks, 1):
            md += f"{i}. {risk}\n"
        md += f"\n---\n\n## Detailed Metrics\n\n### Financial Performance\n- **Total Revenue:** ${briefing.business_metrics.total_revenue:,.2f}\n- **Total Expenses:** ${briefing.business_metrics.total_expenses:,.2f}\n- **Net Profit:** ${briefing.business_metrics.net_profit:,.2f}\n- **Profit Margin:** {briefing.business_metrics.profit_margin:.1f}%\n\n### Operational Performance\n- **Tasks Completed:** {briefing.business_metrics.tasks_completed}\n- **Avg Task Duration:** {briefing.business_metrics.avg_task_duration_ms:.1f}ms\n\n### Social Media Performance\n- **Total Posts:** {briefing.business_metrics.social_posts}\n- **Total Engagement:** {briefing.business_metrics.total_engagement}\n- **Avg Engagement/Post:** {briefing.business_metrics.avg_engagement_per_post:.1f}\n- **Top Platform:** {briefing.business_metrics.top_platform}\n\n### Personal Development\n- **Fitness Sessions:** {briefing.personal_metrics.fitness_sessions}\n- **Learning Hours:** {briefing.personal_metrics.learning_hours:.1f}\n\n---\n\n*Generated by Autonomous Agent Skills System*\n"
        return md

    def _briefing_to_dict(self, briefing: CEOBriefing) -> dict:
        """Convert briefing to dictionary."""
        return {"generated_at": briefing.generated_at, "period": briefing.period, "executive_summary": briefing.executive_summary, "key_metrics": briefing.key_metrics, "recommendations": briefing.recommendations, "risks": briefing.risks, "business_metrics": {"total_revenue": briefing.business_metrics.total_revenue, "total_expenses": briefing.business_metrics.total_expenses, "net_profit": briefing.business_metrics.net_profit, "profit_margin": briefing.business_metrics.profit_margin, "tasks_completed": briefing.business_metrics.tasks_completed, "social_posts": briefing.business_metrics.social_posts, "total_engagement": briefing.business_metrics.total_engagement}, "personal_metrics": {"fitness_sessions": briefing.personal_metrics.fitness_sessions, "learning_hours": briefing.personal_metrics.learning_hours}}
