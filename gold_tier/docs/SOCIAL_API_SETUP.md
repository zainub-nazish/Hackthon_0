# Social Media API Setup Guide

Complete guide for setting up real API credentials for Facebook, Instagram, and X (Twitter).

---

## Prerequisites

- Python 3.10+
- Active accounts on Facebook, Instagram (Business), and X (Twitter)
- Developer access to each platform

---

## 1. X (Twitter) API Setup

### Step 1: Create a Twitter Developer Account

1. Go to [https://developer.twitter.com](https://developer.twitter.com)
2. Sign in with your Twitter account
3. Apply for a developer account (usually approved within minutes)

### Step 2: Create an App

1. Go to the [Developer Portal](https://developer.twitter.com/en/portal/dashboard)
2. Click "Create Project" → "Create App"
3. Fill in app details:
   - App name: "Your App Name"
   - Description: "Social media automation"
   - Website: Your website URL

### Step 3: Get API Credentials

1. In your app settings, go to "Keys and tokens"
2. Generate/copy these credentials:
   - **API Key** (Consumer Key)
   - **API Secret** (Consumer Secret)
   - **Access Token**
   - **Access Token Secret**

3. Set permissions to "Read and Write"

### Step 4: Add to .env

```bash
TWITTER_API_KEY=your_api_key_here
TWITTER_API_SECRET=your_api_secret_here
TWITTER_ACCESS_TOKEN=your_access_token_here
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret_here
```

---

## 2. Facebook Page API Setup

### Step 1: Create a Facebook App

1. Go to [https://developers.facebook.com](https://developers.facebook.com)
2. Click "My Apps" → "Create App"
3. Select "Business" as app type
4. Fill in app details

### Step 2: Add Facebook Login Product

1. In your app dashboard, click "Add Product"
2. Select "Facebook Login"
3. Configure settings (Web platform)

### Step 3: Get Page Access Token

1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app from dropdown
3. Click "Generate Access Token"
4. Grant permissions:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
5. Copy the **User Access Token**

### Step 4: Get Long-Lived Token

```bash
curl -X GET "https://graph.facebook.com/v18.0/oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=SHORT_LIVED_TOKEN"
```

### Step 5: Get Page ID and Page Access Token

```bash
curl -X GET "https://graph.facebook.com/v18.0/me/accounts?access_token=LONG_LIVED_USER_TOKEN"
```

This returns your pages. Copy the `id` and `access_token` for your page.

### Step 6: Add to .env

```bash
FACEBOOK_ACCESS_TOKEN=your_page_access_token_here
FACEBOOK_PAGE_ID=your_page_id_here
```

---

## 3. Instagram Business API Setup

### Prerequisites

- Instagram Business or Creator account
- Facebook Page connected to Instagram account

### Step 1: Connect Instagram to Facebook Page

1. Go to Instagram Settings → Account → Linked Accounts
2. Link to your Facebook Page

### Step 2: Get Instagram Business Account ID

```bash
curl -X GET "https://graph.facebook.com/v18.0/me/accounts?fields=instagram_business_account&access_token=YOUR_PAGE_ACCESS_TOKEN"
```

Copy the `instagram_business_account.id`

### Step 3: Add to .env

```bash
INSTAGRAM_ACCESS_TOKEN=your_page_access_token_here
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_instagram_business_account_id_here
```

**Note:** Instagram uses the same access token as your Facebook Page.

---

## 4. Testing Your Setup

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Test in Dry-Run Mode (Safe)

```bash
python demo_social_real.py
```

This will run without making actual API calls.

### Test with Real APIs

1. Copy `.env.social.example` to `.env`
2. Fill in your credentials
3. Run the demo:

```bash
python demo_social_real.py
```

---

## 5. Important Notes

### Rate Limits

- **Twitter:** 300 tweets per 3 hours (user context)
- **Facebook:** ~200 posts per hour per page
- **Instagram:** ~25 posts per day per account

The skill includes automatic rate limiting to prevent throttling.

### Media Upload Requirements

**Twitter:**
- Images: JPG, PNG, GIF (max 5MB)
- Videos: MP4 (max 512MB)

**Facebook:**
- Images: JPG, PNG (max 4MB)
- Videos: MP4, MOV (max 1GB)

**Instagram:**
- Images: JPG, PNG (min 320px, max 1080px width)
- Must be publicly accessible URL
- Aspect ratio: 4:5 to 1.91:1

### Security Best Practices

1. **Never commit .env to git**
   - Already in .gitignore
   - Use environment variables in production

2. **Rotate tokens regularly**
   - Facebook: Tokens expire after 60 days
   - Twitter: Tokens don't expire but should be rotated

3. **Use least privilege**
   - Only request permissions you need
   - Revoke unused app access

4. **Monitor API usage**
   - Check developer dashboards regularly
   - Set up alerts for unusual activity

---

## 6. Troubleshooting

### Twitter Errors

**Error: "403 Forbidden"**
- Check app permissions (must be Read and Write)
- Regenerate access tokens after changing permissions

**Error: "429 Too Many Requests"**
- You've hit rate limit
- Wait 15 minutes and try again
- Skill will automatically retry with backoff

### Facebook Errors

**Error: "Invalid OAuth access token"**
- Token expired (60 days)
- Generate new long-lived token

**Error: "Permissions error"**
- Grant required permissions in Graph API Explorer
- Regenerate token with correct permissions

**Error: "Image upload failed"**
- Check image file size (max 4MB)
- Ensure file path is correct

### Instagram Errors

**Error: "Invalid media URL"**
- Image must be publicly accessible
- Upload to CDN first (S3, Cloudinary, etc.)
- Cannot use local file paths

**Error: "Media not ready"**
- Instagram takes time to process media
- Wait 30 seconds between container creation and publishing

---

## 7. Production Deployment

### Environment Variables

Set these in your production environment:

```bash
export TWITTER_API_KEY="..."
export TWITTER_API_SECRET="..."
export TWITTER_ACCESS_TOKEN="..."
export TWITTER_ACCESS_TOKEN_SECRET="..."
export FACEBOOK_ACCESS_TOKEN="..."
export FACEBOOK_PAGE_ID="..."
export INSTAGRAM_ACCESS_TOKEN="..."
export INSTAGRAM_BUSINESS_ACCOUNT_ID="..."
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Load env vars from secrets
ENV TWITTER_API_KEY=${TWITTER_API_KEY}
ENV FACEBOOK_ACCESS_TOKEN=${FACEBOOK_ACCESS_TOKEN}

CMD ["python", "main_orchestrator.py"]
```

### Monitoring

1. **Log all API calls**
   - Already implemented in `audit_logger.py`
   - Check `logs/social_demo/actions.jsonl`

2. **Track rate limits**
   - Monitor `X-Rate-Limit-Remaining` headers
   - Set up alerts when approaching limits

3. **Monitor errors**
   - Check `logs/social_demo/errors.jsonl`
   - Set up alerts for repeated failures

---

## 8. Example Usage in Code

```python
from agent_skills import SocialMediaSkill, RecoverySkill, AuditLogger

# Initialize
logger = AuditLogger("my_app")
recovery = RecoverySkill(logger=logger)
social = SocialMediaSkill(recovery=recovery, logger=logger, dry_run=False)

# Post to Twitter
result = await social.post_to_twitter(
    text="Hello world! 🌍",
    media_path="image.jpg"
)

if result.success:
    print(f"Posted: {result.url}")
    print(result.engagement_prediction)
else:
    print(f"Failed: {result.error}")

# Cross-post
results = await social.cross_post(
    text="Big announcement! 🚀",
    platforms=["twitter", "facebook"],
    image_path="announcement.jpg"
)
```

---

## Support

For issues:
1. Check logs in `logs/social_demo/`
2. Verify credentials in `.env`
3. Test with dry-run mode first
4. Check platform API status pages

---

**Last Updated:** 2026-05-01
