import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ShieldRecall"
    DEBUG: bool = False

    # Database
    LOCAL_DB_PATH: str = "secure_recall.db"

    # Encryption key — in production, derive this via Windows Hello / DPAPI.
    # Set via env var SHIELD_RECALL_KEY or .env file. Must be exactly 32 bytes.
    ENCRYPTION_KEY: str = os.getenv(
        "SHIELD_RECALL_KEY", "ShieldRecall_DefaultKey_32Bytes!!"
    )

    # How often (seconds) the capture worker scans the Recall directory and
    # processes the active window text stream.
    CAPTURE_INTERVAL_SECONDS: int = 5

    # Shannon entropy threshold. Strings above this value are treated as
    # high-entropy secrets (passwords, API keys, tokens).
    # Typical ranges:
    #   < 3.5  →  normal English prose
    #   3.5–4.5 →  borderline (monitor)
    #   > 4.5  →  likely credential / key
    ENTROPY_THRESHOLD: float = 4.0

    # Windows Recall snapshot directory (adjust if Microsoft changes the path).
    RECALL_SNAPSHOT_DIR: str = r"%USERPROFILE%\AppData\Local\CoreAIPlatform\CaptureRegions"

    # FastAPI server binding — loopback only, zero external network surface.
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # How many activity log entries to keep in memory.
    MAX_ACTIVITY_LOG: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
