"""Shared Gmail email normalization and cleaning utilities."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..logging_config import logger
from .timezone_store import get_timezone_store


class EmailTextCleaner:
    """Clean and extract readable text from Gmail API email responses."""

    def __init__(self, max_url_length: int = 60) -> None:
        self.max_url_length = max_url_length
        self.remove_elements = [
            "style",
            "script",
            "meta",
            "link",
            "title",
            "head",
            "noscript",
            "iframe",
            "embed",
            "object",
            "img",
        ]
        self.noise_elements = [
            "footer",
            "header",
            ".footer",
            ".header",
            "[class*=\"footer\"]",
            "[class*=\"header\"]",
            "[class*=\"tracking\"]",
            "[class*=\"pixel\"]",
            "[style*=\"display:none\"]",
            "[style*=\"display: none\"]",
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def clean_email_content(self, message: Dict[str, Any]) -> str:
        """Return cleaned plain-text representation of a Gmail message."""

        html_content = self._extract_html_body(message)
        text_content = self._extract_plain_body(message)

        if html_content:
            return self.clean_html_email(html_content)
        if text_content:
            return self.post_process_text(text_content)
        return ""

    def clean_html_email(self, html_content: str) -> str:
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            for element_type in self.remove_elements:
                for element in soup.find_all(element_type):
                    element.decompose()

            for selector in self.noise_elements:
                try:
                    for element in soup.select(selector):
                        element.decompose()
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug(
                        "Failed to remove element via selector",
                        extra={"selector": selector, "error": str(exc)},
                    )

            for link in soup.find_all("a"):
                href = link.get("href", "")
                text = link.get_text(strip=True)

                if href:
                    display_url = self.truncate_url(href)

                    if text and text != href and not self.is_url_like(text):
                        link.replace_with(f"{text} ({display_url})")
                    elif text and text != href:
                        link.replace_with(f"[Link: {display_url}]")
                    else:
                        link.replace_with(f"[Link: {display_url}]")

            text = soup.get_text(separator="\n", strip=True)
            return self.post_process_text(text)

        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error cleaning HTML email", extra={"error": str(exc)})
            return self.fallback_text_extraction(html_content)

    def truncate_url(self, url: str) -> str:
        if not url or len(url) <= self.max_url_length:
            return url

        url = self.remove_tracking_params(url)
        if len(url) <= self.max_url_length:
            return url
        return f"{url[: self.max_url_length]}..."

    def remove_tracking_params(self, url: str) -> str:
        try:
            from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

            parsed = urlparse(url)
            if not parsed.query:
                return url

            tracking_params = {
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "gclid",
                "fbclid",
                "ref",
                "trk",
            }

            query_params = parse_qs(parsed.query, keep_blank_values=False)
            cleaned_params = {
                key: value
                for key, value in query_params.items()
                if key.lower() not in tracking_params
            }

            new_query = urlencode(cleaned_params, doseq=True)
            new_parsed = parsed._replace(query=new_query)
            return urlunparse(new_parsed)

        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(
                "Failed to strip tracking params",
                extra={"error": str(exc), "url": url},
            )
            return url

    def is_url_like(self, text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()
        if lowered.startswith(("http://", "https://", "www.", "ftp://")):
            return True
        return "." in lowered and " " not in lowered and len(lowered.split(".")) >= 2

    def post_process_text(self, text: str) -> str:
        text = html.unescape(text)
        text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n ", "\n", text)

        noise_patterns = [
            r"View this email in your browser.*?\n",
            r"If you can't see this email.*?\n",
            r"This is a system-generated email.*?\n",
            r"Please do not reply to this email.*?\n",
            r"Unsubscribe.*?preferences.*?\n",
            r"© \d{4}.*?All rights reserved.*?\n",
            r"\[Image:.*?\]",
            r"\[Image\]",
            r"<image>.*?</image>",
            r"\(image\)",
            r"\(Image\)",
            r"Image: .*?\n",
            r"Alt text: .*?\n",
        ]

        for pattern in noise_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        return text

    def fallback_text_extraction(self, html_content: str) -> str:
        stripped = re.sub(r"<[^>]+>", " ", html_content)
        stripped = re.sub(r"\s+", " ", stripped)
        return self.post_process_text(stripped)

    def _extract_html_body(self, message: Dict[str, Any]) -> Optional[str]:
        payload = message.get("payload") or {}
        if isinstance(payload, dict):
            parts = payload.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    if not isinstance(part, dict):
                        continue
                    mime_type = part.get("mimeType") or ""
                    if mime_type.lower() == "text/html":
                        if body := part.get("body"):
                            data = body.get("data")
                            if isinstance(data, str):
                                try:
                                    import base64

                                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                                except Exception:
                                    continue
        return message.get("htmlBody")

    def _extract_plain_body(self, message: Dict[str, Any]) -> Optional[str]:
        payload = message.get("payload") or {}
        if isinstance(payload, dict):
            if body := payload.get("body"):
                data = body.get("data")
                if isinstance(data, str):
                    try:
                        import base64

                        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    except Exception:
                        pass
        return message.get("textBody")

    def extract_attachment_info(self, attachments: Iterable[Any]) -> Tuple[bool, int, List[str]]:
        filenames: List[str] = []
        count = 0
        for item in attachments or []:
            if isinstance(item, dict):
                filename = item.get("filename") or item.get("name")
                if filename:
                    filenames.append(str(filename))
                    count += 1
        return bool(count), count, filenames


@dataclass(frozen=True)
class ProcessedEmail:
    """Normalized Gmail message representation."""

    id: str
    thread_id: Optional[str]
    query: str
    subject: str
    sender: str
    recipient: str
    timestamp: datetime
    label_ids: List[str]
    clean_text: str
    has_attachments: bool
    attachment_count: int
    attachment_filenames: List[str]


# ----------------------------------------------------------------------
# Helpers shared across modules
# ----------------------------------------------------------------------

def convert_to_user_timezone(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    store = get_timezone_store()
    user_tz_name = store.get_timezone("UTC")

    try:
        user_tz = ZoneInfo(user_tz_name)
        return dt.astimezone(user_tz)
    except ZoneInfoNotFoundError:
        logger.warning("Invalid user timezone; defaulting to UTC", extra={"timezone": user_tz_name})
        return dt.astimezone(ZoneInfo("UTC"))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Timezone conversion failed; defaulting to UTC", extra={"error": str(exc)})
        return dt.astimezone(ZoneInfo("UTC"))


def parse_gmail_timestamp(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None

    try:
        normalized = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(normalized)
        return convert_to_user_timezone(dt)
    except ValueError:
        return None


def build_processed_email(
    message: Dict[str, Any],
    *,
    query: str,
    cleaner: Optional[EmailTextCleaner] = None,
) -> Optional[ProcessedEmail]:
    message_id = (message.get("messageId") or message.get("id") or "").strip()
    if not message_id:
        logger.warning("Skipping email with missing message ID")
        return None

    cleaner = cleaner or EmailTextCleaner()

    timestamp = parse_gmail_timestamp(message.get("messageTimestamp"))
    if not timestamp:
        logger.warning("Email missing timestamp; using current time", extra={"message_id": message_id})
        timestamp = convert_to_user_timezone(datetime.now(timezone.utc))

    try:
        clean_text = cleaner.clean_email_content(message)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(
            "Failed to clean email content",
            extra={"message_id": message_id, "error": str(exc)},
        )
        clean_text = "Error processing email content"

    attachments = message.get("attachmentList", [])
    has_attachments, attachment_count, attachment_filenames = cleaner.extract_attachment_info(attachments)

    thread_id = message.get("threadId") or message.get("thread_id")
    subject = message.get("subject") or "No Subject"
    sender = message.get("sender") or "Unknown Sender"
    recipient = message.get("to") or "Unknown Recipient"
    label_ids = list(message.get("labelIds") or [])

    return ProcessedEmail(
        id=message_id,
        thread_id=thread_id,
        query=query,
        subject=subject,
        sender=sender,
        recipient=recipient,
        timestamp=timestamp,
        label_ids=label_ids,
        clean_text=clean_text,
        has_attachments=has_attachments,
        attachment_count=attachment_count,
        attachment_filenames=attachment_filenames,
    )


def build_processed_emails(
    messages: Sequence[Dict[str, Any]],
    *,
    query: str,
    cleaner: Optional[EmailTextCleaner] = None,
) -> List[ProcessedEmail]:
    processed: List[ProcessedEmail] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        email = build_processed_email(message, query=query, cleaner=cleaner)
        if email is not None:
            processed.append(email)
    return processed


def parse_gmail_fetch_response(
    raw_result: Any,
    *,
    query: str,
    cleaner: Optional[EmailTextCleaner] = None,
) -> Tuple[List[ProcessedEmail], Optional[str]]:
    """Convert Composio Gmail fetch payload into processed email models."""

    emails: List[ProcessedEmail] = []
    next_page: Optional[str] = None

    containers = [raw_result] if isinstance(raw_result, dict) else (
        raw_result if isinstance(raw_result, list) else []
    )

    for container in containers:
        if not isinstance(container, dict):
            continue

        messages_block: Optional[Sequence[Any]] = None

        data_section = container.get("data")
        if isinstance(data_section, dict):
            token = data_section.get("nextPageToken")
            if isinstance(token, str) and not next_page:
                next_page = token
            candidate = data_section.get("messages")
            if isinstance(candidate, list):
                messages_block = candidate

        if messages_block is None:
            candidate = container.get("messages")
            if isinstance(candidate, list):
                messages_block = candidate

        if not messages_block:
            continue

        for message in messages_block:
            if not isinstance(message, dict):
                continue
            processed = build_processed_email(message, query=query, cleaner=cleaner)
            if processed:
                emails.append(processed)

    return emails, next_page


__all__ = [
    "EmailTextCleaner",
    "ProcessedEmail",
    "build_processed_email",
    "build_processed_emails",
    "convert_to_user_timezone",
    "parse_gmail_timestamp",
    "parse_gmail_fetch_response",
]
