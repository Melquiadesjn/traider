import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from orb_bot.config.constants import (
    DEFAULT_ENV_FILE,
    DEFAULT_SIM_STARTING_CASH,
    DEFAULT_WATCHLIST,
    PAPER_BASE_URL,
)

ENV_FILE = Path(os.environ.get("ORB_BOT_ENV_FILE", DEFAULT_ENV_FILE))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    broker: Literal["sim", "alpaca"] = "sim"
    watchlist: str = DEFAULT_WATCHLIST
    sim_starting_cash: float = Field(default=DEFAULT_SIM_STARTING_CASH, gt=0)
    alpaca_api_key: SecretStr | None = None
    alpaca_secret_key: SecretStr | None = None
    alpaca_base_url: str = PAPER_BASE_URL
    data_feed: Literal["iex", "sip"] = "iex"
    bot_enabled: bool = True
    notifications_enabled: bool = True
    sec_user_agent: str | None = None

    @field_validator("sec_user_agent")
    @classmethod
    def must_identify_contact(cls, value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        if "@" not in value:
            raise ValueError('SEC_USER_AGENT must be "Name email@example.com" (SEC fair-access policy)')
        return value.strip()

    @field_validator("alpaca_base_url")
    @classmethod
    def must_be_paper(cls, value: str) -> str:
        # v1 is paper-only by design: live trading needs an explicit code change.
        if value.rstrip("/") != PAPER_BASE_URL:
            raise ValueError(f"ALPACA_BASE_URL must be {PAPER_BASE_URL}")
        return value

    @field_validator("watchlist")
    @classmethod
    def must_list_symbols(cls, value: str) -> str:
        if not [s for s in value.split(",") if s.strip()]:
            raise ValueError("WATCHLIST must contain at least one symbol")
        return value

    @model_validator(mode="after")
    def alpaca_needs_keys(self) -> "Settings":
        if self.broker == "alpaca" and not (self.alpaca_api_key and self.alpaca_secret_key):
            raise ValueError("BROKER=alpaca requires ALPACA_API_KEY and ALPACA_SECRET_KEY")
        return self

    @property
    def symbols(self) -> list[str]:
        return [s.strip().upper() for s in self.watchlist.split(",") if s.strip()]

    def alpaca_credentials(self) -> tuple[str, str]:
        if not (self.alpaca_api_key and self.alpaca_secret_key):
            raise ValueError("Alpaca credentials are not configured")
        return self.alpaca_api_key.get_secret_value(), self.alpaca_secret_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
