from pydantic import BaseModel, Field
from typing import List, Dict, Any

class PlayerFlags(BaseModel):
    is_bitter: bool = True
    is_evicted: bool = False
    knows_project_backdoor: bool = False
    alignment_score: int = Field(default=0, ge=-100, le=100) # Alignment: -100=Pure Evil, +100=Pure Good

class PlayerState(BaseModel):
    location: str = "pod_interior"
    inventory: List[str] = Field(default_factory=lambda: ["item_laptop_old", "item_trophy_hackathon", "item_ramen_cup_empty"])
    flags: PlayerFlags = Field(default_factory=PlayerFlags)
    # Placeholder for other potential player data like skills, health, etc.
    # skills: List[str] = Field(default_factory=list) 