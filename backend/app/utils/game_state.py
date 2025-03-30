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

# --- Data Fetching Functions --- 

async def get_scene_data(scene_id: str) -> Optional[dict]:
    """Fetches scene description and details."""
    db = await get_db_connection()
    try:
        async with db.cursor() as cursor:
            await cursor.execute("SELECT description, details_json FROM scenes WHERE scene_id = ?", (scene_id,))
            row = await cursor.fetchone()
            if row:
                return {
                    "description": row["description"],
                    "details": json.loads(row["details_json"])
                }
            return None
    except Exception as e:
        logger.error(f"Failed to get scene data for {scene_id}: {e}", exc_info=True)
        return None

async def get_npc_data(npc_id: str) -> Optional[dict]:
    """Fetches NPC persona, state, and memory."""
    db = await get_db_connection()
    try:
        async with db.cursor() as cursor:
            await cursor.execute("SELECT persona, state_json, memory_json FROM npcs WHERE npc_id = ?", (npc_id,))
            row = await cursor.fetchone()
            if row:
                return {
                    "persona": row["persona"],
                    "state": json.loads(row["state_json"]),
                    "memory": json.loads(row["memory_json"])
                }
            return None
    except Exception as e:
        logger.error(f"Failed to get NPC data for {npc_id}: {e}", exc_info=True)
        return None

async def get_object_data(object_id: str) -> Optional[dict]:
    """Fetches object description and state."""
    db = await get_db_connection()
    try:
        async with db.cursor() as cursor:
            await cursor.execute("SELECT description, state_json FROM objects WHERE object_id = ?", (object_id,))
            row = await cursor.fetchone()
            if row:
                return {
                    "description": row["description"],
                    "state": json.loads(row["state_json"])
                }
            return None
    except Exception as e:
        logger.error(f"Failed to get object data for {object_id}: {e}", exc_info=True)
        return None

async def update_npc_memory(npc_id: str, interaction: str, summary: Optional[str] = None):
    """Updates NPC short-term and optionally medium-term memory."""
    db = await get_db_connection()
    try:
        async with db.cursor() as cursor:
            # Fetch current memory
            await cursor.execute("SELECT memory_json FROM npcs WHERE npc_id = ?", (npc_id,))
            row = await cursor.fetchone()
            if not row:
                 logger.error(f"NPC {npc_id} not found for memory update.")
                 return
            
            memory = json.loads(row["memory_json"])
            # Add to short term (capped list)
            memory["short_term"] = ([interaction] + memory.get("short_term", []))[:10] # Prepend and cap at 10
            # Add summary to medium term if provided
            if summary:
                memory["medium_term"] = memory.get("medium_term", []) + [summary]
            
            # Update memory in DB
            await cursor.execute("UPDATE npcs SET memory_json = ? WHERE npc_id = ?", (json.dumps(memory), npc_id))
            await db.commit()
            logger.debug(f"Updated memory for {npc_id}")
            
    except Exception as e:
        logger.error(f"Failed to update memory for {npc_id}: {e}", exc_info=True)
        await db.rollback()

# --- Context Gathering Function --- 
async def get_current_game_context() -> dict:
    """Gathers relevant context for the Game Agent LLM."""
    player_state = await get_player_state_db()
    if not player_state:
        return {"error": "Player state not found"}

    scene_data = await get_scene_data(player_state.location)
    if not scene_data:
        return {"error": f"Scene data not found for {player_state.location}"}

    context = {
        "player_location": player_state.location,
        "player_inventory": player_state.inventory,
        "player_alignment": player_state.flags.alignment_score,
        "scene_description": scene_data["description"],
        "scene_npcs": [],
        "scene_objects": []
    }

    # Fetch details for NPCs in the scene
    for npc_id in scene_data["details"].get("npcs", []):
        npc_data = await get_npc_data(npc_id)
        if npc_data:
            context["scene_npcs"].append({
                "id": npc_id,
                # Include key state aspects for context, not full persona/memory here
                "state": npc_data["state"]
            })

    # Fetch details for objects in the scene
    for object_id in scene_data["details"].get("objects", []):
        # Exclude items already in player inventory from scene object list
        if object_id in player_state.inventory: continue 
        obj_data = await get_object_data(object_id)
        if obj_data:
            context["scene_objects"].append({
                "id": object_id,
                "description": obj_data["description"],
                "state": obj_data["state"]
            })
            
    return context

# --- TODO: Add functions for NPC state, object state, etc. --- 