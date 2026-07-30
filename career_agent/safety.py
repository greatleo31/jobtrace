from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


class ConfirmationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ApprovalGrant:
    token: str
    target_id: str
    message_hash: str
    expires_at: str


@dataclass(frozen=True, slots=True)
class ConfirmedSend:
    target_id: str
    message: str
    idempotency_key: str


class SendGuard:
    def __init__(self, secret: bytes, ttl: timedelta = timedelta(minutes=5)) -> None:
        if not secret:
            raise ValueError("confirmation secret is required")
        self.secret = secret
        self.ttl = ttl

    @staticmethod
    def _message_hash(message: str) -> str:
        return hashlib.sha256(message.encode("utf-8")).hexdigest()

    def prepare(self, target_id: str, message: str, *, now: datetime | None = None) -> ApprovalGrant:
        if not target_id.strip() or not message.strip():
            raise ConfirmationError("target and message are required")
        instant = now or datetime.now(UTC)
        expires_at = instant + self.ttl
        payload = {
            "target_id": target_id,
            "message_hash": self._message_hash(message),
            "expires_at": expires_at.isoformat(),
            "nonce": secrets.token_urlsafe(12),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self.secret, raw, hashlib.sha256).digest()
        token = base64.urlsafe_b64encode(raw + signature).decode("ascii")
        return ApprovalGrant(token, target_id, payload["message_hash"], payload["expires_at"])

    def confirm(
        self,
        approval: ApprovalGrant,
        target_id: str,
        message: str,
        *,
        now: datetime | None = None,
    ) -> ConfirmedSend:
        try:
            decoded = base64.urlsafe_b64decode(approval.token.encode("ascii"))
            raw, supplied_signature = decoded[:-32], decoded[-32:]
            expected_signature = hmac.new(self.secret, raw, hashlib.sha256).digest()
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ConfirmationError("invalid confirmation signature")
            payload = json.loads(raw)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ConfirmationError("invalid confirmation token") from error

        instant = now or datetime.now(UTC)
        expires_at = datetime.fromisoformat(payload["expires_at"])
        if instant > expires_at:
            raise ConfirmationError("confirmation expired")
        if payload["target_id"] != target_id or approval.target_id != target_id:
            raise ConfirmationError("confirmation target mismatch")
        message_hash = self._message_hash(message)
        if payload["message_hash"] != message_hash or approval.message_hash != message_hash:
            raise ConfirmationError("confirmation content mismatch")
        idempotency_key = hashlib.sha256(approval.token.encode("ascii")).hexdigest()
        return ConfirmedSend(target_id, message, idempotency_key)
