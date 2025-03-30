from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import json
from pydantic import ValidationError

from app.models.commands import IncomingWebSocketMessage, OutgoingWebSocketMessage, LookCommandPayload, TalkToCommandPayload
from app.core.llm_interface import get_llm_provider
# Import game logic handlers here (to be created)
# from app.game_logic.command_handlers import handle_look, handle_talk_to

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New connection: {websocket.client}. Total connections: {len(self.active_connections)}")
        # Optionally send initial state or welcome message
        # await self.send_json(OutgoingWebSocketMessage(type="welcome", payload={"message": "Connected!"}).model_dump(), websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Connection closed: {websocket.client}. Total connections: {len(self.active_connections)}")

    async def send_text(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.warning(f"Failed to send text message to {websocket.client}: {e}")
            self.disconnect(websocket)

    async def send_json(self, data: dict, websocket: WebSocket):
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.warning(f"Failed to send JSON message to {websocket.client}: {e}")
            self.disconnect(websocket)

    async def broadcast_text(self, message: str):
        # Iterate over a copy in case disconnect modifies the list during iteration
        for connection in self.active_connections[:]:
            await self.send_text(message, connection)

    async def broadcast_json(self, data: dict):
        for connection in self.active_connections[:]:
            await self.send_json(data, connection)

manager = ConnectionManager()

async def handle_command(websocket: WebSocket, message_data: IncomingWebSocketMessage):
    """Routes the command to the appropriate handler."""
    command_name = message_data.command.upper()
    payload = message_data.payload
    response: OutgoingWebSocketMessage | None = None

    logger.info(f"Handling command: {command_name} with payload: {payload}")

    try:
        if command_name == "LOOK":
            look_payload = LookCommandPayload(**payload)
            # Basic description for objects for now
            target_id = look_payload.target
            description = f"It looks like a {target_id.replace('object_', '').replace('_', ' ')}."
            if target_id == 'object_terminal':
                 description += " It seems old but functional."
                 
            result = {"description": description}
            response = OutgoingWebSocketMessage(type="description", payload=result)

        elif command_name == "TALK_TO":
            talk_payload = TalkToCommandPayload(**payload)
            npc_id = talk_payload.npc_id

            # --- Basic LLM Dialogue --- 
            llm = get_llm_provider() # Get default OpenAI provider
            if not llm:
                 raise Exception("LLM provider not available.") # Or handle gracefully

            # Very basic prompt - Needs significant improvement!
            # TODO: Fetch NPC persona, player state, history from DB/config
            prompt = f"You are {npc_id}. The player character, Dex, just tried to talk to you. Respond briefly in character."
            if npc_id == "npc_clippy":
                 prompt = f"You are Clippy-9000, a glitchy, overly helpful AI assistant from the 90s. You sometimes use emoticons like :) or :(. Dex just tried to talk to you. Respond briefly and helpfully, maybe with a bit of glitchiness." 
            
            logger.info(f"Sending prompt to LLM for {npc_id}: {prompt}")
            dialogue_line = await llm.generate(prompt=prompt, model="gpt-3.5-turbo", max_tokens=50)
            
            if dialogue_line:
                 logger.info(f"LLM ({npc_id}) response: {dialogue_line}")
                 result = {"speaker": npc_id, "line": dialogue_line}
                 response = OutgoingWebSocketMessage(type="dialogue", payload=result)
            else:
                 logger.warning(f"LLM failed to generate dialogue for {npc_id}.")
                 result = {"speaker": "System", "line": f"({npc_id} doesn't respond.)"}
                 response = OutgoingWebSocketMessage(type="dialogue", payload=result)
            # --------------------------

        # elif command_name == "USE_ITEM":
            # use_payload = UseItemCommandPayload(**payload)
            # result = await handle_use_item(use_payload)
            # response = OutgoingWebSocketMessage(type="action_result", payload=result)

        # Add other command handlers here...

        else:
            logger.warning(f"Unknown command received: {command_name}")
            response = OutgoingWebSocketMessage(type="error", payload={"message": f"Unknown command: {command_name}"})

    except ValidationError as e:
        logger.error(f"Invalid payload for command {command_name}: {e}")
        response = OutgoingWebSocketMessage(type="error", payload={"message": f"Invalid payload for {command_name}: {e.errors()}"})
    except Exception as e:
        logger.error(f"Error handling command {command_name}: {e}", exc_info=True)
        response = OutgoingWebSocketMessage(type="error", payload={"message": f"Internal server error while handling {command_name}"})

    if response:
        await manager.send_json(response.model_dump(), websocket)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Raw message from {websocket.client}: {data}")
            try:
                # Parse the incoming JSON data
                message_json = json.loads(data)
                # Validate the structure
                incoming_message = IncomingWebSocketMessage(**message_json)
                # Handle the command
                await handle_command(websocket, incoming_message)

            except json.JSONDecodeError:
                logger.error(f"Received non-JSON message from {websocket.client}: {data}")
                await manager.send_json(OutgoingWebSocketMessage(type="error", payload={"message": "Invalid message format. Expected JSON."}).model_dump(), websocket)
            except ValidationError as e:
                logger.error(f"Invalid message structure from {websocket.client}: {e}")
                await manager.send_json(OutgoingWebSocketMessage(type="error", payload={"message": f"Invalid message structure: {e.errors()}"}).model_dump(), websocket)
            except Exception as e:
                 logger.error(f"Unexpected error processing message from {websocket.client}: {e}", exc_info=True)
                 await manager.send_json(OutgoingWebSocketMessage(type="error", payload={"message": "Internal server error processing message."}).model_dump(), websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"Client {websocket.client} disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket connection with {websocket.client}: {e}", exc_info=True)
        # Ensure disconnect is called even on unexpected errors
        manager.disconnect(websocket) 