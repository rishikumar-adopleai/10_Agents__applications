"""Sample Data Integration and Compatibility Adapter for Pipeline 2."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.config import settings
from backend.app.core.logging import logger


def resolve_fixture_path(relative_path: str) -> Path:
    """Safely resolve fixture path against common project base directories."""
    candidates = [
        Path(relative_path),
        Path(__file__).parent.parent.parent / "tests" / "fixtures" / Path(relative_path).name,
        Path(__file__).parent.parent.parent.parent / relative_path,
        Path.cwd() / relative_path,
        Path.cwd() / "backend" / "app" / "tests" / "fixtures" / Path(relative_path).name,
    ]
    for c in candidates:
        if c.is_file():
            return c
    # Fallback to direct candidate
    return Path(relative_path)


class SampleDataLoader:
    """Loads and validates sample company and contact fixtures without touching production records."""

    def __init__(
        self,
        accounts_file: Optional[str] = None,
        contacts_file: Optional[str] = None,
    ):
        self.accounts_file = resolve_fixture_path(
            accounts_file or settings.PIPELINE2_SAMPLE_ACCOUNTS_FILE
        )
        self.contacts_file = resolve_fixture_path(
            contacts_file or settings.PIPELINE2_SAMPLE_CONTACTS_FILE
        )

    def load_accounts_raw(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Load accounts from sample file.
        Returns: (valid_records, validation_failures)
        """
        if not self.accounts_file.exists():
            logger.warning(f"Accounts fixture not found: {self.accounts_file}")
            return [], [{"error": f"Fixture file not found: {self.accounts_file}"}]

        try:
            with open(self.accounts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to parse accounts JSON: {str(e)}")
            return [], [{"error": f"JSON parse error in {self.accounts_file}: {str(e)}"}]

        raw_accounts = data.get("accounts", [])
        if not isinstance(raw_accounts, list):
            return [], [{"error": "Root 'accounts' field must be a list"}]

        valid_records: List[Dict[str, Any]] = []
        validation_failures: List[Dict[str, Any]] = []

        seen_account_ids = set()

        for idx, item in enumerate(raw_accounts):
            if not isinstance(item, dict):
                validation_failures.append({"index": idx, "error": "Account entry must be an object"})
                continue

            account_id = item.get("account_id")
            if not account_id:
                validation_failures.append({"index": idx, "error": "Missing required field: account_id"})
                continue

            if account_id in seen_account_ids:
                validation_failures.append({
                    "account_id": account_id,
                    "error": f"Duplicate account_id '{account_id}' detected and skipped",
                })
                continue

            company = item.get("company", {})
            if not isinstance(company, dict) or not company.get("name") or not company.get("domain"):
                validation_failures.append({
                    "account_id": account_id,
                    "error": "Account company must include 'name' and 'domain'",
                })
                continue

            seen_account_ids.add(account_id)
            valid_records.append(item)

        return valid_records, validation_failures

    def load_contacts_raw(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load enrichment contacts mapped by account_id.
        """
        if not self.contacts_file.exists():
            logger.info(f"Contacts fixture not found: {self.contacts_file}")
            return {}

        try:
            with open(self.contacts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to parse contacts JSON: {str(e)}")
            return {}

        account_contacts: Dict[str, List[Dict[str, Any]]] = {}
        for acc_entry in data.get("accounts", []):
            acc_id = acc_entry.get("account_id")
            if not acc_id:
                continue
            contacts = acc_entry.get("contacts", [])
            if isinstance(contacts, list):
                account_contacts[acc_id] = contacts

        return account_contacts

    def get_all_sample_accounts(self) -> List[Dict[str, Any]]:
        """
        Merges account data with contact enrichment, deduplicating contacts and preserving all fields.
        """
        valid_accounts, _ = self.load_accounts_raw()
        contacts_by_acc = self.load_contacts_raw()

        processed_accounts = []
        for acc in valid_accounts:
            acc_id = acc["account_id"]
            # Base contacts from agent1 sample
            base_contacts = acc.get("contacts", [])
            # Additional contacts from pipeline2_mock_contacts
            extra_contacts = contacts_by_acc.get(acc_id, [])

            # Deduplicate contacts by contact_id or email
            merged_contacts: List[Dict[str, Any]] = []
            seen_contact_ids = set()
            seen_emails = set()

            for c in base_contacts + extra_contacts:
                cid = c.get("contact_id")
                email = c.get("email")
                if cid and cid in seen_contact_ids:
                    continue
                if email and email in seen_emails:
                    continue
                if cid:
                    seen_contact_ids.add(cid)
                if email:
                    seen_emails.add(email)

                c_copy = dict(c)
                full_name = c_copy.get("full_name", "")
                if "first_name" not in c_copy or not c_copy["first_name"]:
                    parts = full_name.split() if full_name else []
                    c_copy["first_name"] = parts[0] if parts else "there"
                    c_copy["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""
                merged_contacts.append(c_copy)

            normalized = {
                "account_id": acc_id,
                "company_name": acc["company"]["name"],
                "domain": acc["company"]["domain"],
                "website": acc["company"].get("website", f"https://{acc['company']['domain']}"),
                "industry": acc["company"].get("industry", "Technology"),
                "country": acc["company"].get("country", "US"),
                "identity_verified": acc.get("identity_verified", True),
                "priority": acc.get("priority", {
                    "score": 70,
                    "tier": "medium",
                    "why_now": "Prioritized by Signal Radar",
                    "rubric_version": "1.0",
                }),
                "signals": acc.get("signals", []),
                "contacts": merged_contacts,
                "research_status": acc.get("research_status", "ready"),
                "contact_eligibility": acc.get("contact_eligibility", "test_only_not_authorized"),
                "is_synthetic": True,
            }
            processed_accounts.append(normalized)

        return processed_accounts

    def get_sample_account_by_id(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Find single sample account by its ID (e.g. ACC-001)."""
        accounts = self.get_all_sample_accounts()
        for a in accounts:
            if a["account_id"].lower() == account_id.lower():
                return a
        return None


class Pipeline1CompatibilityAdapter:
    """Minimal compatibility adapter to normalize Pipeline 1 outputs or DB records for Pipeline 2."""

    @staticmethod
    def adapt_from_agent1_result(agent1_output: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Agent 1 (BuyingSignalRadarAgent) structured_result into canonical format."""
        account_id = agent1_output.get("account_id", "ACC-UNKNOWN")
        company_name = agent1_output.get("company_name", "Target Company")
        domain = agent1_output.get("domain", "target.example")
        fit_score = agent1_output.get("fit_score", 0.75)
        why_now = agent1_output.get("why_now", "Signal detected by radar")
        observed_facts = agent1_output.get("observed_facts", [])

        # Construct signals from observed facts
        signals = []
        for idx, fact in enumerate(observed_facts):
            signals.append({
                "signal_id": f"SIG-P1-{idx+1}",
                "type": "hiring_expansion",
                "observed_fact": fact,
                "observed_at": "2026-11-17T00:00:00Z",
                "source": {
                    "url": f"https://{domain}/careers",
                    "source_type": "radar_feed",
                    "retrieved_at": "2026-11-17T00:00:00Z",
                },
                "confidence": "verified",
            })

        tier = "high" if fit_score >= 0.80 else ("medium" if fit_score >= 0.50 else "low")

        return {
            "account_id": account_id,
            "company_name": company_name,
            "domain": domain,
            "website": f"https://{domain}",
            "industry": agent1_output.get("industry", "Enterprise Software"),
            "country": "US",
            "identity_verified": True,
            "priority": {
                "score": int(fit_score * 100) if fit_score <= 1.0 else int(fit_score),
                "tier": tier,
                "why_now": why_now,
                "rubric_version": "1.0",
            },
            "signals": signals,
            "contacts": [],
            "research_status": "ready",
            "contact_eligibility": "eligible",
            "is_synthetic": False,
        }
