from __future__ import annotations

from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from sqlalchemy import Engine, StaticPool, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from litestar.testing import TestClient


@pytest.fixture
def data() -> list[dict[str, Any]]:
    return [{"title": "test", "done": False}]


@pytest.fixture()
def sqlite_engine() -> Engine:
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@pytest.fixture()
def aiosqlite_engine() -> Engine:
    return create_async_engine("sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def test_sqlalchemy_async_plugin_example(
    data: dict[str, Any], monkeypatch: MonkeyPatch, aiosqlite_engine: AsyncEngine
) -> None:
    from docs.examples.contrib.sqlalchemy.plugins import sqlalchemy_async_plugin_example

    monkeypatch.setattr(sqlalchemy_async_plugin_example.config, "engine_instance", aiosqlite_engine)

    with TestClient(sqlalchemy_async_plugin_example.app) as client:
        assert client.post("/", json=data[0]).json() == data


def test_sqlalchemy_sync_plugin_example(data: dict[str, Any], monkeypatch: MonkeyPatch, sqlite_engine: Engine) -> None:
    from docs.examples.contrib.sqlalchemy.plugins import sqlalchemy_sync_plugin_example

    monkeypatch.setattr(sqlalchemy_sync_plugin_example.config, "engine_instance", sqlite_engine)

    with TestClient(sqlalchemy_sync_plugin_example.app) as client:
        assert client.post("/", json=data[0]).json() == data


def test_sqlalchemy_async_init_plugin_example(
    data: dict[str, Any], monkeypatch: MonkeyPatch, aiosqlite_engine: AsyncEngine
) -> None:
    from docs.examples.contrib.sqlalchemy.plugins import sqlalchemy_async_init_plugin_example

    monkeypatch.setattr(sqlalchemy_async_init_plugin_example.config, "engine_instance", aiosqlite_engine)

    with TestClient(sqlalchemy_async_init_plugin_example.app) as client:
        assert client.post("/", json=data[0]).json() == data


def test_sqlalchemy_sync_init_plugin_example(
    data: dict[str, Any], monkeypatch: MonkeyPatch, sqlite_engine: Engine
) -> None:
    from docs.examples.contrib.sqlalchemy.plugins import sqlalchemy_sync_init_plugin_example

    monkeypatch.setattr(sqlalchemy_sync_init_plugin_example.config, "engine_instance", sqlite_engine)

    with TestClient(sqlalchemy_sync_init_plugin_example.app) as client:
        assert client.post("/", json=data[0]).json() == data


def test_sqlalchemy_async_init_plugin_dependencies(monkeypatch: MonkeyPatch) -> None:
    from docs.examples.contrib.sqlalchemy.plugins import sqlalchemy_async_dependencies

    monkeypatch.setattr(sqlalchemy_async_dependencies.config, "connection_string", "sqlite+aiosqlite://")

    with TestClient(sqlalchemy_async_dependencies.app) as client:
        assert client.post("/").json() == [1, 2]


def test_sqlalchemy_sync_init_plugin_dependencies(monkeypatch: MonkeyPatch) -> None:
    from docs.examples.contrib.sqlalchemy.plugins import sqlalchemy_sync_dependencies

    monkeypatch.setattr(sqlalchemy_sync_dependencies.config, "connection_string", "sqlite://")

    with TestClient(sqlalchemy_sync_dependencies.app) as client:
        assert client.post("/").json() == [1, 2]


def test_sqlalchemy_async_before_send_handler() -> None:
    from docs.examples.contrib.sqlalchemy.plugins.sqlalchemy_async_before_send_handler import app

    from litestar.contrib.sqlalchemy.plugins.init.config.asyncio import autocommit_before_send_handler

    assert autocommit_before_send_handler is app.before_send[0].ref.value


def test_sqlalchemy_sync_before_send_handler() -> None:
    from docs.examples.contrib.sqlalchemy.plugins.sqlalchemy_sync_before_send_handler import app

    from litestar.contrib.sqlalchemy.plugins.init.config.sync import autocommit_before_send_handler

    assert autocommit_before_send_handler is app.before_send[0].ref.value.func


def test_sqlalchemy_async_serialization_plugin(data: dict[str, Any]) -> None:
    from docs.examples.contrib.sqlalchemy.plugins.sqlalchemy_async_serialization_plugin import app

    with TestClient(app) as client:
        assert client.post("/", json=data[0]).json() == data


def test_sqlalchemy_sync_serialization_plugin(data: dict[str, Any]) -> None:
    from docs.examples.contrib.sqlalchemy.plugins.sqlalchemy_sync_serialization_plugin import app

    with TestClient(app) as client:
        assert client.post("/", json=data[0]).json() == data


def test_sqlalchemy_async_serialization_dto(data: dict[str, Any]) -> None:
    from docs.examples.contrib.sqlalchemy.plugins.sqlalchemy_async_serialization_dto import app

    with TestClient(app) as client:
        assert client.post("/", json=data[0]).json() == data


def test_sqlalchemy_async_serialization_plugin_marking_fields(data: dict[str, Any]) -> None:
    from docs.examples.contrib.sqlalchemy.plugins.sqlalchemy_async_serialization_plugin_marking_fields import app

    with TestClient(app) as client:
        assert client.post("/", json=data[0]).json() == data


def test_sqlalchemy_sync_serialization_plugin_marking_fields(data: dict[str, Any]) -> None:
    from docs.examples.contrib.sqlalchemy.plugins.sqlalchemy_sync_serialization_plugin_marking_fields import app

    with TestClient(app) as client:
        assert client.post("/", json=data[0]).json() == data
