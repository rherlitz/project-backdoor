import aiosqlite
import logging
from .config import settings
import json

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
            # Player State Table (Singleton)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    location TEXT NOT NULL,
                    inventory TEXT NOT NULL DEFAULT '[]', 
                    flags TEXT NOT NULL DEFAULT '{}'
                );
            """ )

            # Scenes Table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS scenes (
                    scene_id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}' -- { "npcs": [], "objects": [] }
                );
            """)

            # NPCs Table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS npcs (
                    npc_id TEXT PRIMARY KEY,
                    persona TEXT NOT NULL,
                    current_scene_id TEXT,
                    state_json TEXT NOT NULL DEFAULT '{}',
                    memory_json TEXT NOT NULL DEFAULT '{}' -- { "short_term": [], "medium_term": [] }
                );
            """)

            # Objects Table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS objects (
                    object_id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    scene_id TEXT,
                    state_json TEXT NOT NULL DEFAULT '{}'
                );
            """)
            
            await db.commit()
        logger.info("Database schema initialized successfully.")
        
        # --- Populate Initial Data --- 
        # (This should ideally be idempotent or checked)
        await populate_initial_game_data()
        
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}", exc_info=True)
        await db.rollback() # Rollback changes on error
        raise 

# --- New Function to Populate Initial Data --- 
async def populate_initial_game_data():
    """Populates the database with initial scene, NPC, and object data if tables are empty."""
    db = await get_db_connection()
    try:
        async with db.cursor() as cursor:
            # Check if data might already exist (e.g., check scenes)
            await cursor.execute("SELECT COUNT(*) FROM scenes")
            count = await cursor.fetchone()
            if count[0] > 0:
                 logger.info("Initial game data seems to exist. Skipping population.")
                 return

            logger.info("Populating initial game data...")

            # -- Scenes --
            await cursor.execute("INSERT OR IGNORE INTO scenes (scene_id, description, details_json) VALUES (?, ?, ?)", 
                               ("scene_pod_interior", 
                                "A cramped, messy living pod. Old tech, instant ramen cups, and a faint smell of ozone.", 
                                json.dumps({"npcs": ["npc_clippy"], "objects": ["object_terminal", "item_laptop_old", "item_trophy_hackathon", "item_ramen_cup_empty"]})))
            # Add scene_welfare_office, scene_printshop etc. later

            # -- NPCs --
            await cursor.execute("INSERT OR IGNORE INTO npcs (npc_id, persona, current_scene_id, state_json, memory_json) VALUES (?, ?, ?, ?, ?)",
                               ("npc_clippy", 
                                "A glitchy, overly helpful AI assistant resembling a paperclip from the late 90s/early 2000s. Expresses emotion via emoticons/ASCII art. Split loyalties between Dex and core programming. Wants to understand 'humanity'. Knows basic hacking, NeuroStream public net (limited), outdated software trivia.",
                                "scene_pod_interior",
                                json.dumps({"loyalty_dex": 0, "current_mode": "helpful"}),
                                json.dumps({"short_term": [], "medium_term": []})))
            # Add npc_cassie, npc_omnius etc. later

            # -- Objects -- 
            await cursor.execute("INSERT OR IGNORE INTO objects (object_id, description, scene_id, state_json) VALUES (?, ?, ?, ?)",
                               ("object_terminal", 
                                "An old, bulky computer terminal. The screen is dark.", 
                                "scene_pod_interior", 
                                json.dumps({"is_powered": False})))
            await cursor.execute("INSERT OR IGNORE INTO objects (object_id, description, scene_id) VALUES (?, ?, ?)",
                               ("item_laptop_old", "Dex's beat-up laptop from the 2020s. Covered in stickers.", "scene_pod_interior")) # Inventory items also listed as objects initially
            await cursor.execute("INSERT OR IGNORE INTO objects (object_id, description, scene_id) VALUES (?, ?, ?)",
                               ("item_trophy_hackathon", "A dusty plastic trophy from a forgotten hackathon.", "scene_pod_interior"))
            await cursor.execute("INSERT OR IGNORE INTO objects (object_id, description, scene_id) VALUES (?, ?, ?)",
                               ("item_ramen_cup_empty", "An empty instant ramen cup. Classic.", "scene_pod_interior"))
            
            await db.commit()
            logger.info("Initial game data populated.")

    except Exception as e:
        logger.error(f"Failed to populate initial game data: {e}", exc_info=True)
        await db.rollback() # Rollback changes on error
        # Decide if this error should prevent startup 