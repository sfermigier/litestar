from types import ModuleType
from typing import Any, Callable, Iterable, List, Optional, Sequence, Union
from unittest.mock import MagicMock

import pytest
from typing_extensions import Annotated

from litestar import get
from litestar._signature import SignatureModel
from litestar.params import Body, Parameter
from litestar.status_codes import HTTP_200_OK, HTTP_204_NO_CONTENT
from litestar.testing import TestClient, create_test_client
from litestar.types import Empty
from litestar.types.helper_types import OptionalSequence
from litestar.utils.signature import ParsedSignature


def test_create_function_signature_model_parameter_parsing() -> None:
    @get()
    def my_fn(a: int, b: str, c: Optional[bytes], d: bytes = b"123", e: Optional[dict] = None) -> None:
        pass

    model = SignatureModel.create(
        dependency_name_set=set(),
        fn=my_fn.fn.value,
        data_dto=None,
        parsed_signature=ParsedSignature.from_fn(my_fn.fn.value, {}),
        type_decoders=[],
    )
    fields = model._fields
    assert fields["a"].annotation is int
    assert not fields["a"].is_optional
    assert fields["b"].annotation is str
    assert not fields["b"].is_optional
    assert fields["c"].annotation is Optional[bytes]
    assert fields["c"].is_optional
    assert fields["c"].default is Empty
    assert fields["d"].annotation is bytes
    assert fields["d"].default == b"123"
    assert fields["e"].annotation == Optional[dict]
    assert fields["e"].is_optional
    assert fields["e"].default is Empty


def test_create_function_signature_model_ignore_return_annotation() -> None:
    @get(path="/health", status_code=HTTP_204_NO_CONTENT)
    async def health_check() -> None:
        return None

    signature_model_type = SignatureModel.create(
        dependency_name_set=set(),
        fn=health_check.fn.value,
        data_dto=None,
        parsed_signature=ParsedSignature.from_fn(health_check.fn.value, {}),
        type_decoders=[],
    )
    assert signature_model_type().to_dict() == {}


def test_signature_model_resolves_forward_ref_annotations(create_module: Callable[[str], ModuleType]) -> None:
    module = create_module(
        """
from __future__ import annotations

from pydantic import BaseModel
from litestar import Litestar, get
from litestar.di import Provide

class Test(BaseModel):
    hello: str

async def get_dep() -> Test:
    return Test(hello="world")

@get("/", dependencies={"test": Provide(get_dep)})
def hello_world(test: Test) -> Test:
    return test

app = Litestar(route_handlers=[hello_world], openapi_config=None)
"""
    )
    with TestClient(app=module.app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"hello": "world"}


@pytest.mark.parametrize(("query", "exp"), [("?a=1&a=2&a=3", [1, 2, 3]), ("", None)])
def test_parse_optional_sequence_from_connection_kwargs(query: str, exp: Any) -> None:
    @get("/")
    def test(a: Optional[List[int]] = Parameter(query="a", default=None, required=False)) -> Optional[List[int]]:
        return a

    with create_test_client(route_handlers=[test]) as client:
        response = client.get(f"/{query}")
        assert response.status_code == HTTP_200_OK, response.json()
        assert response.json() == exp


def test_field_definition_is_non_string_iterable() -> None:
    def fn(a: Iterable[int], b: Optional[Iterable[int]]) -> None:
        pass

    model = SignatureModel.create(
        dependency_name_set=set(),
        fn=fn,
        data_dto=None,
        parsed_signature=ParsedSignature.from_fn(fn, {}),
        type_decoders=[],
    )

    assert model._fields["a"].is_non_string_iterable
    assert model._fields["b"].is_non_string_iterable


def test_field_definition_is_non_string_sequence() -> None:
    def fn(a: Sequence[int], b: OptionalSequence[int]) -> None:
        pass

    model = SignatureModel.create(
        dependency_name_set=set(),
        fn=fn,
        data_dto=None,
        parsed_signature=ParsedSignature.from_fn(fn, signature_namespace={}),
        type_decoders=[],
    )

    assert model._fields["a"].is_non_string_sequence
    assert model._fields["b"].is_non_string_sequence


@pytest.mark.parametrize("query,expected", [("1", True), ("true", True), ("0", False), ("false", False)])
def test_query_param_bool(query: str, expected: bool) -> None:
    mock = MagicMock()

    @get("/")
    def handler(param: bool) -> None:
        mock(param)

    with create_test_client(route_handlers=[handler]) as client:
        response = client.get(f"/?param={query}")
        assert response.status_code == HTTP_200_OK, response.json()
        mock.assert_called_once_with(expected)


def test_union_constraint_handling() -> None:
    mock = MagicMock()

    @get("/")
    def handler(param: Annotated[Union[str, List[str]], Body(max_length=3, max_items=3)]) -> None:
        mock(param)

    with create_test_client([handler]) as client:
        response = client.get("/?param=foo")

    assert response.status_code == 200
    mock.assert_called_once_with("foo")
