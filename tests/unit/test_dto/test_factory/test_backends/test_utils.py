from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

import pytest
from msgspec import Struct

from litestar.dto import DTOField
from litestar.dto._backend import (
    _create_transfer_model_type_annotation,
    _should_mark_private,
    _transfer_nested_union_type_data,
)
from litestar.dto._types import (
    CollectionType,
    CompositeType,
    MappingType,
    NestedFieldInfo,
    SimpleType,
    TupleType,
    UnionType,
)
from litestar.dto.data_structures import DTOFieldDefinition
from litestar.typing import FieldDefinition


@dataclass
class DataModel:
    a: int
    b: str


class TransferModel(Struct):
    a: int
    b: str


def test_transfer_nested_union_type_data_raises_runtime_error_for_complex_union() -> None:
    transfer_type = UnionType(
        field_definition=FieldDefinition.from_annotation(Union[List[DataModel], int]),
        inner_types=(
            CollectionType(
                field_definition=FieldDefinition.from_annotation(List[DataModel]),
                inner_type=SimpleType(
                    field_definition=FieldDefinition.from_annotation(DataModel),
                    nested_field_info=NestedFieldInfo(model=TransferModel, field_definitions=()),
                ),
                has_nested=True,
            ),
            SimpleType(field_definition=FieldDefinition.from_annotation(int), nested_field_info=None),
        ),
        has_nested=True,
    )
    with pytest.raises(RuntimeError):
        _transfer_nested_union_type_data(
            transfer_type=transfer_type,
            is_data_field=True,
            source_value=1,
            override_serialization_name=True,
        )


def test_create_transfer_model_type_annotation_simple_type_without_nested_field_info() -> None:
    transfer_type = SimpleType(field_definition=FieldDefinition.from_annotation(int), nested_field_info=None)
    annotation = _create_transfer_model_type_annotation(transfer_type=transfer_type)
    assert annotation == int


def test_create_transfer_model_type_annotation_simple_type_with_nested_field_info() -> None:
    transfer_type = SimpleType(
        field_definition=FieldDefinition.from_annotation(DataModel),
        nested_field_info=NestedFieldInfo(model=TransferModel, field_definitions=()),
    )
    annotation = _create_transfer_model_type_annotation(transfer_type=transfer_type)
    assert annotation == TransferModel


def test_create_transfer_model_type_annotation_collection_type_not_nested() -> None:
    transfer_type = CollectionType(
        field_definition=FieldDefinition.from_annotation(List[int]),
        inner_type=SimpleType(field_definition=FieldDefinition.from_annotation(int), nested_field_info=None),
        has_nested=False,
    )
    annotation = _create_transfer_model_type_annotation(transfer_type=transfer_type)
    assert annotation == List[int]


def test_create_transfer_model_type_annotation_collection_type_nested() -> None:
    transfer_type = CollectionType(
        field_definition=FieldDefinition.from_annotation(List[DataModel]),
        inner_type=SimpleType(
            field_definition=FieldDefinition.from_annotation(DataModel),
            nested_field_info=NestedFieldInfo(model=TransferModel, field_definitions=()),
        ),
        has_nested=True,
    )
    annotation = _create_transfer_model_type_annotation(transfer_type=transfer_type)
    assert annotation == List[TransferModel]


def test_create_transfer_model_type_annotation_mapping_type_not_nested() -> None:
    transfer_type = MappingType(
        field_definition=FieldDefinition.from_annotation(Dict[str, int]),
        key_type=SimpleType(field_definition=FieldDefinition.from_annotation(str), nested_field_info=None),
        value_type=SimpleType(field_definition=FieldDefinition.from_annotation(int), nested_field_info=None),
        has_nested=False,
    )
    annotation = _create_transfer_model_type_annotation(transfer_type=transfer_type)
    assert annotation == Dict[str, int]


def test_create_transfer_model_type_annotation_mapping_type_nested() -> None:
    transfer_type = MappingType(
        field_definition=FieldDefinition.from_annotation(Dict[str, DataModel]),
        key_type=SimpleType(field_definition=FieldDefinition.from_annotation(str), nested_field_info=None),
        value_type=SimpleType(
            field_definition=FieldDefinition.from_annotation(DataModel),
            nested_field_info=NestedFieldInfo(model=TransferModel, field_definitions=()),
        ),
        has_nested=True,
    )
    annotation = _create_transfer_model_type_annotation(transfer_type=transfer_type)
    assert annotation == Dict[str, TransferModel]


def test_create_transfer_model_type_annotation_tuple_type_not_nested() -> None:
    transfer_type = TupleType(
        field_definition=FieldDefinition.from_annotation(Tuple[str, int]),
        inner_types=(
            SimpleType(field_definition=FieldDefinition.from_annotation(str), nested_field_info=None),
            SimpleType(field_definition=FieldDefinition.from_annotation(int), nested_field_info=None),
        ),
        has_nested=False,
    )
    annotation = _create_transfer_model_type_annotation(transfer_type=transfer_type)
    assert annotation == Tuple[str, int]


def test_create_transfer_model_type_annotation_tuple_type_nested() -> None:
    transfer_type = TupleType(
        field_definition=FieldDefinition.from_annotation(Tuple[str, DataModel]),
        inner_types=(
            SimpleType(field_definition=FieldDefinition.from_annotation(str), nested_field_info=None),
            SimpleType(
                field_definition=FieldDefinition.from_annotation(DataModel),
                nested_field_info=NestedFieldInfo(model=TransferModel, field_definitions=()),
            ),
        ),
        has_nested=True,
    )
    annotation = _create_transfer_model_type_annotation(transfer_type=transfer_type)
    assert annotation == Tuple[str, TransferModel]


def test_create_transfer_model_type_annotation_unexpected_transfer_type() -> None:
    transfer_type = CompositeType(field_definition=FieldDefinition.from_annotation(Union[str, int]), has_nested=False)
    with pytest.raises(RuntimeError):
        _create_transfer_model_type_annotation(transfer_type=transfer_type)


def test_should_mark_private_underscore_fields_private_true() -> None:
    assert (
        _should_mark_private(
            DTOFieldDefinition.from_field_definition(
                field_definition=FieldDefinition.from_kwarg(annotation=int, name="a", default=1),
                model_name="A",
                default_factory=None,
                dto_field=DTOField(),
            ),
            True,
        )
        is False
    )
    assert (
        _should_mark_private(
            DTOFieldDefinition.from_field_definition(
                field_definition=FieldDefinition.from_kwarg(annotation=int, name="_a", default=1),
                model_name="A",
                default_factory=None,
                dto_field=DTOField(),
            ),
            True,
        )
        is True
    )
    assert (
        _should_mark_private(
            DTOFieldDefinition.from_field_definition(
                field_definition=FieldDefinition.from_kwarg(annotation=int, name="_a", default=1),
                model_name="A",
                default_factory=None,
                dto_field=DTOField(mark="read-only"),
            ),
            True,
        )
        is False
    )


def test_should_mark_private_underscore_fields_private_false() -> None:
    assert (
        _should_mark_private(
            DTOFieldDefinition.from_field_definition(
                field_definition=FieldDefinition.from_kwarg(annotation=int, name="a", default=1),
                model_name="A",
                default_factory=None,
                dto_field=DTOField(),
            ),
            False,
        )
        is False
    )
    assert (
        _should_mark_private(
            DTOFieldDefinition.from_field_definition(
                field_definition=FieldDefinition.from_kwarg(annotation=int, name="_a", default=1),
                model_name="A",
                default_factory=None,
                dto_field=DTOField(),
            ),
            False,
        )
        is False
    )
    assert (
        _should_mark_private(
            DTOFieldDefinition.from_field_definition(
                field_definition=FieldDefinition.from_kwarg(annotation=int, name="_a", default=1),
                model_name="A",
                default_factory=None,
                dto_field=DTOField(mark="read-only"),
            ),
            False,
        )
        is False
    )
