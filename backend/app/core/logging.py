import logging
import sys

from app.core.config import get_settings


class _SafeFilter(logging.Filter):
    """Redact common secret patterns from log messages."""

    REDACT = (
        "api_key",
        "apikey",
        "secret",
        "password",
        "authorization",
        "bearer ",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage().lower()
            if any(token in msg for token in self.REDACT) and ("=" in msg or ":" in msg):
                # Soften accidental dumps; keep operation context
                record.msg = "[redacted-sensitive-log]"
                record.args = ()
        except Exception:  # noqa: BLE001
            pass
        return True


def setup_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
    )
    handler.addFilter(_SafeFilter())
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        handlers=[handler],
        force=True,
    )
