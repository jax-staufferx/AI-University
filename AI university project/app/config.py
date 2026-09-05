from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DIGESTS_DIR = DATA_DIR / "digests"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    anthropic_api_key: str = ""
    research_call_soft_cap: int = 40
    database_path: Path = DATA_DIR / "learning_agent.db"

    # Key used to HMAC-sign session cookies — no server-side session store needed.
    session_secret: str = ""

    research_model: str = "claude-opus-5"
    grading_model: str = "claude-opus-5"


settings = Settings()

DATA_DIR.mkdir(parents=True, exist_ok=True)
DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
