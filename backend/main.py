import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from app.api import websockets as ws_router
# Updated imports for SQLite
from app.core.sqlite_client import close_db_connection, get_db_connection
from app.utils.game_state import initialize_player_state_db # No longer needed here
# Corrected import path
from app.core.sqlite_client import initialize_database as initialize_db_schema_and_data # Import the new initializer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize SQLite DB connection, ensure schema, and load static data
    logger.info("Establishing SQLite database connection...")
    # Ensure connection is ready before initializing schema/data
    _ = await get_db_connection() # Call to establish if not already done
    logger.info("Database connection established.")

    logger.info("Initializing database schema and loading static data...")
    await initialize_db_schema_and_data() # Call the consolidated function
    logger.info("Database initialization complete.")

    logger.info("Initializing game state in DB...") # This is now handled by ensure_schema defaults
    await initialize_player_state_db() # Removed separate call
    logger.info("Game state initialization check complete.")

    yield
    # Shutdown: Close SQLite connection
    logger.info("Closing SQLite database connection...")
    await close_db_connection()
    logger.info("Database connection closed.")

app = FastAPI(
    title="Project: Backdoor - Agentic Adventure Game Backend",
    lifespan=lifespan
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to Project: Backdoor Backend!"}

# Include WebSocket router
app.include_router(ws_router.router)

# Placeholder for WebSocket endpoint
# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     while True:
#         data = await websocket.receive_text()
#         await websocket.send_text(f"Message text was: {data}")

if __name__ == "__main__":
    # Note: Uvicorn workers might interfere with singletons like the ConnectionManager
    # For development, running with --reload (1 worker) is fine.
    # For production, consider alternative state sharing for ConnectionManager if using multiple workers.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) # Use string for reload 