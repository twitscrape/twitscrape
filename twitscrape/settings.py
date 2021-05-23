import logging
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    log_level: str = "ERROR"
    tor_log_level: str = Field(
        "CRITICAL",
        description="Log verbosity for underlying tor library, very verbose at info or higher",
    )
    tweet_count: int = Field(5, description="Default number of tweets to return")
    polling_seconds: int = Field(
        10 * 60, description="Default number of seconds between checking for new tweets"
    )
    batch_count: int = Field(
        20, description="Number of responses to query for when paginating"
    )
    host: str = Field("0.0.0.0", description="Host to bind to for web server")
    port: int = Field(8000, description="Port to bind to for web server")


settings = Settings()
logging.basicConfig(level=settings.tor_log_level)
