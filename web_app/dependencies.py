from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from web_app.auth import verify_token
from web_app.google_oauth import WebGoogleOAuth
from web_app.user_store import WebUserStore

_bearer_scheme = HTTPBearer(auto_error=False)

_user_store: Optional[WebUserStore] = None
_assistant_service = None
_google_oauth: Optional[WebGoogleOAuth] = None
_credential_store = None
_health_store = None
_finance_store = None


def get_user_store() -> WebUserStore:
    global _user_store
    if _user_store is None:
        load_dotenv()
        default_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "assistant_memory.sqlite3")
        )
        db_path = os.getenv("ASSISTANT_MEMORY_PATH", default_path)
        _user_store = WebUserStore(db_path)
    return _user_store


def get_assistant_service():
    global _assistant_service
    if _assistant_service is None:
        load_dotenv()
        from assistant_connector.user_credential_store import UserCredentialStore
        from assistant_connector.service import create_assistant_service
        from utils import create_logger

        logger = create_logger.create_logger()
        default_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "assistant_memory.sqlite3")
        )
        memory_path = os.getenv("ASSISTANT_MEMORY_PATH", default_path)
        credential_store = UserCredentialStore(db_path=memory_path)
        _assistant_service = create_assistant_service(
            project_logger=logger,
            user_credential_store=credential_store,
        )
    return _assistant_service


def get_google_oauth() -> Optional[WebGoogleOAuth]:
    global _google_oauth
    if _google_oauth is None:
        load_dotenv()
        callback_url = os.getenv("GOOGLE_OAUTH_CALLBACK_URL", "").strip()
        if not callback_url:
            return None
        from assistant_connector.user_credential_store import UserCredentialStore
        from utils import create_logger

        logger = create_logger.create_logger()
        default_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "assistant_memory.sqlite3")
        )
        memory_path = os.getenv("ASSISTANT_MEMORY_PATH", default_path)
        credential_store = UserCredentialStore(db_path=memory_path)
        _google_oauth = WebGoogleOAuth(
            credential_store=credential_store,
            callback_url=callback_url,
            logger=logger,
        )
    return _google_oauth


def get_credential_store():
    global _credential_store
    if _credential_store is None:
        load_dotenv()
        from assistant_connector.user_credential_store import UserCredentialStore

        default_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "assistant_memory.sqlite3")
        )
        memory_path = os.getenv("ASSISTANT_MEMORY_PATH", default_path)
        _credential_store = UserCredentialStore(db_path=memory_path)
    return _credential_store


def get_health_store():
    global _health_store
    if _health_store is None:
        from assistant_connector.health_store import HealthStore

        default_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "assistant_memory.sqlite3")
        )
        db_path = os.getenv("ASSISTANT_MEMORY_PATH", default_path)
        _health_store = HealthStore(db_path=db_path)
    return _health_store


def get_finance_store():
    global _finance_store
    if _finance_store is None:
        load_dotenv()
        from assistant_connector.finance_store import FinanceStore

        default_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "assistant_memory.sqlite3")
        )
        db_path = os.getenv("ASSISTANT_MEMORY_PATH", default_path)
        encryption_key = os.getenv("CREDENTIAL_ENCRYPTION_KEY", "")
        _finance_store = FinanceStore(db_path=db_path, encryption_key=encryption_key)
    return _finance_store


async def get_current_user_flexible(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict[str, str]:
    """Like get_current_user but also accepts JWT via ?token= query param.

    Used for endpoints that must be fetchable by <img src> tags, which cannot
    send Authorization headers.
    """
    token_str: Optional[str] = None

    if credentials is not None:
        token_str = credentials.credentials
    else:
        token_str = request.query_params.get("token") or None

    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = verify_token(token_str)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    store = get_user_store()
    user = store.get_user_by_id(token_data["user_id"])
    if not user or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict[str, str]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = verify_token(credentials.credentials)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    store = get_user_store()
    user = store.get_user_by_id(token_data["user_id"])
    if not user or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user

