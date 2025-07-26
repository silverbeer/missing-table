# -*- coding: utf-8 -*-
"""
Authentication and authorization utilities for the sports league backend.
"""
import logging
from typing import Optional, Dict, Any
from functools import wraps
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from supabase import Client
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
security = HTTPBearer()

class AuthManager:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.jwt_secret = os.getenv('SUPABASE_JWT_SECRET')
        
        if not self.jwt_secret:
            raise ValueError(
                "SUPABASE_JWT_SECRET environment variable is required. "
                "Please set it in your .env file."
            )
        
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return user data."""
        try:
            # Decode JWT token
            payload = jwt.decode(
                token, 
                self.jwt_secret, 
                algorithms=['HS256'],
                audience='authenticated'
            )
            
            user_id = payload.get('sub')
            if not user_id:
                return None
                
            # Get user profile with role
            profile_response = self.supabase.table('user_profiles').select('*').eq('id', user_id).execute()
            
            if not profile_response.data or len(profile_response.data) == 0:
                logger.warning(f"No profile found for user {user_id}")
                return None
            
            # If multiple profiles exist, take the first one (should be fixed by cleanup script)
            profile = profile_response.data[0]
            if len(profile_response.data) > 1:
                logger.warning(f"Multiple profiles found for user {user_id}, using first one")
            
            return {
                'user_id': user_id,
                'email': payload.get('email'),
                'role': profile['role'],
                'team_id': profile.get('team_id'),
                'display_name': profile.get('display_name')
            }
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return None
    
    def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
        """FastAPI dependency to get current authenticated user."""
        if not credentials:
            raise HTTPException(status_code=401, detail="Authentication required")
            
        user_data = self.verify_token(credentials.credentials)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
            
        return user_data
    
    def require_role(self, required_roles: list):
        """Decorator to require specific roles."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Get current user from kwargs (injected by FastAPI dependency)
                current_user = None
                for key, value in kwargs.items():
                    if isinstance(value, dict) and 'role' in value:
                        current_user = value
                        break
                
                if not current_user:
                    raise HTTPException(status_code=401, detail="Authentication required")
                
                user_role = current_user.get('role')
                if user_role not in required_roles:
                    raise HTTPException(
                        status_code=403, 
                        detail=f"Access denied. Required roles: {required_roles}"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    def can_manage_team(self, user_data: Dict[str, Any], team_id: int) -> bool:
        """Check if user can manage a specific team."""
        role = user_data.get('role')
        user_team_id = user_data.get('team_id')
        
        # Admins can manage any team
        if role == 'admin':
            return True
            
        # Team managers can only manage their own team
        if role == 'team-manager' and user_team_id == team_id:
            return True
            
        return False
    
    def can_edit_game(self, user_data: Dict[str, Any], home_team_id: int, away_team_id: int) -> bool:
        """Check if user can edit a game between specific teams."""
        role = user_data.get('role')
        user_team_id = user_data.get('team_id')
        
        # Admins can edit any game
        if role == 'admin':
            return True
            
        # Team managers can edit games involving their team
        if role == 'team-manager' and user_team_id in [home_team_id, away_team_id]:
            return True
            
        return False

# Auth dependency functions for FastAPI
def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))) -> Optional[Dict[str, Any]]:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None
    
    # This will be injected by the main app
    from app import auth_manager
    return auth_manager.verify_token(credentials.credentials)

def get_current_user_required(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get current user, raise exception if not authenticated."""
    # This will be injected by the main app
    from app import auth_manager
    return auth_manager.get_current_user(credentials)

def require_admin(current_user: Dict[str, Any] = Depends(get_current_user_required)) -> Dict[str, Any]:
    """Require admin role."""
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

def require_team_manager_or_admin(current_user: Dict[str, Any] = Depends(get_current_user_required)) -> Dict[str, Any]:
    """Require team-manager or admin role."""
    role = current_user.get('role')
    if role not in ['admin', 'team-manager']:
        raise HTTPException(status_code=403, detail="Team manager or admin access required")
    return current_user