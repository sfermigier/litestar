import random
from datetime import timedelta
from typing import TYPE_CHECKING, Optional
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from litestar import Litestar, Request, get
from litestar.config.response_cache import CACHE_FOREVER, ResponseCacheConfig
from litestar.stores.base import Store
from litestar.stores.memory import MemoryStore
from litestar.testing import TestClient, create_test_client

if TYPE_CHECKING:
    from time_machine import Coordinates

    from litestar import Response


@pytest.fixture()
def mock() -> MagicMock:
    return MagicMock(return_value=str(random.random()))


def after_request_handler(response: "Response") -> "Response":
    response.headers["unique-identifier"] = str(uuid4())
    return response


@pytest.mark.parametrize("sync_to_thread", (True, False))
def test_default_cache_response(sync_to_thread: bool, mock: MagicMock) -> None:
    @get(
        "/cached",
        sync_to_thread=sync_to_thread,
        cache=True,
        type_encoders={int: str},  # test pickling issues. see https://github.com/litestar-org/litestar/issues/1096
    )
    def handler() -> str:
        return mock()  # type: ignore[no-any-return]

    with create_test_client([handler], after_request=after_request_handler) as client:
        first_response = client.get("/cached")
        second_response = client.get("/cached")

        first_response_identifier = first_response.headers["unique-identifier"]

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.headers["unique-identifier"] == first_response_identifier
        assert first_response.text == second_response.text
        assert mock.call_count == 1


def test_handler_expiration(mock: MagicMock, frozen_datetime: "Coordinates") -> None:
    @get("/cached-local", cache=10)
    async def handler() -> str:
        return mock()  # type: ignore[no-any-return]

    with create_test_client([handler], after_request=after_request_handler) as client:
        first_response = client.get("/cached-local")
        frozen_datetime.shift(delta=timedelta(seconds=5))
        second_response = client.get("/cached-local")
        assert first_response.headers["unique-identifier"] == second_response.headers["unique-identifier"]
        assert mock.call_count == 1

        frozen_datetime.shift(delta=timedelta(seconds=11))
        third_response = client.get("/cached-local")
        assert first_response.headers["unique-identifier"] != third_response.headers["unique-identifier"]
        assert mock.call_count == 2


def test_default_expiration(mock: MagicMock, frozen_datetime: "Coordinates") -> None:
    @get("/cached-default", cache=True)
    async def handler() -> str:
        return mock()  # type: ignore[no-any-return]

    with create_test_client(
        [handler], after_request=after_request_handler, response_cache_config=ResponseCacheConfig(default_expiration=1)
    ) as client:
        first_response = client.get("/cached-default")
        second_response = client.get("/cached-default")
        assert first_response.headers["unique-identifier"] == second_response.headers["unique-identifier"]
        assert mock.call_count == 1

        frozen_datetime.shift(delta=timedelta(seconds=1))
        third_response = client.get("/cached-default")
        assert first_response.headers["unique-identifier"] != third_response.headers["unique-identifier"]
        assert mock.call_count == 2


@pytest.mark.parametrize("expiration,expected_expiration", [(True, None), (10, 10)])
def test_default_expiration_none(
    memory_store: MemoryStore, expiration: int, expected_expiration: Optional[int]
) -> None:
    @get("/cached", cache=expiration)
    def handler() -> None:
        return None

    app = Litestar(
        [handler],
        stores={"response_cache": memory_store},
        response_cache_config=ResponseCacheConfig(default_expiration=None),
    )

    with TestClient(app) as client:
        client.get("/cached")

    if expected_expiration is None:
        assert memory_store._store["/cached"].expires_at is None
    else:
        assert memory_store._store["/cached"].expires_at


def test_cache_forever(memory_store: MemoryStore) -> None:
    @get("/cached", cache=CACHE_FOREVER)
    async def handler() -> None:
        return None

    app = Litestar([handler], stores={"response_cache": memory_store})

    with TestClient(app) as client:
        client.get("/cached")

    assert memory_store._store["/cached"].expires_at is None


@pytest.mark.parametrize("sync_to_thread", (True, False))
async def test_custom_cache_key(sync_to_thread: bool, anyio_backend: str, mock: MagicMock) -> None:
    def custom_cache_key_builder(request: Request) -> str:
        return f"{request.url.path}:::cached"

    @get("/cached", sync_to_thread=sync_to_thread, cache=True, cache_key_builder=custom_cache_key_builder)
    def handler() -> str:
        return mock()  # type: ignore[no-any-return]

    app = Litestar([handler])

    with TestClient(app) as client:
        client.get("/cached")
        store = app.stores.get("response_cache")
        assert await store.exists("/cached:::cached")


async def test_non_default_store_name(mock: MagicMock) -> None:
    @get(cache=True)
    def handler() -> str:
        return mock()  # type: ignore[no-any-return]

    app = Litestar([handler], response_cache_config=ResponseCacheConfig(store="some_store"))

    with TestClient(app=app) as client:
        response_one = client.get("/")
        assert response_one.status_code == 200
        assert response_one.text == mock.return_value

        response_two = client.get("/")
        assert response_two.status_code == 200
        assert response_two.text == mock.return_value

        assert mock.call_count == 1

    assert await app.stores.get("some_store").exists("/")


async def test_with_stores(store: Store, mock: MagicMock) -> None:
    @get(cache=True)
    def handler() -> str:
        return mock()  # type: ignore[no-any-return]

    app = Litestar([handler], stores={"response_cache": store})

    with TestClient(app=app) as client:
        response_one = client.get("/")
        assert response_one.status_code == 200
        assert response_one.text == mock.return_value

        response_two = client.get("/")
        assert response_two.status_code == 200
        assert response_two.text == mock.return_value

        assert mock.call_count == 1
