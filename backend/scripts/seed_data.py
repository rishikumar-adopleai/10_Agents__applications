"""Database Seeding Script for Initial Roles, Users, and Sample Data."""

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select

from backend.app.core.rbac import RoleEnum
from backend.app.core.security import hash_password
from backend.app.db.base import Base
from backend.app.db.session import AsyncSessionLocal, engine
from backend.app.models.identity import Organization, Role, User
from backend.app.models.sales import Account, Contact, Opportunity


async def seed():
    print("Starting database seeding...")
    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # 1. Seed Organization
        res = await session.execute(select(Organization).where(Organization.slug == "acme-corp"))
        org = res.scalars().first()
        if not org:
            org = Organization(
                name="Acme Corporation",
                slug="acme-corp",
                is_active=True,
            )
            session.add(org)
            await session.flush()
            print(f"Created organization: {org.name}")

        # 2. Seed All Roles
        role_map = {}
        for role_enum in RoleEnum:
            res_role = await session.execute(select(Role).where(Role.name == role_enum.value))
            role = res_role.scalars().first()
            if not role:
                role = Role(name=role_enum.value, description=f"{role_enum.value} system role")
                session.add(role)
                await session.flush()
                print(f"Created role: {role.name}")
            role_map[role_enum.value] = role

        # 3. Seed Users with distinct roles
        users_to_seed = [
            (
                "admin@acme.com",
                "AdminPass123!",
                "Admin",
                "User",
                [RoleEnum.ADMINISTRATOR],
                True,
            ),
            (
                "sales.mgr@acme.com",
                "AdminPass123!",
                "Alice",
                "Manager",
                [RoleEnum.SALES_MANAGER],
                False,
            ),
            (
                "sales.rep@acme.com",
                "AdminPass123!",
                "Bob",
                "Representative",
                [RoleEnum.SALES_REPRESENTATIVE],
                False,
            ),
            (
                "security@acme.com",
                "AdminPass123!",
                "Charlie",
                "SecReviewer",
                [RoleEnum.SECURITY_REVIEWER],
                False,
            ),
            (
                "admin@example.com",
                "AdminSecretPass123!",
                "Admin",
                "User",
                [RoleEnum.ADMINISTRATOR],
                True,
            ),
            (
                "manager@example.com",
                "SalesManagerPass123!",
                "Alice",
                "Manager",
                [RoleEnum.SALES_MANAGER],
                False,
            ),
            (
                "sales@example.com",
                "SalesPass123!",
                "Bob",
                "Representative",
                [RoleEnum.SALES_REPRESENTATIVE],
                False,
            ),
            (
                "security@example.com",
                "SecurityPass123!",
                "Charlie",
                "SecReviewer",
                [RoleEnum.SECURITY_REVIEWER],
                False,
            ),
            (
                "delivery@example.com",
                "DeliveryPass123!",
                "Diana",
                "DeliveryOwner",
                [RoleEnum.DELIVERY_OWNER],
                False,
            ),
            (
                "marketing@example.com",
                "MarketingPass123!",
                "Eve",
                "Marketing",
                [RoleEnum.MARKETING_MANAGER],
                False,
            ),
            (
                "partner@example.com",
                "PartnerPass123!",
                "Frank",
                "PartnerMgr",
                [RoleEnum.PARTNER_MANAGER],
                False,
            ),
        ]

        for email, password, fname, lname, roles, is_super in users_to_seed:
            res_user = await session.execute(select(User).where(User.email == email))
            user = res_user.scalars().first()
            if not user:
                user = User(
                    email=email,
                    hashed_password=hash_password(password),
                    first_name=fname,
                    last_name=lname,
                    organization_id=org.id,
                    is_active=True,
                    is_superuser=is_super,
                    roles=[role_map[r.value] for r in roles],
                )
                session.add(user)
                await session.flush()
                print(f"Created user: {email} ({[r.value for r in roles]})")

        # 4. Seed Sample Account and Contact
        res_acc = await session.execute(select(Account).where(Account.domain == "globex.com"))
        acc = res_acc.scalars().first()
        if not acc:
            acc = Account(
                organization_id=org.id,
                name="Globex International",
                domain="globex.com",
                industry="Financial Services",
                employee_count=1200,
                fit_score=0.92,
                status="prioritized",
            )
            session.add(acc)
            await session.flush()
            print(f"Created account: {acc.name}")

            contact = Contact(
                organization_id=org.id,
                account_id=acc.id,
                first_name="Hank",
                last_name="Scorpio",
                email="hank.scorpio@globex.com",
                phone="+15559876543",
                title="Chief Technology Officer",
                logical_outreach_attempts=0,
                is_suppressed=False,
            )
            session.add(contact)
            await session.flush()
            print(f"Created contact: {contact.first_name} {contact.last_name}")

            opp = Opportunity(
                organization_id=org.id,
                account_id=acc.id,
                name="Globex Enterprise Platform Deal",
                amount=75000.0,
                stage="discovery",
                discovery_completed=True,
                discovery_notes="Buyer confirmed urgent need to automate inbound qualification and proposal turnaround.",
            )
            session.add(opp)
            await session.flush()
            print(f"Created opportunity: {opp.name}")

        await session.commit()
    print("Database seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
