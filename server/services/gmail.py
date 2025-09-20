from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import status
from fastapi.responses import JSONResponse

from ..config import Settings, get_settings
from ..logging_config import logger
from ..models import GmailConnectPayload, GmailStatusPayload
from ..utils import error_response


# Persist Gmail user ID to disk for session continuity across restarts
def _save_gmail_user_id(user_id: str) -> None:
    """Save the Gmail user_id to a file for future use."""
    try:
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        user_id_file = data_dir / "gmail_user_id.txt"
        user_id_file.write_text(user_id)
        logger.info(f"Saved Gmail user_id: {user_id}")
    except Exception as e:
        logger.error(f"Failed to save Gmail user_id: {e}")


# Retrieve persisted Gmail user ID from disk storage
def _load_gmail_user_id() -> Optional[str]:
    """Load the saved Gmail user_id."""
    try:
        user_id_file = Path("data") / "gmail_user_id.txt"
        if user_id_file.exists():
            return user_id_file.read_text().strip()
    except Exception as e:
        logger.error(f"Failed to load Gmail user_id: {e}")
    return None


_CLIENT_LOCK = threading.Lock()
_CLIENT: Optional[Any] = None


def _gmail_import_client():
    try:
        from composio import Composio  # type: ignore

        return Composio
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Composio SDK not installed on server. pip install composio") from exc


# Get or create a singleton Composio client instance with thread-safe initialization
def _get_composio_client(settings: Optional[Settings] = None):
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    with _CLIENT_LOCK:
        if _CLIENT is None:
            resolved_settings = settings or get_settings()
            Composio = _gmail_import_client()
            api_key = resolved_settings.composio_api_key
            try:
                _CLIENT = Composio(api_key=api_key) if api_key else Composio()
            except TypeError as exc:
                if api_key:
                    raise RuntimeError(
                        "Installed Composio SDK does not accept the api_key argument; upgrade the SDK or remove COMPOSIO_API_KEY."
                    ) from exc
                _CLIENT = Composio()
    return _CLIENT


def _extract_email(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    for key in ("email", "user_email", "provider_email", "account_email"):
        try:
            val = getattr(obj, key)
            if isinstance(val, str) and "@" in val:
                return val
        except Exception:
            pass
        if isinstance(obj, dict):
            val = obj.get(key)
            if isinstance(val, str) and "@" in val:
                return val
    if isinstance(obj, dict):
        nested_paths = (
            ("profile", "email"),
            ("profile", "emailAddress"),
            ("user", "email"),
            ("data", "email"),
            ("data", "user", "email"),
            ("provider_profile", "email"),
        )
        for path in nested_paths:
            current: Any = obj
            for segment in path:
                if isinstance(current, dict) and segment in current:
                    current = current[segment]
                else:
                    current = None
                    break
            if isinstance(current, str) and "@" in current:
                return current
    return None
# Start Gmail OAuth connection process and return redirect URL
def initiate_connect(payload: GmailConnectPayload, settings: Settings) -> JSONResponse:
    auth_config_id = payload.auth_config_id or settings.composio_gmail_auth_config_id or ""
    if not auth_config_id:
        return error_response(
            "Missing auth_config_id. Set COMPOSIO_GMAIL_AUTH_CONFIG_ID or pass auth_config_id.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user_id = payload.user_id or f"web-{os.getpid()}"
    try:
        client = _get_composio_client(settings)
        req = client.connected_accounts.initiate(user_id=user_id, auth_config_id=auth_config_id)
        data = {
            "ok": True,
            "redirect_url": getattr(req, "redirect_url", None) or getattr(req, "redirectUrl", None),
            "connection_request_id": getattr(req, "id", None),
            "user_id": user_id,
        }
        return JSONResponse(data)
    except Exception as exc:
        logger.exception("gmail connect failed", extra={"user_id": user_id})
        return error_response(
            "Failed to initiate Gmail connect",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# Check Gmail connection status and retrieve user account information
def fetch_status(payload: GmailStatusPayload) -> JSONResponse:
    if not payload.connection_request_id and not payload.user_id:
        return error_response(
            "Missing connection_request_id or user_id",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        client = _get_composio_client()
        account: Any = None
        if payload.connection_request_id:
            try:
                account = client.connected_accounts.wait_for_connection(payload.connection_request_id, timeout=2.0)
            except Exception:
                try:
                    account = client.connected_accounts.get(payload.connection_request_id)
                except Exception:
                    account = None
        if account is None and payload.user_id:
            try:
                items = client.connected_accounts.list(
                    user_ids=[payload.user_id], toolkit_slugs=["GMAIL"], statuses=["ACTIVE"]
                )
                data = getattr(items, "data", None)
                if data is None and isinstance(items, dict):
                    data = items.get("data")
                if data:
                    account = data[0]
            except Exception:
                account = None
        status_value = None
        email = None
        connected = False
        if account is not None:
            status_value = getattr(account, "status", None) or (account.get("status") if isinstance(account, dict) else None)
            normalized = (status_value or "").upper()
            connected = normalized in {"CONNECTED", "SUCCESS", "SUCCESSFUL", "ACTIVE", "COMPLETED"}
            email = _extract_email(account)

            # Save user_id when Gmail is successfully connected
            if connected and payload.user_id:
                _save_gmail_user_id(payload.user_id)

        return JSONResponse(
            {
                "ok": True,
                "connected": bool(connected),
                "status": status_value or "UNKNOWN",
                "email": email,
            }
        )
    except Exception as exc:
        logger.exception(
            "gmail status failed",
            extra={
                "connection_request_id": payload.connection_request_id,
                "user_id": payload.user_id,
            },
        )
        return error_response(
            "Failed to fetch connection status",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


def _normalize_tool_response(result: Any) -> Dict[str, Any]:
    payload_dict: Optional[Dict[str, Any]] = None
    try:
        if hasattr(result, "model_dump"):
            payload_dict = result.model_dump()  # type: ignore[assignment]
        elif hasattr(result, "dict"):
            payload_dict = result.dict()  # type: ignore[assignment]
    except Exception:
        payload_dict = None

    if payload_dict is None:
        try:
            if hasattr(result, "model_dump_json"):
                payload_dict = json.loads(result.model_dump_json())
        except Exception:
            payload_dict = None

    if payload_dict is None:
        if isinstance(result, dict):
            payload_dict = result
        else:
            payload_dict = {"repr": str(result)}

    return payload_dict


# Execute Gmail operations through Composio SDK with error handling
def execute_gmail_tool(
    tool_name: str,
    composio_user_id: str,
    *,
    arguments: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    prepared_arguments: Dict[str, Any] = {}
    if isinstance(arguments, dict):
        for key, value in arguments.items():
            if value is not None:
                prepared_arguments[key] = value

    prepared_arguments.setdefault("user_id", "me")

    try:
        client = _get_composio_client()
        result = client.client.tools.execute(
            tool_name,
            user_id=composio_user_id,
            arguments=prepared_arguments,
        )
        return _normalize_tool_response(result)
    except Exception as exc:
        logger.exception(
            "gmail tool execution failed",
            extra={"tool": tool_name, "user_id": composio_user_id},
        )
        raise RuntimeError(f"{tool_name} invocation failed: {exc}") from exc
