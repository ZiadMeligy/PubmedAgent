from fastapi import APIRouter, HTTPException, status, Depends
import uuid
from typing import Dict, Any

from src.api.schemas import SignupRequest, LoginRequest, AuthResponse, UserProfile
from src.auth.security import get_password_hash, verify_password, create_access_token, create_refresh_token
from src.auth.dependencies import get_current_user
from src.storage.conversation_repository import get_conversation_repository

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=AuthResponse)
def signup(request: SignupRequest):
    repo = get_conversation_repository()
    
    if repo.get_user_by_email(request.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if repo.get_user_by_username(request.username):
        raise HTTPException(status_code=400, detail="Username already taken")
        
    user_id = str(uuid.uuid4())
    hashed_pwd = get_password_hash(request.password)
    
    repo.create_user(user_id, request.email, request.username, hashed_pwd)
    
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})
    
    return AuthResponse(user_id=user_id, token=access_token, refresh_token=refresh_token)

@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest):
    repo = get_conversation_repository()
    user = repo.get_user_by_email(request.email)
    
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
        
    access_token = create_access_token(data={"sub": user["id"]})
    refresh_token = create_refresh_token(data={"sub": user["id"]})
    
    return AuthResponse(user_id=user["id"], token=access_token, refresh_token=refresh_token)

@router.get("/me", response_model=UserProfile)
def read_users_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    return UserProfile(id=current_user["id"], email=current_user["email"], username=current_user["username"])
