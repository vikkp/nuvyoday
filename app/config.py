"""Application configuration helpers."""

import os
from pathlib import Path


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / "data"
    JT400_JAR = os.getenv("JT400_JAR_PATH", str(BASE_DIR / "lib" / "jt400.jar"))
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATA_DIR / 'nuvyoday.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
