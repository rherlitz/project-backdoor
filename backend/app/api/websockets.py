from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import json
from pydantic import ValidationError
from typing import Optional

from app.models.commands import IncomingWebSocketMessage, OutgoingWebSocketMessage, LookCommandPayload, TalkToCommandPayload, ProcessInputPayload
from app.core.llm_interface import get_llm_provider
from app.utils.game_state import get_current_game_context, get_npc_data, update_npc_memory
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
        # --- Command Routing --- 
        if command_name == "PROCESS_INPUT":
            process_payload = ProcessInputPayload(**payload)
            response = await handle_process_input(process_payload.inputText)
        
        # --- Keep direct commands temporarily for testing/debugging? (Optional) ---
        # elif command_name == "LOOK":
        #     look_payload = LookCommandPayload(**payload)
        #     response = await handle_direct_look(look_payload) # Create helper
        # elif command_name == "TALK_TO":
        #     talk_payload = TalkToCommandPayload(**payload)
        #     response = await handle_direct_talk(talk_payload) # Create helper
        # --- End Optional Direct Commands --- 

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

# --- New Handler for PROCESS_INPUT --- 
async def handle_process_input(inputText: str) -> Optional[OutgoingWebSocketMessage]:
    """Uses a 'Game Agent' LLM to parse intent and dispatch to specific handlers."""
    logger.info(f"Processing player input via LLM: '{inputText}'")
    game_agent_llm = get_llm_provider()
    if not game_agent_llm:
        return OutgoingWebSocketMessage(type="error", payload={"message": "Game Agent LLM not available."}) 

    # --- Get Game Context from DB --- 
    game_context = await get_current_game_context()
    if "error" in game_context:
         logger.error(f"Failed to get game context: {game_context['error']}")
         return OutgoingWebSocketMessage(type="error", payload={"message": "Failed to understand context."}) 
    
    # --- Format Context for Prompt --- 
    player_loc = game_context.get('player_location', 'an unknown place')
    scene_desc = game_context.get('scene_description', "It's hard to make out any details.")
    inventory_list = game_context.get('player_inventory', [])
    inventory_str = "Inventory: " + (", ".join(inventory_list) if inventory_list else "Empty")
    npcs_in_scene = [npc['id'] for npc in game_context.get('scene_npcs', [])]
    objects_in_scene = [obj['id'] for obj in game_context.get('scene_objects', [])]
    npcs_str = "Visible NPCs: " + (", ".join(npcs_in_scene) if npcs_in_scene else "None")
    objects_str = "Visible Objects: " + (", ".join(objects_in_scene) if objects_in_scene else "None")
    player_align = game_context.get('player_alignment', 0)
    
    # Build context string step-by-step
    context_str = f"You (Alignment: {player_align}) are in {player_loc}. "
    context_str += f"{scene_desc} "
    context_str += f"{npcs_str}. "
    context_str += f"{objects_str}. "
    context_str += inventory_str
    
    # Define the expected JSON output structure for the Game Agent
    json_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["LOOK", "TALK_TO", "GO", "GET", "USE", "UNKNOWN"]},
            "target": {"type": "string", "description": "Primary target ID (e.g., npc_clippy, object_terminal, pod_interior) or direction (north, south)."},
            "sentence": {"type": "string", "description": "If the action is TALK_TO, capture the essence of what the player wants to say here."}
        },
        "required": ["action"]
    }

    # Construct the Game Agent prompt
    game_agent_prompt = f"""
You are the Game Agent for a retro text adventure game. Analyze the player's input and determine their intended action based on the current context. Output ONLY a JSON object matching the following schema:
Schema: {json.dumps(json_schema)}

Context: {context_str}
Player Input: "{inputText}"

Determine the action, target, and the sentence if the action is TALK_TO. 
If the intent is unclear or doesn't match a known action, use action UNKNOWN.
If talking, try to capture the essence of what the player wants to say in the 'sentence' property.
Target should be a known ID from the context if applicable. For looking around, use target 'player_loc'.

JSON Output:
"""

    logger.debug(f"Game Agent Prompt:\n{game_agent_prompt}")
    
    try:
        # Use JSON mode if available (check specific provider/model support)
        # For OpenAI 4o-mini (newer versions): response_format={ "type": "json_object" }
        agent_response_str = await game_agent_llm.generate(
            prompt=game_agent_prompt, 
            model="gpt-4o-mini", # Or GPT-4 for better results
            max_tokens=250, 
            temperature=0.2, # Lower temp for more predictable JSON
            response_format={ "type": "json_object" } # Request JSON output
        )

        if not agent_response_str:
             raise ValueError("Game Agent LLM returned empty response.")

        logger.debug(f"Game Agent Raw Response: {agent_response_str}")
        agent_action_data = json.loads(agent_response_str) # Parse the JSON string

        # Validate parsed data (basic checks)
        action = agent_action_data.get('action', 'UNKNOWN').upper()
        target = agent_action_data.get('target')
        sentence = agent_action_data.get('sentence', {})
        logger.info(f"Game Agent Parsed Intent: Action={action}, Target={target}, Sentence={sentence}")

        # --- Dispatch based on parsed action --- 
        if action == "TALK_TO":
            npc_id = target
            if not npc_id or not npc_id.startswith('npc_'):
                 logger.warning(f"TALK_TO action parsed, but target '{target}' is not a valid NPC ID.")
                 return OutgoingWebSocketMessage(type="dialogue", payload={"speaker":"System", "line":"Talk to who exactly?"}) 
            
            # --- Generate NPC Dialogue --- 
            npc_llm = get_llm_provider() 
            if not npc_llm: return OutgoingWebSocketMessage(type="error", payload={"message": "NPC LLM not available."}) 
            npc_data = await get_npc_data(npc_id)
            if not npc_data:
                 logger.error(f"NPC data not found for {npc_id}")
                 return OutgoingWebSocketMessage(type="dialogue", payload={"speaker":"System", "line": f"You can't talk to {npc_id}."})
            npc_persona = npc_data['persona']
            npc_memory = npc_data['memory']
            short_term_history = "\n".join(npc_memory.get('short_term', []))
            medium_term_summary = "\n".join(npc_memory.get('medium_term', []))
            
            # *** Pass original inputText to NPC prompt ***
            npc_prompt = f"""Persona: {npc_persona}
Relevant Facts/Memory:
{medium_term_summary}

Recent Conversation Snippets:
{short_term_history}

Current Situation: Dex (the player, alignment: {game_context.get('player_alignment')}) is in {game_context.get('player_location')} with you.

Dex says to you: "{sentence if sentence else inputText}"  # Use parsed sentence if available, otherwise original input

Your brief, in-character response:
""" 
            
            logger.info(f"NPC ({npc_id}) Prompt:\n{npc_prompt}")
            dialogue_line = await npc_llm.generate(prompt=npc_prompt, model="gpt-4o-mini", max_tokens=150, temperature=0.75)
            
            if dialogue_line:
                 logger.info(f"NPC ({npc_id}) Response: {dialogue_line}")
                 interaction_record = f'Dex said: "{inputText}" / You responded: "{dialogue_line}"'
                 await update_npc_memory(npc_id, interaction_record)
                 return OutgoingWebSocketMessage(type="dialogue", payload={"speaker": npc_id, "line": dialogue_line})
            else:
                 logger.warning(f"NPC LLM failed to generate dialogue for {npc_id}.")
                 return OutgoingWebSocketMessage(type="dialogue", payload={"speaker": "System", "line": f"({npc_id} doesn't respond.)"})
        
        # --- Use World Simulator LLM for Other Actions --- 
        else: 
            # Construct prompt for the World Simulator/Narrator LLM
            # Give it the parsed action/target AND the original text
            result_prompt = f"""You are the Narrator/World Simulator for a retro adventure game.
Context: {context_str}
Player Intent (parsed): Action={action}, Target={target}
Original Player Input: "{inputText}" # Provide original input for detail

Describe the outcome of the player's intended action based on their original input and the context. 
- Use the Original Player Input to understand specifics (e.g., if they said 'look at the bed', describe the bed).
- If the parsed Action is LOOK, describe the most relevant object/area mentioned in the Original Player Input within the context.
- If the parsed Action is GET/USE, describe the attempt based on the Original Player Input.
- If the Action is UNKNOWN, explain why the Original Player Input doesn't make sense.
- Respond concisely (1-3 sentences) in a narrative style.
- Do not actually change the game state, just describe.

Narrator's Description:
"""
            logger.debug(f"World Simulator Result Prompt:\n{result_prompt}")
            
            world_sim_llm = get_llm_provider() 
            if not world_sim_llm:
                 return OutgoingWebSocketMessage(type="error", payload={"message": "World Sim LLM not available."}) 
                 
            narration = await world_sim_llm.generate(
                 prompt=result_prompt, 
                 model="gpt-4o-mini", # Use a capable model
                 max_tokens=100, 
                 temperature=0.6
            )
            
            if not narration:
                 narration = "Nothing seems to happen." # Fallback
            
            # TODO: Actual state updates based on action/target would go here in the future
                 
            return OutgoingWebSocketMessage(type="description", payload={"description": narration})

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response from Game Agent LLM: {agent_response_str}. Error: {e}", exc_info=True)
        return OutgoingWebSocketMessage(type="error", payload={"message": "Internal error processing command (LLM parse)."})
    except Exception as e:
        logger.error(f"Error processing input with Game Agent LLM: {e}", exc_info=True)
        return OutgoingWebSocketMessage(type="error", payload={"message": "Internal error processing command."}) 

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