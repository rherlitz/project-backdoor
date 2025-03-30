import logging
import json
import aiosqlite
from typing import Optional

from app.models.player import PlayerState, PlayerFlags
from app.core.sqlite_client import get_db_connection

logger = logging.getLogger(__name__)

async def initialize_player_state_db(force_reset: bool = False):
    """Initializes the default player state in the SQLite DB if it doesn't exist or if force_reset is True."""
    db = await get_db_connection()
    try:
        async with db.cursor() as cursor:
            # Check if state already exists (row with id=1)
            await cursor.execute("SELECT 1 FROM player_state WHERE id = 1")
            exists = await cursor.fetchone()

            if exists and not force_reset:
                logger.info("Player state already exists in DB. Skipping initialization.")
                return

            if force_reset:
                logger.warning("Forcing reset of player state in DB.")
                await cursor.execute("DELETE FROM player_state WHERE id = 1")

            # Get default state from Pydantic model
            default_state = PlayerState()
            inventory_json = json.dumps(default_state.inventory)
            flags_json = default_state.flags.model_dump_json()

            # Insert or replace the single row for player state
            await cursor.execute("""
                INSERT OR REPLACE INTO player_state (id, location, inventory, flags)
                VALUES (1, ?, ?, ?)
            """, (default_state.location, inventory_json, flags_json))

            await db.commit()
            logger.info("Player state initialized in DB.")

    except Exception as e:
        logger.error(f"Failed to initialize player state in DB: {e}", exc_info=True)
        await db.rollback()
        raise # Reraise to indicate failure

async def get_player_state_db() -> Optional[PlayerState]:
    """Retrieves the current player state from the SQLite DB."""
    db = await get_db_connection()
    try:
        async with db.cursor() as cursor:
            await cursor.execute("SELECT location, inventory, flags FROM player_state WHERE id = 1")
            row = await cursor.fetchone()

            if not row:
                logger.error("Player state not found in database!")
                return None

            # Parse JSON fields
            inventory_list = json.loads(row["inventory"])
            # Use model_validate for robust parsing back into Pydantic model
            flags_model = PlayerFlags.model_validate_json(row["flags"])

            return PlayerState(
                location=row["location"],
                inventory=inventory_list,
                flags=flags_model
            )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from player_state in DB: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve player state from DB: {e}", exc_info=True)
        return None

async def update_player_state_db(new_state: PlayerState):
    """Updates the entire player state in the SQLite DB."""
    db = await get_db_connection()
    try:
        inventory_json = json.dumps(new_state.inventory)
        flags_json = new_state.flags.model_dump_json()

        async with db.cursor() as cursor:
            await cursor.execute("""
                UPDATE player_state
                SET location = ?, inventory = ?, flags = ?
                WHERE id = 1
            """, (new_state.location, inventory_json, flags_json))

            if cursor.rowcount == 0:
                 logger.error("Attempted to update player state, but no row found (id=1).")
                 # Optionally try to insert if it really should exist
                 raise ValueError("Player state row not found for update.")

            await db.commit()
            logger.debug(f"Player state updated in DB: {new_state}")

    except Exception as e:
        logger.error(f"Failed to update player state in DB: {e}", exc_info=True)
        await db.rollback()
        raise # Reraise to indicate failure

# --- TODO: Add functions for NPC state, object state, etc. --- 