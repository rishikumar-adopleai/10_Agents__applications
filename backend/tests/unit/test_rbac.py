"""Unit Tests for RBAC and Authorization Boundaries."""

from backend.app.core.rbac import (
    CurrentUser,
    Permission,
    RoleEnum,
)


def test_rbac_commercial_approval_separation():
    """Verify that Administrator does NOT automatically have commercial approval authority."""
    admin_user = CurrentUser(
        id="admin-1",
        email="admin@test.com",
        organization_id="org-1",
        roles=[RoleEnum.ADMINISTRATOR],
    )
    sales_manager_user = CurrentUser(
        id="mgr-1",
        email="mgr@test.com",
        organization_id="org-1",
        roles=[RoleEnum.SALES_MANAGER],
    )

    # Sales Manager has PROPOSAL_APPROVE
    assert sales_manager_user.has_permission(Permission.PROPOSAL_APPROVE) is True

    # Administrator does NOT have PROPOSAL_APPROVE (strict segregation of duties)
    assert admin_user.has_permission(Permission.PROPOSAL_APPROVE) is False


def test_rbac_security_attestation_separation():
    """Verify that only Security Reviewer has SECURITY_ATTEST permission."""
    sec_user = CurrentUser(
        id="sec-1",
        email="sec@test.com",
        organization_id="org-1",
        roles=[RoleEnum.SECURITY_REVIEWER],
    )
    rep_user = CurrentUser(
        id="rep-1",
        email="rep@test.com",
        organization_id="org-1",
        roles=[RoleEnum.SALES_REPRESENTATIVE],
    )

    assert sec_user.has_permission(Permission.SECURITY_ATTEST) is True
    assert rep_user.has_permission(Permission.SECURITY_ATTEST) is False
