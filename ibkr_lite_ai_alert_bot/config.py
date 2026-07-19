import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    gemini_api_key: str
    model: str
    watchlist: list[str]
    base_currency: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None


def load_watchlist() -> list[str]:
    watchlist_raw = os.getenv("WATCHLIST", "AAPL,MSFT,SPY,QQQ")
    return [s.strip().upper() for s in watchlist_raw.split(",") if s.strip()]


def get_config() -> Config:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file.")

    return Config(
        gemini_api_key=api_key,
        model=os.getenv("MODEL", "gemma-4-31b-it"),
        watchlist=load_watchlist(),
        base_currency=os.getenv("BASE_CURRENCY", "USD"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
    )
