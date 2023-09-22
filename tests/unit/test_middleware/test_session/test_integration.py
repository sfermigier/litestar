from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, SecretStr

from litestar import Request, get, post
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.middleware.session.server_side import (
    ServerSideSessionBackend,
    ServerSideSessionConfig,
)
from litestar.security.session_auth import SessionAuth
from litestar.status_codes import HTTP_204_NO_CONTENT
from litestar.stores.memory import MemoryStore
from litestar.testing import create_test_client


class User(BaseModel):
    id: UUID
    name: str
    email: EmailStr


class UserLoginPayload(BaseModel):
    email: EmailStr
    password: SecretStr


MOCK_DB: Dict[str, User] = {}
memory_store = MemoryStore()


async def retrieve_user_handler(
    session: Dict[str, Any], connection: "ASGIConnection[Any, Any, Any, Any]"
) -> Optional[User]:
    return MOCK_DB.get(user_id) if (user_id := session.get("user_id")) else None


@post("/login")
async def login(data: UserLoginPayload, request: "Request[Any, Any, Any]") -> User:
    user_id_bytes = await memory_store.get(data.email)

    if not user_id_bytes:
        raise NotAuthorizedException

    user_id = user_id_bytes.decode("utf-8")
    request.set_session({"user_id": user_id})
    return MOCK_DB[user_id]


@get("/user", sync_to_thread=False)
def get_user(request: Request[User, Dict[Literal["user_id"], str], Any]) -> Any:
    return request.user


session_auth = SessionAuth[User, ServerSideSessionBackend](
    retrieve_user_handler=retrieve_user_handler,
    session_backend_config=ServerSideSessionConfig(),
    exclude=["/login", "/schema"],
)


def test_options_request_with_session_auth() -> None:
    with create_test_client(
        route_handlers=[login, get_user],
        on_app_init=[session_auth.on_app_init],
    ) as client:
        response = client.options(get_user.paths.pop())
        assert response.status_code == HTTP_204_NO_CONTENT
