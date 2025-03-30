from pydantic import BaseModel, Field
from typing import Dict, Any, Literal, Optional

class BaseCommandPayload(BaseModel):
    """Base model for command payloads. Specific commands inherit from this."""
    pass

class LookCommandPayload(BaseCommandPayload):
    target: str = Field(..., description="The ID of the object, character, or area to look at.")

class UseItemCommandPayload(BaseCommandPayload):
    item: str = Field(..., description="The ID of the item to use.")
    target: Optional[str] = Field(None, description="Optional target ID for the item usage (e.g., use key on door).")

# Add other command payload models here as needed...
# class TalkToCommandPayload(BaseCommandPayload):
#     npc_id: str = Field(..., description="The ID of the NPC to talk to.")

class IncomingWebSocketMessage(BaseModel):
    command: str = Field(..., description="The name of the command to execute (e.g., LOOK, USE_ITEM, TALK_TO).")
    payload: Dict[str, Any] = Field(default_factory=dict, description="The parameters for the command.")

# Example structure for outgoing messages from backend to frontend
class OutgoingWebSocketMessage(BaseModel):
    type: str # e.g., 'description', 'dialogue', 'error', 'state_update'
    payload: Dict[str, Any] 