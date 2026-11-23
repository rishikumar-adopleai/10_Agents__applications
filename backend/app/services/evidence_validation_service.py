"""Evidence Validation Service conforming to Sections 13 & 14."""

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse


class EvidenceValidationService:
    """Validates external source evidence against strict enterprise criteria."""

    def __init__(self, freshness_days: int = 90):
        self.freshness_days = freshness_days

    def compute_evidence_hash(
        self, account_id: str, signal_type: str, source_provider: str, identifier_or_url: str
    ) -> str:
        """Generate a stable, deterministic fingerprint to deduplicate evidence."""
        raw_key = f"{account_id.strip()}:{signal_type.strip().lower()}:{source_provider.strip().lower()}:{identifier_or_url.strip().lower()}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def sanitize_untrusted_text(self, text: str, max_length: int = 1000) -> str:
        """Sanitize raw text from external sources to prevent injection and format errors."""
        if not text:
            return ""
        # Remove null bytes and excessive whitespace
        clean = text.replace("\x00", " ")
        clean = " ".join(clean.split())
        # Strip potential HTML / script tags
        clean = re.sub(r"<[^>]+>", "", clean)
        return clean[:max_length].strip()

    def validate_url(self, url: str) -> bool:
        """Validate URL syntax, scheme, and enforce SSRF defenses against private and metadata networks."""
        import ipaddress

        if not url:
            return False
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                return False

            hostname = parsed.hostname
            if not hostname:
                return False

            hostname_lower = hostname.lower()
            if hostname_lower in ("localhost", "0.0.0.0", "127.0.0.1", "::1", "metadata.google.internal"):
                return False
            if hostname_lower.endswith(".local") or hostname_lower.endswith(".internal"):
                return False

            # Check for private or link-local IP addresses (e.g., 169.254.169.254, 10.x, 192.168.x)
            try:
                ip = ipaddress.ip_address(hostname_lower)
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_reserved
                    or ip.is_multicast
                    or str(ip).startswith("169.254.")
                ):
                    return False
            except ValueError:
                # Hostname is a standard domain name, not an IP literal
                pass

            return True
        except Exception:
            return False

    def validate_evidence_record(
        self,
        account_id: str,
        account_domain: str,
        signal_data: Dict[str, Any],
        now: Optional[datetime] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Validate an evidence candidate. Returns (is_valid, status, normalized_evidence_dict)."""
        current_time = now or datetime.now(timezone.utc)

        signal_type = signal_data.get("signal_type", "").strip()
        signal_subtype = signal_data.get("signal_subtype", "").strip()
        observed_fact = self.sanitize_untrusted_text(signal_data.get("observed_fact", ""))
        business_hypothesis = self.sanitize_untrusted_text(signal_data.get("business_hypothesis", ""))
        source_provider = signal_data.get("source_provider", "").strip()
        source_url = signal_data.get("source_url", "").strip()
        source_record_id = signal_data.get("source_record_id")

        if not signal_type or not observed_fact or not source_provider:
            return False, "REJECTED", None

        # 1. URL validation
        if not self.validate_url(source_url):
            return False, "REJECTED", None

        # 2. Freshness check
        verification_status = "VERIFIED"
        published_at = signal_data.get("published_at")
        pub_dt = None
        if published_at:
            if isinstance(published_at, str):
                try:
                    clean_str = published_at.strip().replace("Z", "+00:00")
                    if len(clean_str) == 10 and clean_str.count("-") == 2:
                        clean_str += "T00:00:00+00:00"
                    pub_dt = datetime.fromisoformat(clean_str)
                except Exception:
                    pub_dt = None
            elif isinstance(published_at, datetime):
                pub_dt = published_at
            elif hasattr(published_at, "year") and hasattr(published_at, "month") and hasattr(published_at, "day"):
                pub_dt = datetime(published_at.year, published_at.month, published_at.day, tzinfo=timezone.utc)

            if pub_dt:
                # Normalize both to UTC timezone-aware to prevent offset subtraction errors
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                else:
                    pub_dt = pub_dt.astimezone(timezone.utc)

                if current_time.tzinfo is None:
                    current_time = current_time.replace(tzinfo=timezone.utc)
                else:
                    current_time = current_time.astimezone(timezone.utc)

                age_days = (current_time - pub_dt).days
                if age_days > self.freshness_days:
                    verification_status = "STALE"

        # 3. Source identifier & fingerprint
        id_for_hash = source_record_id or source_url
        evidence_hash = self.compute_evidence_hash(
            account_id=account_id,
            signal_type=signal_type,
            source_provider=source_provider,
            identifier_or_url=id_for_hash,
        )

        confidence = float(signal_data.get("confidence", 1.0))
        if verification_status == "STALE":
            confidence = max(0.1, confidence * 0.5)

        normalized = {
            "account_id": account_id,
            "signal_type": signal_type,
            "signal_subtype": signal_subtype,
            "observed_fact": observed_fact,
            "business_hypothesis": business_hypothesis,
            "source_provider": source_provider,
            "source_url": source_url,
            "source_record_id": str(source_record_id) if source_record_id else None,
            "published_at": pub_dt,
            "first_observed_at": current_time,
            "last_checked_at": current_time,
            "verification_status": verification_status,
            "evidence_hash": evidence_hash,
            "confidence": confidence,
            "raw_metadata": signal_data.get("raw_metadata", {}),
        }

        return True, verification_status, normalized
