"""
Weekly Audit Scheduler Demo

Demonstrates automated weekly CEO briefing generation using the schedule library.
Can be run as a background service or cron job.
"""

import asyncio
import schedule
import time
from datetime import datetime
from pathlib import Path

from agent_skills import AuditLogger, RecoverySkill, AuditSkill


def generate_weekly_briefing():
    """Generate weekly CEO briefing - called by scheduler."""
    print(f"[{datetime.now()}] Generating weekly CEO briefing...")
    
    async def run_briefing():
        logger = AuditLogger("weekly_audit", log_dir="logs/weekly_audit/")
        recovery = RecoverySkill(logger=logger)
        audit = AuditSkill(recovery=recovery, logger=logger, db_path="data/accounting.db")
        
        # Generate briefing
        briefing_wrapper = await audit.generate_ceo_briefing(days=7, format="markdown")
        briefing_md = briefing_wrapper.data if hasattr(briefing_wrapper, 'data') else briefing_wrapper
        
        # Save with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("reports/weekly")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"ceo_briefing_{timestamp}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(briefing_md)
        
        # Also save as latest
        latest_file = output_dir / "ceo_briefing_latest.md"
        with open(latest_file, "w", encoding="utf-8") as f:
            f.write(briefing_md)
        
        print(f"[OK] Briefing saved to {output_file}")
        print(f"[OK] Latest briefing: {latest_file}")
        
        # Generate JSON version for API/integrations
        briefing_json_wrapper = await audit.generate_ceo_briefing(days=7, format="json")
        briefing_json = briefing_json_wrapper.data if hasattr(briefing_json_wrapper, 'data') else briefing_json_wrapper
        
        json_file = output_dir / f"ceo_briefing_{timestamp}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            f.write(briefing_json)
        
        print(f"[OK] JSON briefing saved to {json_file}")
    
    # Run async function
    asyncio.run(run_briefing())


def main():
    """Main scheduler loop."""
    print("=" * 80)
    print("  Weekly Audit Scheduler")
    print("=" * 80)
    print()
    print("Schedule: Every Monday at 9:00 AM")
    print("Press Ctrl+C to stop")
    print()
    
    # Schedule weekly briefing every Monday at 9 AM
    schedule.every().monday.at("09:00").do(generate_weekly_briefing)
    
    # For testing: also run every 5 minutes (comment out in production)
    # schedule.every(5).minutes.do(generate_weekly_briefing)
    
    # Run once immediately for testing
    print("[INFO] Running initial briefing generation...")
    generate_weekly_briefing()
    print()
    
    # Keep running
    print("[INFO] Scheduler started. Waiting for next scheduled run...")
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("
[INFO] Scheduler stopped by user")
