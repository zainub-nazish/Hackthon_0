"""
Social Media Posting Demo - Real API Integration

This demo shows how to use the production-ready social media skills
with real API credentials.

Setup:
  1. Copy .env.social.example to .env
  2. Fill in your API credentials
  3. Run this script
"""

import asyncio
from pathlib import Path

from agent_skills import AuditLogger, RecoverySkill, SocialMediaSkill


async def demo_twitter():
    """Demo: Post to X (Twitter)."""
    print("\n" + "=" * 70)
    print("  Twitter (X) Posting Demo")
    print("=" * 70)

    logger = AuditLogger("social_demo", log_dir="logs/social_demo/")
    recovery = RecoverySkill(logger=logger)
    social = SocialMediaSkill(recovery=recovery, logger=logger, dry_run=False)

    # Text-only tweet
    print("\n[1] Posting text-only tweet...")
    result = await social.post_to_twitter(
        text="Just launched our new AI agent system! 🚀 Built with Python and Claude. #AI #Automation"
    )

    print(f"  Status: {'SUCCESS' if result.success else 'FAILED'}")
    if result.success:
        print(f"  Post ID: {result.post_id}")
        print(f"  URL: {result.url}")
        print(f"  {result.engagement_prediction}")
    else:
        print(f"  Error: {result.error}")

    # Tweet with media
    print("\n[2] Posting tweet with image...")
    # Note: You need to provide a valid image path
    image_path = "path/to/your/image.jpg"
    if Path(image_path).exists():
        result = await social.post_to_twitter(
            text="Check out our latest feature! 📊",
            media_path=image_path
        )
        print(f"  Status: {'SUCCESS' if result.success else 'FAILED'}")
        if result.success:
            print(f"  Post ID: {result.post_id}")
            print(f"  URL: {result.url}")
    else:
        print(f"  Skipped: Image not found at {image_path}")


async def demo_facebook():
    """Demo: Post to Facebook Page."""
    print("\n" + "=" * 70)
    print("  Facebook Page Posting Demo")
    print("=" * 70)

    logger = AuditLogger("social_demo", log_dir="logs/social_demo/")
    recovery = RecoverySkill(logger=logger)
    social = SocialMediaSkill(recovery=recovery, logger=logger, dry_run=False)

    # Text post
    print("\n[1] Posting text to Facebook Page...")
    result = await social.post_to_facebook(
        message="Excited to announce our new autonomous agent system! "
                "It handles social media, audits, and task management automatically. "
                "Learn more at our website."
    )

    print(f"  Status: {'SUCCESS' if result.success else 'FAILED'}")
    if result.success:
        print(f"  Post ID: {result.post_id}")
        print(f"  URL: {result.url}")
        print(f"  {result.engagement_prediction}")
    else:
        print(f"  Error: {result.error}")

    # Post with link
    print("\n[2] Posting with link...")
    result = await social.post_to_facebook(
        message="Read our latest blog post about AI automation!",
        link="https://example.com/blog/ai-automation"
    )
    print(f"  Status: {'SUCCESS' if result.success else 'FAILED'}")

    # Post with image
    print("\n[3] Posting with image...")
    image_path = "path/to/your/image.jpg"
    if Path(image_path).exists():
        result = await social.post_to_facebook(
            message="Our team at work! 👨‍💻👩‍💻",
            image_path=image_path
        )
        print(f"  Status: {'SUCCESS' if result.success else 'FAILED'}")
    else:
        print(f"  Skipped: Image not found")


async def demo_instagram():
    """Demo: Post to Instagram Business account."""
    print("\n" + "=" * 70)
    print("  Instagram Business Posting Demo")
    print("=" * 70)

    logger = AuditLogger("social_demo", log_dir="logs/social_demo/")
    recovery = RecoverySkill(logger=logger)
    social = SocialMediaSkill(recovery=recovery, logger=logger, dry_run=False)

    print("\n[1] Posting image to Instagram...")
    print("  Note: Image must be publicly accessible URL for Instagram API")

    # Instagram requires publicly accessible image URL
    image_url = "https://example.com/images/product.jpg"

    result = await social.post_to_instagram(
        caption="New product launch! 🎉 Check out our latest innovation. "
                "#ProductLaunch #Innovation #Tech",
        image_path=image_url  # Must be public URL
    )

    print(f"  Status: {'SUCCESS' if result.success else 'FAILED'}")
    if result.success:
        print(f"  Post ID: {result.post_id}")
        print(f"  URL: {result.url}")
        print(f"  {result.engagement_prediction}")
    else:
        print(f"  Error: {result.error}")


async def demo_cross_post():
    """Demo: Cross-post to multiple platforms."""
    print("\n" + "=" * 70)
    print("  Cross-Platform Posting Demo")
    print("=" * 70)

    logger = AuditLogger("social_demo", log_dir="logs/social_demo/")
    recovery = RecoverySkill(logger=logger)
    social = SocialMediaSkill(recovery=recovery, logger=logger, dry_run=False)

    print("\n[1] Cross-posting to Twitter and Facebook...")
    results = await social.cross_post(
        text="Big announcement! 🚀 Our new AI system is live. "
             "Automates social media, audits, and more. #AI #Automation",
        platforms=["twitter", "facebook"]
    )

    for platform, result in results.items():
        print(f"\n  {platform.upper()}:")
        print(f"    Status: {'SUCCESS' if result.success else 'FAILED'}")
        if result.success:
            print(f"    Post ID: {result.post_id}")
            print(f"    URL: {result.url}")
            print(f"    {result.engagement_prediction}")
        else:
            print(f"    Error: {result.error}")


async def demo_dry_run():
    """Demo: Dry-run mode (no actual API calls)."""
    print("\n" + "=" * 70)
    print("  Dry-Run Mode Demo (Safe Testing)")
    print("=" * 70)

    logger = AuditLogger("social_demo", log_dir="logs/social_demo/")
    recovery = RecoverySkill(logger=logger)
    social = SocialMediaSkill(recovery=recovery, logger=logger, dry_run=True)

    print("\n[1] Dry-run: Twitter post...")
    result = await social.post_to_twitter(
        text="This is a test post. It won't actually be published! 🧪"
    )

    # Result is a SkillResult, data contains the PostResult
    post_result = result.data if hasattr(result, 'data') else result

    print(f"  Status: {post_result.success}")
    print(f"  Post ID (mock): {post_result.post_id}")
    print(f"  URL (mock): {post_result.url}")
    print(f"  {post_result.engagement_prediction}")

    print("\n[2] Dry-run: Cross-post...")
    results_wrapper = await social.cross_post(
        text="Testing cross-platform posting in dry-run mode.",
        platforms=["twitter", "facebook"]
    )

    # Unwrap outer SkillResult to get the dict
    results = results_wrapper.data if hasattr(results_wrapper, 'data') else results_wrapper

    # Each value in the dict is also a SkillResult wrapping a PostResult
    for platform, result_wrapper in results.items():
        post_result = result_wrapper.data if hasattr(result_wrapper, 'data') else result_wrapper
        print(f"\n  {platform}: {post_result.post_id}")
        print(f"    {post_result.engagement_prediction}")


async def main():
    print("=" * 70)
    print("  Social Media Skills - Production Demo")
    print("=" * 70)
    print("\nThis demo shows real API integration with:")
    print("  - X (Twitter) API v2")
    print("  - Facebook Graph API")
    print("  - Instagram Graph API")
    print("\nMake sure you've configured credentials in .env file!")

    # Check if running in dry-run mode
    import os
    from dotenv import load_dotenv
    load_dotenv()

    has_twitter = all([
        os.getenv("TWITTER_API_KEY"),
        os.getenv("TWITTER_API_SECRET"),
        os.getenv("TWITTER_ACCESS_TOKEN"),
        os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
    ])

    has_facebook = all([
        os.getenv("FACEBOOK_ACCESS_TOKEN"),
        os.getenv("FACEBOOK_PAGE_ID")
    ])

    has_instagram = all([
        os.getenv("INSTAGRAM_ACCESS_TOKEN"),
        os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    ])

    print("\n[CREDENTIALS CHECK]")
    print(f"  Twitter: {'[OK] Configured' if has_twitter else '[X] Missing'}")
    print(f"  Facebook: {'[OK] Configured' if has_facebook else '[X] Missing'}")
    print(f"  Instagram: {'[OK] Configured' if has_instagram else '[X] Missing'}")

    if not any([has_twitter, has_facebook, has_instagram]):
        print("\n[!] No credentials found. Running in DRY-RUN mode.")
        print("    To use real APIs, copy .env.social.example to .env and add credentials.")
        await demo_dry_run()
    else:
        print("\n[OK] Credentials found. Running with real APIs...")

        if has_twitter:
            await demo_twitter()

        if has_facebook:
            await demo_facebook()

        if has_instagram:
            await demo_instagram()

        if has_twitter and has_facebook:
            await demo_cross_post()

    print("\n" + "=" * 70)
    print("  Demo Complete!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Check logs/social_demo/ for detailed logs")
    print("  2. View your posts on the respective platforms")
    print("  3. Integrate into your autonomous agent workflows")


if __name__ == "__main__":
    asyncio.run(main())
