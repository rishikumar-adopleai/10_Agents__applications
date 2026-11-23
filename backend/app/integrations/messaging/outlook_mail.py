"""Microsoft Outlook / Graph API Email Outreach Adapter."""

import asyncio
import uuid
from typing import Any, Dict, List, Optional

import httpx

from backend.app.core.config import is_configured_value, settings
from backend.app.core.logging import logger
from backend.app.integrations.base import BaseIntegrationAdapter, IntegrationHealth


class OutlookMailAdapter(BaseIntegrationAdapter):
    """Sends outreach emails through Microsoft Graph Mail.Send using Entra ID OAuth2."""

    GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tenant_id: Optional[str] = None,
        sender_email: Optional[str] = None,
    ):
        self._explicit_client_id = client_id
        self._explicit_client_secret = client_secret
        self._explicit_tenant_id = tenant_id
        self._explicit_sender_email = sender_email

    @property
    def client_id(self) -> Optional[str]:
        return self._explicit_client_id or settings.MICROSOFT_CLIENT_ID

    @property
    def client_secret(self) -> Optional[str]:
        return self._explicit_client_secret or settings.MICROSOFT_CLIENT_SECRET

    @property
    def tenant_id(self) -> Optional[str]:
        return self._explicit_tenant_id or settings.MICROSOFT_TENANT_ID

    @property
    def sender_email(self) -> Optional[str]:
        return self._explicit_sender_email or settings.MICROSOFT_SENDER_EMAIL

    @property
    def graph_base_url(self) -> str:
        return settings.MICROSOFT_GRAPH_BASE_URL.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "microsoft_outlook"

    def missing_credentials(self) -> List[str]:
        """Return names of any unconfigured or placeholder Microsoft credentials."""
        required = {
            "MICROSOFT_CLIENT_ID": self.client_id,
            "MICROSOFT_CLIENT_SECRET": self.client_secret,
            "MICROSOFT_TENANT_ID": self.tenant_id,
            "MICROSOFT_SENDER_EMAIL": self.sender_email,
        }
        return [key for key, val in required.items() if not is_configured_value(val)]

    def _is_live_enabled(self, mode: Optional[str] = None) -> bool:
        return True

    async def check_health(self) -> IntegrationHealth:
        missing = self.missing_credentials()
        if missing:
            return IntegrationHealth(
                provider=self.provider_name,
                status="degraded",
                details={"mode": "production", "missing_credentials": missing},
            )
        return IntegrationHealth(
            provider=self.provider_name,
            status="healthy",
            latency_ms=5,
            details={"mode": "production", "sender_configured": True},
        )

    def _acquire_access_token_sync(self) -> str:
        """Acquire OAuth2 access token from Microsoft Entra ID via MSAL."""
        import msal

        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        app = msal.ConfidentialClientApplication(
            client_id=str(self.client_id),
            authority=authority,
            client_credential=str(self.client_secret),
        )
        token_result = app.acquire_token_for_client(scopes=self.GRAPH_SCOPE)
        access_token = token_result.get("access_token") if isinstance(token_result, dict) else None
        if not access_token:
            error_code = (
                token_result.get("error", "unknown_auth_error")
                if isinstance(token_result, dict)
                else "invalid_token_response"
            )
            error_desc = (
                token_result.get("error_description", "Token acquisition failed.")
                if isinstance(token_result, dict)
                else "Token acquisition failed."
            )
            # Never log credentials or tokens; log only the error code and sanitized summary.
            raise PermissionError(f"Microsoft Entra authentication failed ({error_code}): {error_desc[:200]}")
        return str(access_token)

    async def acquire_access_token(self) -> str:
        """Async wrapper around MSAL token acquisition."""
        return await asyncio.to_thread(self._acquire_access_token_sync)

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        mode: Optional[str] = None,
        content_type: str = "Text",
    ) -> Dict[str, Any]:
        """Send an email via Microsoft Graph API."""
        if not to_email or "@" not in to_email:
            err = f"Invalid recipient email address: '{to_email}'."
            logger.warning(f"[OutlookMail] Blocked dispatch: {err}")
            return {
                "status": "failed",
                "provider": self.provider_name,
                "sender": self.sender_email,
                "recipient": to_email,
                "subject": subject,
                "message_id": None,
                "error": err,
            }

        if to_email.lower().endswith(".example"):
            err = (
                f"Recipient '{to_email}' is a demo placeholder address (.example). "
                "Please enter a real recipient email address in Outreach Studio to dispatch via Microsoft Outlook."
            )
            logger.warning(f"[OutlookMail] {err}")
            return {
                "status": "failed",
                "provider": self.provider_name,
                "sender": self.sender_email,
                "recipient": to_email,
                "subject": subject,
                "message_id": None,
                "error": err,
            }

        missing = self.missing_credentials()
        if missing:
            err = f"Missing or placeholder Microsoft Outlook credentials: {', '.join(missing)}"
            logger.error(f"[OutlookMail] {err}")
            return {
                "status": "failed",
                "provider": self.provider_name,
                "sender": self.sender_email,
                "recipient": to_email,
                "subject": subject,
                "message_id": None,
                "error": err,
            }

        try:
            access_token = await self.acquire_access_token()
        except Exception as auth_err:
            err = f"Microsoft authentication failed: {str(auth_err)}"
            logger.error(f"[OutlookMail] {err}")
            return {
                "status": "failed",
                "provider": self.provider_name,
                "sender": self.sender_email,
                "recipient": to_email,
                "subject": subject,
                "message_id": None,
                "error": err,
            }

        endpoint = f"{self.graph_base_url}/users/{self.sender_email}/sendMail"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": content_type,
                    "content": body,
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email,
                        }
                    }
                ],
            },
            "saveToSentItems": True,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(endpoint, headers=headers, json=payload)

            if res.status_code in (200, 202):
                request_id = res.headers.get("request-id") or f"ms-mail-{uuid.uuid4().hex[:12]}"
                logger.info(
                    f"[OutlookMail] Email sent successfully to='{to_email}' "
                    f"from='{self.sender_email}' request_id='{request_id}'."
                )
                return {
                    "status": "sent",
                    "provider": self.provider_name,
                    "sender": self.sender_email,
                    "recipient": to_email,
                    "subject": subject,
                    "message_id": request_id,
                    "error": None,
                }

            if res.status_code in (401, 403):
                err = (
                    f"Microsoft Graph authorization denied (HTTP {res.status_code}). "
                    "Verify Mail.Send Application permission and admin consent."
                )
            elif res.status_code == 404:
                err = f"Microsoft Graph mailbox not found (HTTP 404) for sender '{self.sender_email}'."
            elif res.status_code == 429:
                err = "Microsoft Graph API rate limit exceeded (HTTP 429)."
            else:
                err = f"Microsoft Graph sendMail failed with HTTP {res.status_code}."

            logger.error(f"[OutlookMail] {err}")
            return {
                "status": "failed",
                "provider": self.provider_name,
                "sender": self.sender_email,
                "recipient": to_email,
                "subject": subject,
                "message_id": None,
                "error": err,
            }
        except httpx.TimeoutException:
            err = "Microsoft Graph sendMail request timed out."
            logger.error(f"[OutlookMail] {err}")
            return {
                "status": "failed",
                "provider": self.provider_name,
                "sender": self.sender_email,
                "recipient": to_email,
                "subject": subject,
                "message_id": None,
                "error": err,
            }
        except Exception as e:
            err = f"Microsoft Graph sendMail unexpected error: {type(e).__name__}"
            logger.error(f"[OutlookMail] {err}")
            return {
                "status": "failed",
                "provider": self.provider_name,
                "sender": self.sender_email,
                "recipient": to_email,
                "subject": subject,
                "message_id": None,
                "error": err,
            }

    async def fetch_inbox_messages(
        self,
        top: int = 25,
        unread_only: bool = False,
    ) -> Dict[str, Any]:
        """Fetch incoming emails from the organizer's inbox via Microsoft Graph API."""
        missing = self.missing_credentials()
        if missing:
            return {
                "status": "failed",
                "messages": [],
                "error": f"Missing Microsoft credentials: {', '.join(missing)}",
            }

        try:
            access_token = await self.acquire_access_token()
        except Exception as auth_err:
            return {
                "status": "failed",
                "messages": [],
                "error": f"Microsoft authentication failed: {str(auth_err)}",
            }

        params = [f"$top={top}", "$orderby=receivedDateTime desc"]
        if unread_only:
            params.append("$filter=isRead eq false")
        query_str = "&".join(params)

        endpoint = f"{self.graph_base_url}/users/{self.sender_email}/mailFolders/inbox/messages?{query_str}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(endpoint, headers=headers)

            if res.status_code == 200:
                data = res.json()
                raw_messages = data.get("value", [])
                items = []
                for m in raw_messages:
                    from_info = m.get("from", {}).get("emailAddress", {})
                    items.append({
                        "message_id": m.get("id"),
                        "subject": m.get("subject", ""),
                        "sender_email": from_info.get("address", "").strip().lower(),
                        "sender_name": from_info.get("name", ""),
                        "recipient_email": self.sender_email,
                        "received_time": m.get("receivedDateTime"),
                        "body": m.get("body", {}).get("content", "") or m.get("bodyPreview", ""),
                        "body_preview": m.get("bodyPreview", ""),
                        "is_read": m.get("isRead", False),
                    })
                return {
                    "status": "success",
                    "messages": items,
                    "count": len(items),
                    "error": None,
                }

            if res.status_code in (401, 403):
                err = (
                    "Microsoft Graph Access Denied (HTTP 403). Azure Entra ID App registration "
                    f"'{self.client_id}' requires the 'Mail.Read' Application permission with Admin Consent "
                    "in Azure Portal to read incoming email replies."
                )
                logger.warning(f"[OutlookMail] {err}")
                return {
                    "status": "permission_denied",
                    "messages": [],
                    "error": err,
                    "required_permission": "Mail.Read",
                }

            err = f"Microsoft Graph failed to fetch inbox (HTTP {res.status_code}): {res.text[:200]}"
            logger.error(f"[OutlookMail] {err}")
            return {
                "status": "failed",
                "messages": [],
                "error": err,
            }
        except Exception as e:
            err = f"Failed to connect to Microsoft Graph inbox: {str(e)}"
            logger.error(f"[OutlookMail] {err}")
            return {
                "status": "failed",
                "messages": [],
                "error": err,
            }
