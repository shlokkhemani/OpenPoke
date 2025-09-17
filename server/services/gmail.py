from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from fastapi import status
from fastapi.responses import JSONResponse

from ..config import Settings
from ..logging_config import logger
from ..models import GmailConnectPayload, GmailFetchPayload, GmailStatusPayload
from ..utils import error_response


def _gmail_import_client():
    try:
        from composio import Composio  # type: ignore

        return Composio
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Composio SDK not installed on server. pip install composio") from exc


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


def initiate_connect(payload: GmailConnectPayload, settings: Settings) -> JSONResponse:
    auth_config_id = payload.auth_config_id or settings.composio_gmail_auth_config_id or ""
    if not auth_config_id:
        return error_response(
            "Missing auth_config_id. Set COMPOSIO_GMAIL_AUTH_CONFIG_ID or pass auth_config_id.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user_id = payload.user_id or f"web-{os.getpid()}"
    try:
        Composio = _gmail_import_client()
        client = Composio()
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


def fetch_status(payload: GmailStatusPayload) -> JSONResponse:
    if not payload.connection_request_id and not payload.user_id:
        return error_response(
            "Missing connection_request_id or user_id",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        Composio = _gmail_import_client()
        client = Composio()
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
        Composio = _gmail_import_client()
        client = Composio()
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


def fetch_emails(payload: GmailFetchPayload) -> JSONResponse:
    arguments: Dict[str, Any] = (
        {k: v for k, v in (payload.arguments or {}).items() if v is not None}
        if isinstance(payload.arguments, dict)
        else {}
    )

    arguments.setdefault("max_results", payload.max_results if payload.max_results is not None else 3)
    arguments.setdefault(
        "include_payload",
        payload.include_payload if payload.include_payload is not None else True,
    )
    arguments.setdefault("verbose", payload.verbose if payload.verbose is not None else False)
    arguments.setdefault("user_id", "me")

    try:
        response = execute_gmail_tool(
            "GMAIL_FETCH_EMAILS",
            payload.user_id,
            arguments=arguments,
        )
        return JSONResponse({"ok": True, "response": response})
    except Exception as exc:
        logger.exception("gmail fetch failed", extra={"user_id": payload.user_id})
        return error_response(
            "Failed to fetch emails",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
