"""Apollo CSV Company & Contact Import Service."""

import csv
import io
import re
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import logger
from backend.app.models.radar import CsvImportHistory
from backend.app.models.sales import Account, Contact
from backend.app.repositories.radar_repo import CsvImportHistoryRepository
from backend.app.repositories.sales_repo import AccountRepository, ContactRepository

# Common Apollo column aliases to canonical internal field names
STANDARD_COLUMN_MAP = {
    "company name": "name",
    "company": "name",
    "organization": "name",
    "account name": "name",
    "website": "domain",
    "company website": "domain",
    "domain": "domain",
    "industry": "industry",
    "# employees": "employee_count",
    "employees": "employee_count",
    "estimated num employees": "employee_count",
    "company country": "country",
    "country": "country",
    "company state": "state",
    "state": "state",
    "company city": "city",
    "city": "city",
    "annual revenue": "annual_revenue",
    "revenue": "annual_revenue",
    "apollo org id": "apollo_id",
    "apollo account id": "apollo_id",
    "company linkedin url": "linkedin_url",
    "short description": "short_description",
    "contact first name": "contact_first_name",
    "first name": "contact_first_name",
    "contact last name": "contact_last_name",
    "last name": "contact_last_name",
    "contact email": "contact_email",
    "email": "contact_email",
    "contact phone": "contact_phone",
    "phone": "contact_phone",
    "contact title": "contact_title",
    "title": "contact_title",
}


def sanitize_csv_cell(value: Optional[str]) -> Optional[str]:
    """Prevent CSV formula injection by escaping dangerous leading characters."""
    if not value or not isinstance(value, str):
        return value
    val = value.strip()
    # If cell starts with formula characters and is not purely a negative number
    if val.startswith(("=", "+", "-", "@")) and len(val) > 1:
        # Check if it's a valid number like -500 or +10
        test_num = val[1:].replace(".", "", 1)
        if not test_num.isdigit():
            val = "'" + val
    return val


def canonicalize_domain(raw_url_or_domain: str) -> str:
    """Normalize domain to clean lowercase domain without scheme, www, or path."""
    if not raw_url_or_domain:
        return ""
    domain = raw_url_or_domain.strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = re.sub(r"^www\.", "", domain)
    domain = domain.split("/")[0].split("?")[0].strip()
    return domain


class CsvImportService:
    """Service for uploading, previewing, mapping, validating, and importing Apollo CSV files."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.account_repo = AccountRepository(session)
        self.contact_repo = ContactRepository(session)
        self.history_repo = CsvImportHistoryRepository(session)

    def preview_csv(self, content_str: str, max_rows: int = 5) -> Dict[str, Any]:
        """Read CSV headers and preview sample rows with suggested column mapping."""
        reader = csv.DictReader(io.StringIO(content_str))
        headers = reader.fieldnames or []

        suggested_mappings = {}
        for h in headers:
            clean_h = h.strip().lower()
            if clean_h in STANDARD_COLUMN_MAP:
                suggested_mappings[h] = STANDARD_COLUMN_MAP[clean_h]

        sample_rows = []
        total_rows = 0
        for row in reader:
            total_rows += 1
            if len(sample_rows) < max_rows:
                # Sanitize sample
                sample = {k: str(v)[:120] if v is not None else "" for k, v in row.items()}
                sample_rows.append(sample)

        return {
            "total_rows_detected": total_rows,
            "headers": headers,
            "sample_rows": sample_rows,
            "suggested_mappings": suggested_mappings,
        }

    async def import_csv(
        self,
        organization_id: str,
        content_str: str,
        filename: str = "apollo_export.csv",
        custom_mapping: Optional[Dict[str, str]] = None,
    ) -> CsvImportHistory:
        """Parse, validate, deduplicate, and import accounts and contacts into SQLite."""
        reader = csv.DictReader(io.StringIO(content_str))
        headers = reader.fieldnames or []

        # Build active mapping
        active_map: Dict[str, str] = {}
        for h in headers:
            clean_h = h.strip().lower()
            if custom_mapping and h in custom_mapping:
                active_map[h] = custom_mapping[h]
            elif clean_h in STANDARD_COLUMN_MAP:
                active_map[h] = STANDARD_COLUMN_MAP[clean_h]

        total_rows = 0
        imported_accounts = 0
        imported_contacts = 0
        duplicate_accounts = 0
        errors = []

        # Cache seen domains in current batch to handle intra-file duplicates
        seen_domains_in_batch: Dict[str, Account] = {}

        for row_idx, row in enumerate(reader, start=2):
            total_rows += 1
            try:
                # Map fields
                mapped: Dict[str, Any] = {}
                for csv_col, field_name in active_map.items():
                    val = row.get(csv_col)
                    if val is not None:
                        mapped[field_name] = sanitize_csv_cell(val)

                raw_domain = mapped.get("domain", "")
                domain = canonicalize_domain(raw_domain)
                name = mapped.get("name") or (domain.split(".")[0].capitalize() if domain else "Unnamed Company")

                if not domain:
                    errors.append({
                        "row": row_idx,
                        "error": "Missing company website/domain. Record skipped.",
                        "data": {"name": name},
                    })
                    continue

                # Parse employee count safely
                employee_count = None
                raw_emp = mapped.get("employee_count")
                if raw_emp:
                    cleaned_emp = re.sub(r"[^0-9]", "", str(raw_emp))
                    if cleaned_emp:
                        employee_count = int(cleaned_emp)

                # Parse annual revenue safely
                annual_revenue = None
                raw_rev = mapped.get("annual_revenue")
                if raw_rev:
                    cleaned_rev = re.sub(r"[^0-9\.]", "", str(raw_rev))
                    if cleaned_rev:
                        annual_revenue = float(cleaned_rev)

                account = None
                if domain in seen_domains_in_batch:
                    account = seen_domains_in_batch[domain]
                    duplicate_accounts += 1
                else:
                    # Check database for deduplication by canonical domain within organization
                    existing = await self.account_repo.get_by_domain(domain, organization_id)
                    if existing:
                        account = existing
                        duplicate_accounts += 1
                        # Safe non-destructive update of empty fields
                        if not account.employee_count and employee_count:
                            account.employee_count = employee_count
                        if not account.industry and mapped.get("industry"):
                            account.industry = mapped.get("industry")
                        if not account.apollo_id and mapped.get("apollo_id"):
                            account.apollo_id = mapped.get("apollo_id")
                        if not account.country and mapped.get("country"):
                            account.country = mapped.get("country")
                    else:
                        account = Account(
                            organization_id=organization_id,
                            name=name,
                            domain=domain,
                            industry=mapped.get("industry"),
                            employee_count=employee_count,
                            country=mapped.get("country"),
                            state=mapped.get("state"),
                            city=mapped.get("city"),
                            annual_revenue=annual_revenue,
                            apollo_id=mapped.get("apollo_id"),
                            linkedin_url=mapped.get("linkedin_url"),
                            short_description=mapped.get("short_description"),
                            status="prospect",
                            fit_score=0.0,
                        )
                        self.session.add(account)
                        await self.session.flush()
                        imported_accounts += 1

                    seen_domains_in_batch[domain] = account

                # Handle contact if contact data is in row
                contact_email = mapped.get("contact_email")
                if contact_email and "@" in contact_email:
                    clean_email = contact_email.lower().strip()
                    existing_contact = await self.contact_repo.get_by_email(clean_email, organization_id)
                    if not existing_contact:
                        first_name = mapped.get("contact_first_name") or "Contact"
                        last_name = mapped.get("contact_last_name") or name
                        contact = Contact(
                            organization_id=organization_id,
                            account_id=account.id,
                            first_name=first_name,
                            last_name=last_name,
                            email=clean_email,
                            phone=mapped.get("contact_phone"),
                            title=mapped.get("contact_title"),
                            linkedin_url=mapped.get("contact_linkedin_url"),
                            apollo_id=mapped.get("contact_apollo_id"),
                        )
                        self.session.add(contact)
                        await self.session.flush()
                        imported_contacts += 1

            except Exception as row_exc:
                logger.warning(f"Error importing row {row_idx}: {row_exc}")
                errors.append({"row": row_idx, "error": str(row_exc)})

        history = CsvImportHistory(
            organization_id=organization_id,
            filename=filename,
            total_rows=total_rows,
            imported_accounts=imported_accounts,
            imported_contacts=imported_contacts,
            duplicate_accounts=duplicate_accounts,
            errors_count=len(errors),
            status="completed" if not errors or imported_accounts > 0 else "failed",
            column_mapping=active_map,
            error_log=errors[:50],  # Bound log size
        )
        self.session.add(history)
        await self.session.commit()

        logger.info(
            f"Imported CSV '{filename}': {imported_accounts} new accounts, "
            f"{imported_contacts} contacts, {duplicate_accounts} duplicates, {len(errors)} errors."
        )
        return history
