import aiosqlite
import logging
from .config import settings

logger = logging.getLogger(__name__)

# Global variable to hold the connection
_db_connection = None

async def get_db_connection() -> aiosqlite.Connection:
    """Gets the singleton async SQLite database connection."""
    global _db_connection
    if _db_connection is None:
        try:
            # Connect to the database file specified in settings
            _db_connection = await aiosqlite.connect(settings.DATABASE_FILE)
            # Use Row factory for dict-like access to rows
            _db_connection.row_factory = aiosqlite.Row
            logger.info(f"Successfully connected to SQLite database: {settings.DATABASE_FILE}")
        except Exception as e:
            logger.error(f"Failed to connect to SQLite database: {settings.DATABASE_FILE}. Error: {e}", exc_info=True)
            raise # Reraise the exception to prevent app startup if DB connection fails
    return _db_connection

async def close_db_connection():
    """Closes the SQLite database connection."""
    global _db_connection
    if _db_connection:
        try:
            await _db_connection.close()
            _db_connection = None
            logger.info(f"Successfully closed SQLite database connection: {settings.DATABASE_FILE}")
        except Exception as e:
            logger.error(f"Error closing SQLite database connection: {e}", exc_info=True)

async def initialize_database():
    """Initializes the database schema (creates tables if they don't exist)."""
    db = await get_db_connection()
    try:
        async with db.cursor() as cursor:
            # Create player_state table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1), -- Enforce singleton row
                    location TEXT NOT NULL,
                    inventory TEXT NOT NULL, -- Store as JSON list
                    flags TEXT NOT NULL -- Store as JSON dict
                );
            """)
            # --- Add other tables here --- 
            # Example: NPC state table
            # await cursor.execute("""
            #     CREATE TABLE IF NOT EXISTS npc_state (
            #         npc_id TEXT PRIMARY KEY,
            #         location TEXT,
            #         data TEXT -- Store other state (trust, mode, etc.) as JSON
            #     );
            # """)
            await db.commit()
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}", exc_info=True)
        await db.rollback() # Rollback changes on error
        raise 