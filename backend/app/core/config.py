from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    google_places_api_key: str = Field(default="", alias="GOOGLE_PLACES_API_KEY")
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/leadflow",
        alias="DATABASE_URL",
    )
    frontend_url: str = Field(default="http://localhost:5173", alias="FRONTEND_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    # development | test | production
    app_env: str = Field(default="development", alias="APP_ENV")
    secret_key: str = Field(default="", alias="SECRET_KEY")
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")  # comma-separated; empty = frontend_url + localhost
    # Opt-in ONLY for local/offline QA. Default false = production uses live Google Places.
    google_places_mock: bool = Field(default=False, alias="GOOGLE_PLACES_MOCK")
    places_page_size: int = 20
    places_max_pages: int = 10
    places_request_delay_seconds: float = 0.35

    # Phase 11 — API rate limits (requests per window)
    api_rate_limit_enabled: bool = Field(default=True, alias="API_RATE_LIMIT_ENABLED")
    api_rate_limit_per_minute: int = Field(default=120, alias="API_RATE_LIMIT_PER_MINUTE")
    api_rate_limit_sensitive_per_minute: int = Field(default=30, alias="API_RATE_LIMIT_SENSITIVE_PER_MINUTE")
    public_booking_rate_limit_per_minute: int = Field(default=20, alias="PUBLIC_BOOKING_RATE_LIMIT_PER_MINUTE")
    job_queue_backend: str = Field(default="local", alias="JOB_QUEUE_BACKEND")  # local | redis (future)
    job_default_max_attempts: int = Field(default=3, alias="JOB_DEFAULT_MAX_ATTEMPTS")
    fail_fast_on_invalid_config: bool = Field(default=True, alias="FAIL_FAST_ON_INVALID_CONFIG")

    # Phase 12 — authentication
    jwt_access_ttl_minutes: int = Field(default=30, alias="JWT_ACCESS_TTL_MINUTES")
    jwt_refresh_ttl_days: int = Field(default=14, alias="JWT_REFRESH_TTL_DAYS")
    password_reset_ttl_minutes: int = Field(default=60, alias="PASSWORD_RESET_TTL_MINUTES")
    invitation_ttl_days: int = Field(default=7, alias="INVITATION_TTL_DAYS")
    auth_max_login_attempts_per_minute: int = Field(default=10, alias="AUTH_MAX_LOGIN_ATTEMPTS_PER_MINUTE")
    # When true (tests only), private APIs still require tokens unless overridden in fixtures
    auth_required: bool = Field(default=True, alias="AUTH_REQUIRED")

    # Phase 4 — email verification (never expose keys to frontend)
    email_verification_provider: str = Field(default="", alias="EMAIL_VERIFICATION_PROVIDER")
    email_verification_api_key: str = Field(default="", alias="EMAIL_VERIFICATION_API_KEY")
    email_verification_api_url: str = Field(default="", alias="EMAIL_VERIFICATION_API_URL")
    verification_cache_days: int = Field(default=30, alias="VERIFICATION_CACHE_DAYS")
    verification_request_delay_seconds: float = Field(default=0.25, alias="VERIFICATION_REQUEST_DELAY_SECONDS")
    verification_max_batch: int = Field(default=100, alias="VERIFICATION_MAX_BATCH")
    verification_timeout_seconds: float = Field(default=15.0, alias="VERIFICATION_TIMEOUT_SECONDS")

    # Phase 5 — AI qualification (never expose keys to frontend)
    # Provider: empty/none = unconfigured | mock = offline QA only | openai = OpenAI API
    ai_provider: str = Field(default="", alias="AI_PROVIDER")
    ai_api_key: str = Field(default="", alias="AI_API_KEY")
    ai_model: str = Field(default="gpt-4o-mini", alias="AI_MODEL")
    ai_api_url: str = Field(default="", alias="AI_API_URL")
    ai_prompt_version: str = Field(default="v1.0", alias="AI_PROMPT_VERSION")
    ai_max_tokens: int = Field(default=1200, alias="AI_MAX_TOKENS")
    ai_timeout_seconds: float = Field(default=45.0, alias="AI_TIMEOUT_SECONDS")
    ai_request_delay_seconds: float = Field(default=0.35, alias="AI_REQUEST_DELAY_SECONDS")
    ai_max_batch: int = Field(default=50, alias="AI_MAX_BATCH")
    ai_max_retries: int = Field(default=2, alias="AI_MAX_RETRIES")

    # Phase 6 — outreach draft generation (never sends email)
    outreach_prompt_version: str = Field(default="v1.0", alias="OUTREACH_PROMPT_VERSION")
    outreach_max_tokens: int = Field(default=900, alias="OUTREACH_MAX_TOKENS")
    outreach_max_batch: int = Field(default=50, alias="OUTREACH_MAX_BATCH")
    outreach_request_delay_seconds: float = Field(default=0.35, alias="OUTREACH_REQUEST_DELAY_SECONDS")
    outreach_allow_unknown_verification: bool = Field(
        default=False, alias="OUTREACH_ALLOW_UNKNOWN_VERIFICATION"
    )
    agency_name: str = Field(default="LeadFlow AI", alias="AGENCY_NAME")

    # Phase 7 — real email sending (defaults prevent accidental sends)
    email_sending_provider: str = Field(default="", alias="EMAIL_SENDING_PROVIDER")
    email_sending_api_key: str = Field(default="", alias="EMAIL_SENDING_API_KEY")
    email_sending_api_url: str = Field(default="", alias="EMAIL_SENDING_API_URL")
    email_webhook_secret: str = Field(default="", alias="EMAIL_WEBHOOK_SECRET")
    sender_email: str = Field(default="", alias="SENDER_EMAIL")
    sender_name: str = Field(default="LeadFlow AI", alias="SENDER_NAME")
    email_send_enabled: bool = Field(default=False, alias="EMAIL_SEND_ENABLED")
    email_test_mode: bool = Field(default=True, alias="EMAIL_TEST_MODE")
    max_emails_per_hour: int = Field(default=20, alias="MAX_EMAILS_PER_HOUR")
    max_emails_per_day: int = Field(default=100, alias="MAX_EMAILS_PER_DAY")
    email_send_max_retries: int = Field(default=2, alias="EMAIL_SEND_MAX_RETRIES")
    email_send_timeout_seconds: float = Field(default=20.0, alias="EMAIL_SEND_TIMEOUT_SECONDS")
    public_app_url: str = Field(default="http://localhost:5173", alias="PUBLIC_APP_URL")

    # Phase 8 — campaign send windows (defaults; per-campaign can override)
    campaign_send_start_hour: int = Field(default=9, alias="CAMPAIGN_SEND_START_HOUR")
    campaign_send_end_hour: int = Field(default=17, alias="CAMPAIGN_SEND_END_HOUR")
    campaign_default_timezone: str = Field(default="UTC", alias="CAMPAIGN_DEFAULT_TIMEZONE")
    campaign_scheduler_batch_size: int = Field(default=25, alias="CAMPAIGN_SCHEDULER_BATCH_SIZE")
    campaign_lock_ttl_seconds: int = Field(default=120, alias="CAMPAIGN_LOCK_TTL_SECONDS")

    # Phase 9 — reply intelligence (classification/suggestions; never auto-send)
    reply_prompt_version: str = Field(default="v1.0", alias="REPLY_PROMPT_VERSION")
    reply_max_tokens: int = Field(default=800, alias="REPLY_MAX_TOKENS")
    reply_auto_classify: bool = Field(default=True, alias="REPLY_AUTO_CLASSIFY")
    reply_auto_suggest: bool = Field(default=True, alias="REPLY_AUTO_SUGGEST")
    # Inbound webhooks require EMAIL_WEBHOOK_SECRET when send enabled; mock inbound allowed in test mode
    reply_inbound_enabled: bool = Field(default=False, alias="REPLY_INBOUND_ENABLED")

    # Phase 10 — meetings / calendar (defaults: unconfigured, no live calendar)
    calendar_provider: str = Field(default="", alias="CALENDAR_PROVIDER")
    calendar_api_key: str = Field(default="", alias="CALENDAR_API_KEY")
    meeting_default_timezone: str = Field(default="UTC", alias="MEETING_DEFAULT_TIMEZONE")
    meeting_booking_token_ttl_days: int = Field(default=14, alias="MEETING_BOOKING_TOKEN_TTL_DAYS")
    meeting_slot_interval_minutes: int = Field(default=30, alias="MEETING_SLOT_INTERVAL_MINUTES")
    meeting_send_confirmations: bool = Field(default=True, alias="MEETING_SEND_CONFIRMATIONS")

    # Phase 13 — SaaS billing (default: unconfigured; free plan works without Stripe)
    billing_provider: str = Field(default="unconfigured", alias="BILLING_PROVIDER")
    billing_test_mode: bool = Field(default=True, alias="BILLING_TEST_MODE")
    billing_grace_period_days: int = Field(default=3, alias="BILLING_GRACE_PERIOD_DAYS")
    stripe_secret_key: str = Field(default="", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field(default="", alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_starter: str = Field(default="", alias="STRIPE_PRICE_STARTER")
    stripe_price_growth: str = Field(default="", alias="STRIPE_PRICE_GROWTH")
    stripe_price_agency: str = Field(default="", alias="STRIPE_PRICE_AGENCY")
    # Configurable display prices (None/empty annual uses monthly*10 heuristic only when monthly set)
    plan_currency: str = Field(default="USD", alias="PLAN_CURRENCY")
    plan_price_starter_monthly: float | None = Field(default=29.0, alias="PLAN_PRICE_STARTER_MONTHLY")
    plan_price_starter_annual: float | None = Field(default=290.0, alias="PLAN_PRICE_STARTER_ANNUAL")
    plan_price_growth_monthly: float | None = Field(default=99.0, alias="PLAN_PRICE_GROWTH_MONTHLY")
    plan_price_growth_annual: float | None = Field(default=990.0, alias="PLAN_PRICE_GROWTH_ANNUAL")
    plan_price_agency_monthly: float | None = Field(default=299.0, alias="PLAN_PRICE_AGENCY_MONTHLY")
    plan_price_agency_annual: float | None = Field(default=2990.0, alias="PLAN_PRICE_AGENCY_ANNUAL")

    provider_test_email: str = Field(default="", alias="PROVIDER_TEST_EMAIL")
    provider_test_rate_limit_per_minute: int = Field(default=5, alias="PROVIDER_TEST_RATE_LIMIT_PER_MINUTE")
    calendar_test_calendar_id: str = Field(default="", alias="CALENDAR_TEST_CALENDAR_ID")

    def require_places_key(self) -> str:
        if self.google_places_mock:
            if self.app_env == "production":
                raise RuntimeError("GOOGLE_PLACES_MOCK cannot be enabled in production")
            return "offline-mock-key"
        key = (self.google_places_api_key or "").strip()
        if not key:
            raise RuntimeError(
                "GOOGLE_PLACES_API_KEY is not configured. "
                "Set it in backend/.env before running lead generation, "
                "or set GOOGLE_PLACES_MOCK=true for offline QA only."
            )
        return key

    def cors_origin_list(self) -> list[str]:
        extras = [o.strip() for o in (self.cors_origins or "").split(",") if o.strip()]
        base = [self.frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"]
        return list(dict.fromkeys([*base, *extras]))

    def is_production(self) -> bool:
        return (self.app_env or "").strip().lower() == "production"


class ProductionConfigError(RuntimeError):
    pass


def validate_settings(settings: Settings | None = None) -> list[str]:
    """Return list of config problems. Raises in production when fail-fast enabled."""
    settings = settings or get_settings()
    problems: list[str] = []
    env = (settings.app_env or "development").strip().lower()

    if not (settings.database_url or "").strip():
        problems.append("DATABASE_URL is required")

    if env == "production":
        if (
            not (settings.secret_key or "").strip()
            or settings.secret_key in {"changeme", "secret", "leadflow-dev-only-secret-change-me"}
            or len(settings.secret_key.strip()) < 32
        ):
            problems.append("SECRET_KEY must be set to a strong value (32+ chars) in production")
        if settings.google_places_mock:
            problems.append("GOOGLE_PLACES_MOCK must be false in production")
        if (settings.ai_provider or "").strip().lower() == "mock":
            problems.append("AI_PROVIDER=mock is not allowed in production")
        if (settings.email_verification_provider or "").strip().lower() == "mock":
            problems.append("EMAIL_VERIFICATION_PROVIDER=mock is not allowed in production")
        if (settings.calendar_provider or "").strip().lower() == "mock":
            problems.append("CALENDAR_PROVIDER=mock is not allowed in production")
        billing_name = (settings.billing_provider or "").strip().lower()
        if billing_name == "mock":
            problems.append("BILLING_PROVIDER=mock is not allowed in production")
        if billing_name == "stripe" and not (settings.stripe_secret_key or "").strip():
            problems.append("STRIPE_SECRET_KEY is required when BILLING_PROVIDER=stripe")
        if settings.email_send_enabled and settings.email_test_mode:
            problems.append("EMAIL_SEND_ENABLED=true with EMAIL_TEST_MODE=true is inconsistent for production live sends")
        if settings.email_send_enabled and not (settings.sender_email or "").strip():
            problems.append("SENDER_EMAIL is required when EMAIL_SEND_ENABLED=true")
        if settings.email_send_enabled and not (settings.email_webhook_secret or "").strip():
            problems.append("EMAIL_WEBHOOK_SECRET is recommended/required when EMAIL_SEND_ENABLED=true")
        if settings.reply_inbound_enabled and not (settings.email_webhook_secret or "").strip():
            problems.append("EMAIL_WEBHOOK_SECRET is required when REPLY_INBOUND_ENABLED=true")

    if settings.fail_fast_on_invalid_config and env == "production" and problems:
        raise ProductionConfigError("; ".join(problems))
    return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
