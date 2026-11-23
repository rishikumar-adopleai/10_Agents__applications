"""User Business Logic Service."""

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ConflictError, NotFoundError
from backend.app.core.security import hash_password
from backend.app.models.identity import Role, User
from backend.app.repositories.user_repo import RoleRepository, UserRepository
from backend.app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.role_repo = RoleRepository(session)

    async def get_user_by_id(self, user_id: str) -> User:
        user = await self.user_repo.get_with_roles(user_id)
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found")
        return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        return await self.user_repo.get_by_email(email)

    async def list_users(
        self,
        organization_id: str,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> List[User]:
        return await self.user_repo.list_by_organization(
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            search=search,
        )

    async def count_users(self, organization_id: str) -> int:
        return await self.user_repo.count(organization_id=organization_id)

    async def create_user(self, user_in: UserCreate, organization_id: str) -> User:
        # Check existing email
        existing = await self.user_repo.get_by_email(user_in.email)
        if existing:
            raise ConflictError(f"User with email '{user_in.email}' already exists")

        # Resolve roles
        roles: List[Role] = []
        for role_name in user_in.role_names:
            role = await self.role_repo.get_by_name(role_name.value)
            if not role:
                # auto-create role if not initialized
                role = await self.role_repo.create(
                    {"name": role_name.value, "description": f"{role_name.value} role"}
                )
            roles.append(role)

        new_user = User(
            email=user_in.email.lower().strip(),
            hashed_password=hash_password(user_in.password),
            first_name=user_in.first_name.strip(),
            last_name=user_in.last_name.strip(),
            is_active=user_in.is_active,
            organization_id=organization_id,
            roles=roles,
        )
        await self.user_repo.create(new_user)
        return await self.get_user_by_id(new_user.id)

    async def update_user(self, user_id: str, user_in: UserUpdate) -> User:
        user = await self.get_user_by_id(user_id)

        update_dict = {}
        if user_in.first_name is not None:
            update_dict["first_name"] = user_in.first_name.strip()
        if user_in.last_name is not None:
            update_dict["last_name"] = user_in.last_name.strip()
        if user_in.is_active is not None:
            update_dict["is_active"] = user_in.is_active
        if user_in.password:
            update_dict["hashed_password"] = hash_password(user_in.password)

        if user_in.role_names is not None:
            roles = []
            for role_name in user_in.role_names:
                role = await self.role_repo.get_by_name(role_name.value)
                if not role:
                    role = await self.role_repo.create({"name": role_name.value})
                roles.append(role)
            user.roles = roles

        await self.user_repo.update(user, update_dict)
        return await self.get_user_by_id(user_id)

    async def delete_user(self, user_id: str) -> bool:
        user = await self.get_user_by_id(user_id)
        return await self.user_repo.delete(user.id)
