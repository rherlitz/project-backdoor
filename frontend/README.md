# Project: Backdoor - Frontend

This directory contains the Phaser 3 (TypeScript) frontend for the "Project: Backdoor" game.

## Setup

1.  **Ensure Node.js and npm (or yarn) are installed.**
2.  **Navigate to the `frontend` directory:**
    ```bash
    cd frontend
    ```
3.  **Install dependencies:**
    ```bash
    npm install
    # or
    # yarn install
    ```
4.  **Run the development server:**
    ```bash
    npm run dev
    # or
    # yarn dev
    ```
    This will start the Vite development server, typically available at `http://localhost:5173` (check the terminal output for the exact URL).

## Build for Production

```bash
npm run build
# or
# yarn build
```
This command compiles the TypeScript code and bundles the assets into the `dist/` directory, ready for deployment.

## Project Structure

*   `index.html`: The main HTML entry point.
*   `package.json`: Project metadata and dependencies.
*   `tsconfig.json`: TypeScript compiler configuration.
*   `vite.config.js` / `vite.config.ts` (Optional): Vite configuration file (if needed for customization).
*   `src/`: Contains the game source code.
    *   `main.ts`: Phaser game configuration and initialization.
    *   `scenes/`: Directory for different game scenes (e.g., Boot, Preload, Menu, Game levels).
        *   `BootScene.ts`: The first scene loaded, responsible for basic setup and loading initial assets.
    *   `assets/`: (To be created) Directory for game assets (images, audio, data).
    *   `services/`: (Optional) Directory for services like WebSocket communication.
    *   `ui/`: (Optional) Directory for UI component logic (if using DOM overlay). 