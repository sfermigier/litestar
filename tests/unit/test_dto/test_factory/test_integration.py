# ruff: noqa: UP007, UP006
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Generic, List, Optional, Sequence, TypeVar, cast
from unittest.mock import MagicMock
from uuid import UUID

import msgspec
import pytest
from msgspec import Struct
from pydantic import BaseModel
from typing_extensions import Annotated

from litestar import Controller, Response, get, patch, post
from litestar.connection.request import Request
from litestar.contrib.pydantic import PydanticDTO, _model_dump_json
from litestar.datastructures import UploadFile
from litestar.dto import DataclassDTO, DTOConfig, DTOData, MsgspecDTO, dto_field
from litestar.dto.types import RenameStrategy
from litestar.enums import MediaType, RequestEncodingType
from litestar.pagination import ClassicPagination, CursorPagination, OffsetPagination
from litestar.params import Body
from litestar.serialization import encode_json
from litestar.testing import create_test_client

if TYPE_CHECKING:
    from typing import Any


def test_url_encoded_form_data() -> None:
    @dataclass
    class User:
        name: str
        age: int
        read_only: str = field(default="read-only", metadata=dto_field("read-only"))

    @post(dto=DataclassDTO[User], signature_namespace={"User": User})
    def handler(data: User = Body(media_type=RequestEncodingType.URL_ENCODED)) -> User:
        return data

    with create_test_client(route_handlers=[handler]) as client:
        response = client.post(
            "/",
            content=b"id=1&name=John&age=42&read_only=whoops",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.json() == {"name": "John", "age": 42, "read_only": "read-only"}


async def test_multipart_encoded_form_data() -> None:
    @dataclass
    class Payload:
        file: UploadFile
        forbidden: UploadFile = field(
            default=UploadFile(content_type="text/plain", filename="forbidden", file_data=b"forbidden"),
            metadata=dto_field("read-only"),
        )

    @post(
        dto=DataclassDTO[Payload], return_dto=None, signature_namespace={"Payload": Payload}, media_type=MediaType.TEXT
    )
    async def handler(data: Payload = Body(media_type=RequestEncodingType.MULTI_PART)) -> bytes:
        return await data.forbidden.read()

    with create_test_client(route_handlers=[handler]) as client:
        response = client.post(
            "/",
            files={"file": b"abc123", "forbidden": b"123abc"},
        )
        assert response.content == b"forbidden"


def test_renamed_field() -> None:
    @dataclass
    class Foo:
        bar: str

    config = DTOConfig(rename_fields={"bar": "baz"})
    dto = DataclassDTO[Annotated[Foo, config]]

    @post(dto=dto, signature_namespace={"Foo": Foo})
    def handler(data: Foo) -> Foo:
        assert data.bar == "hello"
        return data

    with create_test_client(route_handlers=[handler]) as client:
        response = client.post("/", json={"baz": "hello"})
        assert response.json() == {"baz": "hello"}


@dataclass
class Spam:
    main_id: str = "spam-id"


@dataclass
class Fzop:
    bar: str = "hello"
    SPAM: str = "bye"
    spam_bar: str = "welcome"
    spam_model: Optional[Spam] = None


@pytest.mark.parametrize(
    "rename_strategy, instance, tested_fields, data",
    [
        ("upper", Fzop(bar="hi"), ["BAR"], {"BAR": "hi"}),
        ("lower", Fzop(SPAM="goodbye"), ["spam"], {"spam": "goodbye"}),
        (lambda x: x[::-1], Fzop(bar="h", SPAM="bye!"), ["rab", "MAPS"], {"rab": "h", "MAPS": "bye!"}),
        ("camel", Fzop(spam_bar="star"), ["spamBar"], {"spamBar": "star"}),
        ("pascal", Fzop(spam_bar="star"), ["SpamBar"], {"SpamBar": "star"}),
        ("camel", Fzop(spam_model=Spam()), ["spamModel"], {"spamModel": {"mainId": "spam-id"}}),
    ],
)
def test_fields_alias_generator(
    rename_strategy: RenameStrategy,
    instance: Fzop,
    tested_fields: list[str],
    data: dict[str, str],
) -> None:
    DataclassDTO._dto_backends = {}
    config = DTOConfig(rename_strategy=rename_strategy)
    dto = DataclassDTO[Annotated[Fzop, config]]

    @post(dto=dto, signature_namespace={"Foo": Fzop})
    def handler(data: Fzop) -> Fzop:
        assert data.bar == instance.bar
        assert data.SPAM == instance.SPAM
        return data

    with create_test_client(route_handlers=[handler]) as client:
        response = client.post("/", json=data)
        for f in tested_fields:
            assert response.json()[f] == data[f]


def test_dto_data_injection() -> None:
    @dataclass
    class Foo:
        bar: str

    @post(dto=DataclassDTO[Foo], return_dto=None, signature_namespace={"Foo": Foo})
    def handler(data: DTOData[Foo]) -> Foo:
        assert isinstance(data, DTOData)
        assert data.as_builtins() == {"bar": "hello"}
        assert isinstance(data.create_instance(), Foo)
        return data.create_instance()

    with create_test_client(route_handlers=[handler]) as client:
        response = client.post("/", json={"bar": "hello"})
        assert response.json() == {"bar": "hello"}


@dataclass
class NestedFoo:
    bar: str
    baz: str


@dataclass
class NestingBar:
    foo: NestedFoo


def test_dto_data_injection_with_nested_model() -> None:
    @post(dto=DataclassDTO[Annotated[NestingBar, DTOConfig(exclude={"foo.baz"})]], return_dto=None)
    def handler(data: DTOData[NestingBar]) -> Dict[str, Any]:
        assert isinstance(data, DTOData)
        return cast("dict[str, Any]", data.as_builtins())

    with create_test_client(
        route_handlers=[handler], signature_namespace={"Foo": NestedFoo, "NestingBar": NestingBar}
    ) as client:
        resp = client.post("/", json={"foo": {"bar": "hello"}})
        assert resp.status_code == 201
        assert resp.json() == {"foo": {"bar": "hello"}}


def test_dto_data_create_instance_nested_kwargs() -> None:
    @post(dto=DataclassDTO[Annotated[NestingBar, DTOConfig(exclude={"foo.baz"})]], return_dto=None)
    def handler(data: DTOData[NestingBar]) -> NestingBar:
        assert isinstance(data, DTOData)
        result = data.create_instance(foo__baz="world")
        assert result.foo.baz == "world"
        return result

    with create_test_client(
        route_handlers=[handler], signature_namespace={"NestedFoo": NestedFoo, "NestingBar": NestingBar}
    ) as client:
        response = client.post("/", json={"foo": {"bar": "hello"}})
        assert response.status_code == 201
        assert response.json() == {"foo": {"bar": "hello", "baz": "world"}}


@dataclass
class User:
    name: str
    age: int
    read_only: str = field(default="read-only", metadata=dto_field("read-only"))


def test_dto_data_with_url_encoded_form_data() -> None:
    @post(dto=DataclassDTO[User], signature_namespace={"User": User})
    def handler(data: DTOData[User] = Body(media_type=RequestEncodingType.URL_ENCODED)) -> User:
        return data.create_instance()

    with create_test_client(route_handlers=[handler]) as client:
        response = client.post(
            "/",
            content=b"id=1&name=John&age=42&read_only=whoops",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.json() == {"name": "John", "age": 42, "read_only": "read-only"}


RenamedBarT = TypeVar("RenamedBarT")


@dataclass
class GenericRenamedBar(Generic[RenamedBarT]):
    bar: str
    spam_bar: RenamedBarT
    foo_foo: str


@dataclass
class InnerBar:
    best_greeting: str


@dataclass
class RenamedBar(GenericRenamedBar[InnerBar]):
    pass


def test_dto_data_create_instance_renamed_fields() -> None:
    @post(
        dto=DataclassDTO[Annotated[RenamedBar, DTOConfig(exclude={"foo_foo"}, rename_strategy="camel")]],
        return_dto=DataclassDTO[Annotated[RenamedBar, DTOConfig(rename_strategy="camel")]],
    )
    def handler(data: DTOData[RenamedBar]) -> RenamedBar:
        assert isinstance(data, DTOData)
        result = data.create_instance(foo_foo="world")
        assert result.foo_foo == "world"
        assert result.spam_bar.best_greeting == "hello world"
        return result

    with create_test_client(
        route_handlers=[handler], signature_namespace={"NestedFoo": NestedFoo, "NestingBar": NestingBar}
    ) as client:
        response = client.post("/", json={"bar": "hello", "spamBar": {"bestGreeting": "hello world"}})
        assert response.status_code == 201
        assert response.json() == {"bar": "hello", "fooFoo": "world", "spamBar": {"bestGreeting": "hello world"}}


def test_dto_data_with_patch_request() -> None:
    class PatchDTO(DataclassDTO[User]):
        config = DTOConfig(partial=True)

    @patch(dto=PatchDTO, return_dto=None, signature_namespace={"User": User})
    def handler(data: DTOData[User]) -> User:
        return data.update_instance(User(name="John", age=42))

    with create_test_client(route_handlers=[handler]) as client:
        response = client.patch("/", json={"age": 41, "read_only": "whoops"})
        assert response.json() == {"name": "John", "age": 41, "read_only": "read-only"}


@dataclass
class UniqueModelName:
    id: int
    foo: str


def test_dto_openapi_with_unique_handler_names() -> None:
    @post(
        dto=DataclassDTO[Annotated[UniqueModelName, DTOConfig(exclude={"id"})]],
        return_dto=DataclassDTO[UniqueModelName],
        signature_namespace={"UniqueModelName": UniqueModelName},
    )
    def handler(data: UniqueModelName) -> UniqueModelName:
        return data

    with create_test_client(route_handlers=[handler]) as client:
        response = client.get("/schema/openapi.json")
        schemas = list(response.json()["components"]["schemas"].values())
        assert len(schemas) == 2
        assert schemas[0]["title"] == "HandlerUniqueModelNameRequestBody"
        assert schemas[1]["title"] == "HandlerUniqueModelNameResponseBody"


@dataclass
class SharedModelName:
    id: int
    foo: str


def test_dto_openapi_without_unique_handler_names() -> None:
    write_dto = DataclassDTO[Annotated[SharedModelName, DTOConfig(exclude={"id"})]]
    read_dto = DataclassDTO[SharedModelName]

    @post(dto=write_dto, return_dto=read_dto, signature_namespace={"UniqueModelName": SharedModelName})
    def handler(data: SharedModelName) -> SharedModelName:
        return data

    class MyController(Controller):
        path = "/sub-path"

        @post(dto=write_dto, return_dto=read_dto, signature_namespace={"SharedModelName": SharedModelName})
        def handler(self, data: SharedModelName) -> SharedModelName:
            return data

    with create_test_client(route_handlers=[handler, MyController]) as client:
        response = client.get("/schema/openapi.json")
        schemas = list(response.json()["components"]["schemas"].values())
        assert len(schemas) == 4
        assert schemas[0]["title"] == "HandlerSharedModelNameRequestBody"
        assert schemas[1]["title"] == "HandlerSharedModelNameResponseBody"
        assert (
            schemas[2]["title"]
            == "tests.unit.test_dto.test_factory.test_integration.test_dto_openapi_without_unique_handler_names.<locals>.MyController.handlerSharedModelNameRequestBody"
        )
        assert (
            schemas[3]["title"]
            == "tests.unit.test_dto.test_factory.test_integration.test_dto_openapi_without_unique_handler_names.<locals>.MyController.handlerSharedModelNameResponseBody"
        )


def test_url_encoded_form_data_patch_request() -> None:
    @dataclass
    class User:
        name: str
        age: int
        read_only: str = field(default="read-only", metadata=dto_field("read-only"))

    dto = DataclassDTO[Annotated[User, DTOConfig(partial=True)]]

    @post(dto=dto, return_dto=None, signature_namespace={"User": User, "dict": Dict})
    def handler(data: DTOData[User] = Body(media_type=RequestEncodingType.URL_ENCODED)) -> Dict[str, Any]:
        return data.as_builtins()  # type:ignore[no-any-return]

    with create_test_client(route_handlers=[handler]) as client:
        response = client.post(
            "/",
            content=b"name=John&read_only=whoops",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.json() == {"name": "John"}


def test_dto_with_generic_sequence_annotations() -> None:
    @dataclass
    class User:
        name: str
        age: int

    @post(dto=DataclassDTO[User], signature_namespace={"User": User})
    def handler(data: Sequence[User]) -> Sequence[User]:
        return data

    with create_test_client(route_handlers=[handler]) as client:
        response = client.post("/", json=[{"name": "John", "age": 42}])
        assert response.json() == [{"name": "John", "age": 42}]


def test_dto_private_fields() -> None:
    @dataclass
    class Foo:
        bar: str
        _baz: int

    mock = MagicMock()

    @post(dto=DataclassDTO[Foo], signature_namespace={"Foo": Foo})
    def handler(data: DTOData[Foo]) -> Foo:
        mock.received_data = data.as_builtins()
        return data.create_instance(_baz=42)

    with create_test_client(route_handlers=[handler]) as client:
        response = client.post("/", json={"bar": "hello", "_baz": "world"})
        assert response.status_code == 201
        assert response.json() == {"bar": "hello"}

    assert mock.received_data == {"bar": "hello"}


def test_dto_private_fields_disabled() -> None:
    @dataclass
    class Foo:
        bar: str
        _baz: int

    @post(
        dto=DataclassDTO[Annotated[Foo, DTOConfig(underscore_fields_private=False)]],
        signature_namespace={"Foo": Foo},
    )
    def handler(data: Foo) -> Foo:
        return data

    with create_test_client(route_handlers=[handler]) as client:
        response = client.post("/", json={"bar": "hello", "_baz": 42})
        assert response.status_code == 201
        assert response.json() == {"bar": "hello", "_baz": 42}


def test_dto_concrete_builtin_collection_types() -> None:
    @dataclass
    class Foo:
        bar: dict
        baz: list

    @post(
        dto=DataclassDTO[Annotated[Foo, DTOConfig(underscore_fields_private=False)]],
        signature_namespace={"Foo": Foo},
    )
    def handler(data: Foo) -> Foo:
        return data

    with create_test_client(route_handlers=[handler]) as client:
        response = client.post("/", json={"bar": {"a": 1, "b": [1, 2, 3]}, "baz": [4, 5, 6]})
        assert response.status_code == 201
        assert response.json() == {"bar": {"a": 1, "b": [1, 2, 3]}, "baz": [4, 5, 6]}


@dataclass
class PaginatedUser:
    name: str
    age: int


def test_dto_classic_pagination() -> None:
    @get(dto=DataclassDTO[Annotated[PaginatedUser, DTOConfig(exclude={"age"})]])
    def handler() -> ClassicPagination[PaginatedUser]:
        return ClassicPagination(
            items=[PaginatedUser(name="John", age=42), PaginatedUser(name="Jane", age=43)],
            page_size=2,
            current_page=1,
            total_pages=20,
        )

    with create_test_client(handler, signature_namespace={"PaginatedUser": PaginatedUser}) as client:
        response = client.get("/")
        assert response.json() == {
            "items": [{"name": "John"}, {"name": "Jane"}],
            "page_size": 2,
            "current_page": 1,
            "total_pages": 20,
        }


def test_dto_cursor_pagination() -> None:
    uuid = UUID("00000000-0000-0000-0000-000000000000")

    @get(dto=DataclassDTO[Annotated[PaginatedUser, DTOConfig(exclude={"age"})]])
    def handler() -> CursorPagination[UUID, PaginatedUser]:
        return CursorPagination(
            items=[PaginatedUser(name="John", age=42), PaginatedUser(name="Jane", age=43)],
            results_per_page=2,
            cursor=uuid,
        )

    with create_test_client(handler, signature_namespace={"PaginatedUser": PaginatedUser}) as client:
        response = client.get("/")
        assert response.json() == {
            "items": [{"name": "John"}, {"name": "Jane"}],
            "results_per_page": 2,
            "cursor": "00000000-0000-0000-0000-000000000000",
        }


def test_dto_offset_pagination() -> None:
    @get(dto=DataclassDTO[Annotated[PaginatedUser, DTOConfig(exclude={"age"})]])
    def handler() -> OffsetPagination[PaginatedUser]:
        return OffsetPagination(
            items=[PaginatedUser(name="John", age=42), PaginatedUser(name="Jane", age=43)],
            limit=2,
            offset=0,
            total=20,
        )

    with create_test_client(handler, signature_namespace={"PaginatedUser": PaginatedUser}) as client:
        response = client.get("/")
        assert response.json() == {
            "items": [{"name": "John"}, {"name": "Jane"}],
            "limit": 2,
            "offset": 0,
            "total": 20,
        }


T = TypeVar("T")
V = TypeVar("V")
K = TypeVar("K")


@dataclass
class Wrapped(Generic[T, V]):
    data: T
    other: V


def test_dto_generic_dataclass_wrapped_list_response() -> None:
    @get(dto=DataclassDTO[Annotated[PaginatedUser, DTOConfig(exclude={"age"})]])
    def handler() -> Wrapped[List[PaginatedUser], int]:
        return Wrapped(
            data=[PaginatedUser(name="John", age=42), PaginatedUser(name="Jane", age=43)],
            other=2,
        )

    with create_test_client(
        handler, signature_namespace={"PaginatedUser": PaginatedUser, "Wrapped": Wrapped}
    ) as client:
        response = client.get("/")
        assert response.json() == {"data": [{"name": "John"}, {"name": "Jane"}], "other": 2}


def test_dto_generic_dataclass_wrapped_scalar_response() -> None:
    @get(dto=DataclassDTO[Annotated[PaginatedUser, DTOConfig(exclude={"age"})]])
    def handler() -> Wrapped[PaginatedUser, int]:
        return Wrapped(
            data=PaginatedUser(name="John", age=42),
            other=2,
        )

    with create_test_client(handler) as client:
        response = client.get("/")
        assert response.json() == {"data": {"name": "John"}, "other": 2}


@dataclass
class WrappedWithDict(Generic[K, V, T]):
    data: T
    other: Dict[K, V]


def test_dto_generic_dataclass_wrapped_scalar_response_with_additional_mapping_data() -> None:
    @get(dto=DataclassDTO[Annotated[PaginatedUser, DTOConfig(exclude={"age"})]])
    def handler() -> WrappedWithDict[str, int, PaginatedUser]:
        return WrappedWithDict(
            data=PaginatedUser(name="John", age=42),
            other={"a": 1, "b": 2},
        )

    with create_test_client(handler, signature_namespace={"WrappedWithDict": WrappedWithDict}) as client:
        response = client.get("/")
        assert response.json() == {"data": {"name": "John"}, "other": {"a": 1, "b": 2}}


def test_dto_response_wrapped_scalar_return_type() -> None:
    @get(dto=DataclassDTO[Annotated[PaginatedUser, DTOConfig(exclude={"age"})]])
    def handler() -> Response[PaginatedUser]:
        return Response(content=PaginatedUser(name="John", age=42))

    with create_test_client(handler) as client:
        response = client.get("/")
        assert response.json() == {"name": "John"}


def test_dto_response_wrapped_collection_return_type() -> None:
    @get(dto=DataclassDTO[Annotated[PaginatedUser, DTOConfig(exclude={"age"})]])
    def handler() -> Response[List[PaginatedUser]]:
        return Response(content=[PaginatedUser(name="John", age=42), PaginatedUser(name="Jane", age=43)])

    with create_test_client(handler) as client:
        response = client.get("/")
        assert response.json() == [{"name": "John"}, {"name": "Jane"}]


def test_schema_required_fields_with_msgspec_dto() -> None:
    class MsgspecUser(Struct):
        age: int
        name: str

    class UserDTO(MsgspecDTO[MsgspecUser]):
        pass

    @post(dto=UserDTO, return_dto=None, signature_namespace={"MsgspecUser": MsgspecUser})
    def handler(data: MsgspecUser, request: Request) -> dict:
        schema = request.app.openapi_schema
        return schema.to_schema()

    with create_test_client(handler) as client:
        data = MsgspecUser(name="A", age=10)
        headers = {"Content-Type": "application/json; charset=utf-8"}
        received = client.post(
            "/",
            content=msgspec.json.encode(data),
            headers=headers,
        )
        required = next(iter(received.json()["components"]["schemas"].values()))["required"]
        assert len(required) == 2


def test_schema_required_fields_with_pydantic_dto() -> None:
    class PydanticUser(BaseModel):
        age: int
        name: str

    class UserDTO(PydanticDTO[PydanticUser]):
        pass

    @post(dto=UserDTO, return_dto=None, signature_namespace={"PydanticUser": PydanticUser})
    def handler(data: PydanticUser, request: Request) -> dict:
        schema = request.app.openapi_schema
        return schema.to_schema()

    with create_test_client(handler) as client:
        data = PydanticUser(name="A", age=10)
        headers = {"Content-Type": "application/json; charset=utf-8"}
        received = client.post(
            "/",
            content=_model_dump_json(data),
            headers=headers,
        )
        required = next(iter(received.json()["components"]["schemas"].values()))["required"]
        assert len(required) == 2


def test_schema_required_fields_with_dataclass_dto() -> None:
    @dataclass
    class DataclassUser:
        age: int
        name: str

    class UserDTO(DataclassDTO[DataclassUser]):
        pass

    @post(dto=UserDTO, return_dto=None, signature_namespace={"DataclassUser": DataclassUser})
    def handler(data: DataclassUser, request: Request) -> dict:
        schema = request.app.openapi_schema
        return schema.to_schema()

    with create_test_client(handler) as client:
        data = DataclassUser(name="A", age=10)
        headers = {"Content-Type": "application/json; charset=utf-8"}
        received = client.post(
            "/",
            content=msgspec.json.encode(data),
            headers=headers,
        )
        required = next(iter(received.json()["components"]["schemas"].values()))["required"]
        assert len(required) == 2


def test_schema_required_fields_with_msgspec_dto_and_default_fields() -> None:
    class MsgspecUser(Struct):
        age: int
        name: str = "A"

    class UserDTO(MsgspecDTO[MsgspecUser]):
        pass

    @post(dto=UserDTO, return_dto=None, signature_namespace={"MsgspecUser": MsgspecUser})
    def handler(data: MsgspecUser, request: Request) -> dict:
        schema = request.app.openapi_schema
        return schema.to_schema()

    with create_test_client(handler) as client:
        data = MsgspecUser(name="A", age=10)
        headers = {"Content-Type": "application/json; charset=utf-8"}
        received = client.post(
            "/",
            content=msgspec.json.encode(data),
            headers=headers,
        )
        required = next(iter(received.json()["components"]["schemas"].values()))["required"]
        assert required == ["age"]


X = TypeVar("X", bound=Struct)


class ClassicNameStyle(Struct):
    first_name: str
    surname: str


class BoundUser(Struct, Generic[X]):
    age: int
    data: X


class Superuser(BoundUser[ClassicNameStyle]):
    pass


def test_dto_with_msgspec_with_bound_generic_and_inherited_models() -> None:
    @post(dto=MsgspecDTO[Superuser])
    def handler(data: Superuser) -> Superuser:
        return data

    with create_test_client(
        handler,
        signature_namespace={"Superuser": Superuser, "BoundUser": BoundUser, "ClassicNameStyle": ClassicNameStyle},
    ) as client:
        data = Superuser(data=ClassicNameStyle(first_name="A", surname="B"), age=10)
        received = client.post(
            "/",
            content=encode_json(data),
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        assert msgspec.json.decode(received.content, type=Superuser) == data
