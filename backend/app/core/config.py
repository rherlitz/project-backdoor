from pydantic_settings import BaseSettings, SettingsConfigDict
import os

# Determine the base directory of the backend project
# This assumes config.py is in backend/app/core/
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB_PATH = os.path.join(BACKEND_DIR, "game_database.sqlite3")

class Settings(BaseSettings):
    OPENAI_API_KEY: str = "YOUR_API_KEY_HERE"
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DEFAULT_DB_PATH}" # Use DATABASE_URL format
    DATABASE_FILE: str = DEFAULT_DB_PATH # Store the raw file path too

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()

# Print the determined database path for verification during startup
print(f"[Config] Database file path: {settings.DATABASE_FILE}") 