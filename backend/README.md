# Project: Backdoor - Agentic Retro Adventure Game Backend

This directory contains the Python backend for the "Project: Backdoor" game.

## Setup

1.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure environment variables:**
    *   Copy `.env.example` to `.env`.
    *   Fill in your `OPENAI_API_KEY` in the `.env` file.
    *   (Optional) You can override the default SQLite database file path (`backend/game_database.sqlite3`) by setting `DATABASE_URL` in the `.env` file (e.g., `DATABASE_URL=sqlite+aiosqlite:///C:/path/to/your/preferred/game.sqlite3`).
4.  **Run the server:**
    ```bash
    uvicorn main:app --reload
    ```
    The server will automatically create the `game_database.sqlite3` file in the `backend` directory if it doesn't exist.
    The API will be available at `http://localhost:8000`.

## Structure

*   `main.py`: FastAPI application entry point.
*   `requirements.txt`: Python dependencies.
*   `.env.example`: Example environment variable configuration.
*   `.gitignore`: Specifies intentionally untracked files that Git should ignore.
*   `game_database.sqlite3`: (Created on first run) The SQLite database file.
*   `app/`: Main application package.
    *   `api/`: API endpoints (including WebSockets).
    *   `core/`: Core logic, configuration, DB/LLM interaction.
    *   `models/`: Pydantic models for data structures.
    *   `utils/`: Utility functions (including game state management). 