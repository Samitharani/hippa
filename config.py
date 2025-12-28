# app/config.py
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY") or "change-me"
ALGORITHM = os.getenv("ALGORITHM") or "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES") or 60)

# AES_KEY as hex string in .env
AES_KEY_HEX = os.getenv("AES_KEY") or "00000000000000000000000000000000"

DB_URL = os.getenv("DATABASE_URL") or "sqlite:///./app.db"

CYBORGDB_URL = os.getenv("CYBORGDB_URL") or "http://localhost:7000"
CYBORGDB_API_KEY = os.getenv("CYBORGDB_API_KEY") or ""
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in ("1", "true", "yes")
