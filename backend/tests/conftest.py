"""Pytest Configuration and Shared Test Fixtures."""

from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.rbac import RoleEnum
from backend.app.core.security import create_access_token, hash_password
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.identity import Organization, Role, User

# Test database in memory
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def init_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def seed_data(db_session: AsyncSession):
    # Create Organization
    org = Organization(name="Test Org", slug="test-org", is_active=True)
    db_session.add(org)
    await db_session.flush()

    # Create Roles
    role_admin = Role(name=RoleEnum.ADMINISTRATOR.value)
    role_mgr = Role(name=RoleEnum.SALES_MANAGER.value)
    role_rep = Role(name=RoleEnum.SALES_REPRESENTATIVE.value)
    role_sec = Role(name=RoleEnum.SECURITY_REVIEWER.value)
    db_session.add_all([role_admin, role_mgr, role_rep, role_sec])
    await db_session.flush()

    # Create Admin User
    admin = User(
        email="admin@test.com",
        hashed_password=hash_password("Password123!"),
        first_name="Admin",
        last_name="Test",
        organization_id=org.id,
        is_active=True,
        is_superuser=True,
        roles=[role_admin],
    )
    # Create Sales Rep User
    sales_rep = User(
        email="rep@test.com",
        hashed_password=hash_password("Password123!"),
        first_name="Rep",
        last_name="Test",
        organization_id=org.id,
        is_active=True,
        roles=[role_rep],
    )
    # Create Sales Manager User
    sales_mgr = User(
        email="manager@test.com",
        hashed_password=hash_password("Password123!"),
        first_name="Manager",
        last_name="Test",
        organization_id=org.id,
        is_active=True,
        roles=[role_mgr],
    )
    # Create Security Reviewer
    sec_rev = User(
        email="sec@test.com",
        hashed_password=hash_password("Password123!"),
        first_name="Sec",
        last_name="Test",
        organization_id=org.id,
        is_active=True,
        roles=[role_sec],
    )
    db_session.add_all([admin, sales_rep, sales_mgr, sec_rev])
    await db_session.commit()

    return {
        "org": org,
        "admin": admin,
        "sales_rep": sales_rep,
        "sales_mgr": sales_mgr,
        "sec_rev": sec_rev,
    }


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_token(seed_data):
    admin = seed_data["admin"]
    token, _ = create_access_token(
        user_id=admin.id,
        organization_id=admin.organization_id,
        roles=[RoleEnum.ADMINISTRATOR.value],
    )
    return token


@pytest.fixture
def rep_token(seed_data):
    rep = seed_data["sales_rep"]
    token, _ = create_access_token(
        user_id=rep.id,
        organization_id=rep.organization_id,
        roles=[RoleEnum.SALES_REPRESENTATIVE.value],
    )
    return token
