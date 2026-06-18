from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any

from src.api.schemas import SettingsSchema
from src.auth.dependencies import get_current_user
from src.storage.conversation_repository import get_conversation_repository

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("", response_model=SettingsSchema)
def get_settings(current_user: Dict[str, Any] = Depends(get_current_user)):
    repo = get_conversation_repository()
    prefs = repo.get_preferences(current_user["id"])
    return SettingsSchema(alpha=prefs["alpha"], beta=prefs["beta"], gamma=prefs["gamma"])

@router.put("", response_model=SettingsSchema)
def update_settings(settings: SettingsSchema, current_user: Dict[str, Any] = Depends(get_current_user)):
    # Validate sum is approx 1.0
    total = settings.alpha + settings.beta + settings.gamma
    if abs(total - 1.0) > 0.01:
        # Normalize
        settings.alpha /= total
        settings.beta /= total
        settings.gamma /= total
        
    repo = get_conversation_repository()
    repo.update_preferences(current_user["id"], settings.alpha, settings.beta, settings.gamma)
    
    return settings
