"""Unit Tests for Strict Business Rules Enforcement."""

import pytest

from backend.app.core.exceptions import BusinessRuleViolationError
from backend.app.models.sales import Account, Contact
from backend.app.services.attempt_service import AttemptTrackingService
from backend.app.services.suppression_service import SuppressionService


@pytest.mark.asyncio
async def test_max_three_outreach_attempts_strict_limit(db_session, seed_data):
    """Verify that the 4th unanswered outreach attempt is strictly blocked."""
    org = seed_data["org"]
    account = Account(organization_id=org.id, name="Test Account", domain="test.com")
    db_session.add(account)
    await db_session.flush()

    contact = Contact(
        organization_id=org.id,
        account_id=account.id,
        first_name="Alice",
        last_name="Smith",
        email="alice@test.com",
        logical_outreach_attempts=0,
    )
    db_session.add(contact)
    await db_session.flush()

    service = AttemptTrackingService(db_session)

    # Attempt 1 -> OK
    att1 = await service.record_logical_attempt(org.id, contact.id)
    assert att1.attempt_number == 1
    assert contact.logical_outreach_attempts == 1

    # Attempt 2 -> OK
    att2 = await service.record_logical_attempt(org.id, contact.id)
    assert att2.attempt_number == 2
    assert contact.logical_outreach_attempts == 2

    # Attempt 3 -> OK
    att3 = await service.record_logical_attempt(org.id, contact.id)
    assert att3.attempt_number == 3
    assert contact.logical_outreach_attempts == 3

    # Attempt 4 -> Strictly Blocked with BusinessRuleViolationError
    with pytest.raises(BusinessRuleViolationError) as exc_info:
        await service.record_logical_attempt(org.id, contact.id)
    assert exc_info.value.code == "MAX_ATTEMPTS_EXCEEDED"
    assert "4th attempt strictly forbidden" in exc_info.value.message


@pytest.mark.asyncio
async def test_contact_suppression_hard_enforcement(db_session, seed_data):
    """Verify that suppressed contact immediately blocks subsequent outreach."""
    org = seed_data["org"]
    suppression_service = SuppressionService(db_session)

    test_email = "optout@company.com"
    test_phone = "+15550001122"

    # Initially not suppressed
    assert (
        await suppression_service.is_contact_suppressed(email=test_email, phone=test_phone) is False
    )

    # Record opt-out
    await suppression_service.record_suppression(
        organization_id=org.id,
        reason="opt_out",
        email=test_email,
        phone=test_phone,
    )

    # Check suppression
    assert await suppression_service.is_contact_suppressed(email=test_email) is True
    assert await suppression_service.is_contact_suppressed(phone=test_phone) is True

    # Assert raises BusinessRuleViolationError
    with pytest.raises(BusinessRuleViolationError) as exc_info:
        await suppression_service.assert_can_contact(email=test_email)
    assert exc_info.value.code == "CONTACT_SUPPRESSED"
