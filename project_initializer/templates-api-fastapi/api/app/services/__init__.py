"""
Services Package
================

This package contains business logic services that orchestrate operations
between repositories, external APIs, and other services.

File Structure
--------------
services/
├── __init__.py           # This file - exports service classes
├── base.py               # Base service class (optional)
└── <domain>_service.py   # Domain-specific services

Service Layer Responsibilities
------------------------------
- Business logic and validation
- Orchestrating repository operations
- External API integrations
- Event publishing
- Transaction management
- Caching strategies

Service Pattern
---------------
```python
# services/user_service.py
from typing import Optional, Sequence
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.repositories.user_repository import UserRepository
from app.core.security import get_password_hash, verify_password
from app.core.exceptions import NotFoundError, ConflictError


class UserService:
    \"\"\"
    Service for user-related business logic.

    Handles:
    - User CRUD with business rules
    - Password hashing
    - Email uniqueness validation
    - User authentication
    \"\"\"

    def __init__(self, session: Session):
        self.session = session
        self.repository = UserRepository(session)

    def get(self, user_id: str) -> Optional[User]:
        \"\"\"Get user by ID.\"\"\"
        return self.repository.get(user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        \"\"\"Get user by email.\"\"\"
        return self.repository.get_by_email(email)

    def get_multi(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> Sequence[User]:
        \"\"\"Get paginated list of users.\"\"\"
        return self.repository.get_multi(skip=skip, limit=limit)

    def create(self, user_in: UserCreate) -> User:
        \"\"\"
        Create a new user.

        Raises:
            ConflictError: If email already exists
        \"\"\"
        existing = self.repository.get_by_email(user_in.email)
        if existing:
            raise ConflictError(f"Email {user_in.email} already registered")

        user_data = user_in.model_dump()
        user_data["hashed_password"] = get_password_hash(user_data.pop("password"))

        user = User(**user_data)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)

        return user

    def update(
        self,
        user_id: str,
        user_in: UserUpdate
    ) -> User:
        \"\"\"
        Update an existing user.

        Raises:
            NotFoundError: If user not found
            ConflictError: If new email already exists
        \"\"\"
        user = self.repository.get(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")

        update_data = user_in.model_dump(exclude_unset=True)

        if "email" in update_data and update_data["email"] != user.email:
            existing = self.repository.get_by_email(update_data["email"])
            if existing:
                raise ConflictError(f"Email {update_data['email']} already registered")

        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(
                update_data.pop("password")
            )

        for field, value in update_data.items():
            setattr(user, field, value)

        self.session.commit()
        self.session.refresh(user)

        return user

    def delete(self, user_id: str) -> bool:
        \"\"\"
        Delete a user.

        Raises:
            NotFoundError: If user not found
        \"\"\"
        user = self.repository.get(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")

        self.session.delete(user)
        self.session.commit()
        return True

    def authenticate(
        self,
        email: str,
        password: str
    ) -> Optional[User]:
        \"\"\"
        Authenticate user by email and password.

        Returns:
            User if authentication successful, None otherwise
        \"\"\"
        user = self.repository.get_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
```

Using Services in Routes
------------------------
```python
# api/v1/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserResponse
from app.core.exceptions import NotFoundError, ConflictError

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
):
    service = UserService(db)
    try:
        return service.create(user_in)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
```

Best Practices
--------------
1. **Business Logic Only**: Keep HTTP/API concerns in routes
2. **Transaction Boundaries**: Services control commit/rollback
3. **Repository Composition**: Services can use multiple repositories
4. **Exception Handling**: Raise domain exceptions, not HTTP exceptions
5. **Dependency Injection**: Inject session/repos via constructor
6. **Synchronous Operations**: Use synchronous SQLAlchemy with psycopg2
7. **Single Responsibility**: One service per domain/aggregate
8. **Testing**: Services should be easily testable with mocked repos
9. **Caching**: Implement caching strategies in services
10. **Logging**: Log important business operations
"""

# Import and export your services here:
# from app.services.user_service import UserService
# from app.services.auth_service import AuthService
from app.services.chatbot_service import ChatbotService

__all__ = [
    # "UserService",
    # "AuthService",
    "ChatbotService",
]
