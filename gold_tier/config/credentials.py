"""
Credentials loader — all secrets come from .env, never hardcoded.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_FILE, override=False)


class TwitterCreds(BaseSettings):
    api_key: SecretStr = Field(alias="TWITTER_API_KEY")
    api_secret: SecretStr = Field(alias="TWITTER_API_SECRET")
    access_token: SecretStr = Field(alias="TWITTER_ACCESS_TOKEN")
    access_token_secret: SecretStr = Field(alias="TWITTER_ACCESS_TOKEN_SECRET")
    bearer_token: SecretStr = Field(alias="TWITTER_BEARER_TOKEN")

    class Config:
        env_file = str(_ENV_FILE)
        populate_by_name = True


class FacebookCreds(BaseSettings):
    app_id: SecretStr = Field(alias="FACEBOOK_APP_ID")
    app_secret: SecretStr = Field(alias="FACEBOOK_APP_SECRET")
    page_access_token: SecretStr = Field(alias="FACEBOOK_PAGE_ACCESS_TOKEN")
    page_id: str = Field(alias="FACEBOOK_PAGE_ID")

    class Config:
        env_file = str(_ENV_FILE)
        populate_by_name = True


class InstagramCreds(BaseSettings):
    access_token: SecretStr = Field(alias="INSTAGRAM_ACCESS_TOKEN")
    account_id: str = Field(alias="INSTAGRAM_ACCOUNT_ID")

    class Config:
        env_file = str(_ENV_FILE)
        populate_by_name = True


class AnthropicCreds(BaseSettings):
    api_key: SecretStr = Field(alias="ANTHROPIC_API_KEY")

    class Config:
        env_file = str(_ENV_FILE)
        populate_by_name = True


class NotificationCreds(BaseSettings):
    slack_webhook: SecretStr | None = Field(default=None, alias="SLACK_WEBHOOK_URL")
    email_smtp_host: str | None = Field(default=None, alias="EMAIL_SMTP_HOST")
    email_smtp_port: int = Field(default=587, alias="EMAIL_SMTP_PORT")
    email_user: str | None = Field(default=None, alias="EMAIL_USER")
    email_password: SecretStr | None = Field(default=None, alias="EMAIL_PASSWORD")
    ceo_email: str | None = Field(default=None, alias="CEO_EMAIL")

    class Config:
        env_file = str(_ENV_FILE)
        populate_by_name = True


@lru_cache(maxsize=1)
def get_twitter_creds() -> TwitterCreds:
    return TwitterCreds()


@lru_cache(maxsize=1)
def get_facebook_creds() -> FacebookCreds:
    return FacebookCreds()


@lru_cache(maxsize=1)
def get_instagram_creds() -> InstagramCreds:
    return InstagramCreds()


@lru_cache(maxsize=1)
def get_anthropic_creds() -> AnthropicCreds:
    return AnthropicCreds()


@lru_cache(maxsize=1)
def get_notification_creds() -> NotificationCreds:
    return NotificationCreds()
