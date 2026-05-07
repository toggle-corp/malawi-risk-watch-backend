import typing

import strawberry
from rest_framework import serializers

from utils.common import to_camel_case, to_snake_case

from .types import CustomErrorType

ARRAY_NON_MEMBER_ERRORS = "nonMemberErrors"


def _recursive_dict(data: typing.Any) -> typing.Any:
    if isinstance(data, dict):
        return {key: _recursive_dict(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_recursive_dict(item) for item in data]
    if isinstance(data, (ArrayNestedErrorType, MutationCustomErrorType)):
        return dict(data)
    return data


@strawberry.type
class ArrayNestedErrorType:
    client_id: str
    messages: str | None
    object_errors: list[CustomErrorType | None] | None

    def keys(self) -> list[str]:
        return ["client_id", "messages", "object_errors"]

    def __getitem__(self, key: str) -> typing.Any:
        key = to_snake_case(key)
        attr_value = getattr(self, key)
        if key == "object_errors" and attr_value:
            return [_recursive_dict(each) for each in attr_value]
        return attr_value


@strawberry.type
class MutationCustomErrorType:
    field: str
    client_id: str | None = None
    messages: str | None
    object_errors: list[CustomErrorType | None] | None
    array_errors: list[ArrayNestedErrorType | None] | None
    pydantic_errors: list[CustomErrorType] | None = None

    DEFAULT_ERROR_MESSAGE: str = "Something unexpected has occurred. Please contact an admin."

    @staticmethod
    def generate_message(message: str = DEFAULT_ERROR_MESSAGE) -> CustomErrorType:
        return CustomErrorType(
            [
                dict(
                    field="nonFieldErrors",
                    messages=message,
                    object_errors=None,
                    array_errors=None,
                ),
            ],
        )

    def keys(self) -> list[str]:
        return ["field", "client_id", "messages", "object_errors", "array_errors", "pydantic_errors"]

    def __getitem__(self, key: str) -> typing.Any:
        key = to_snake_case(key)
        attr_value = getattr(self, key)
        if key == "array_errors" and attr_value:
            return [_recursive_dict(each) for each in attr_value]
        return attr_value


def _serializer_error_to_error_types(
    errors: dict[str, typing.Any],
    initial_data: dict[typing.Any, typing.Any] | None = None,
) -> list[typing.Any]:
    initial_data = initial_data or {}
    node_client_id = initial_data.get("client_id")
    error_types: list[MutationCustomErrorType] = []

    for field, value in errors.items():
        if isinstance(value, dict):
            err = MutationCustomErrorType(
                client_id=node_client_id,
                field=to_camel_case(field),
                object_errors=value,  # type: ignore[reportArgumentType]
                array_errors=None,
                messages=None,
            )
            error_types.append(err)
        elif isinstance(value, list):
            if isinstance(value[0], str):
                if isinstance(initial_data.get(field), list):
                    err = MutationCustomErrorType(
                        client_id=node_client_id,
                        field=to_camel_case(field),
                        array_errors=[
                            ArrayNestedErrorType(
                                client_id=ARRAY_NON_MEMBER_ERRORS,
                                messages="".join(str(msg) for msg in value),
                                object_errors=None,
                            ),
                        ],
                        messages=None,
                        object_errors=None,
                    )
                else:
                    err = MutationCustomErrorType(
                        client_id=node_client_id,
                        field=to_camel_case(field),
                        messages=", ".join(str(msg) for msg in value),
                        object_errors=None,
                        array_errors=None,
                    )
                error_types.append(err)
            elif isinstance(value[0], dict):
                array_errors = []
                for pos, array_item in enumerate(value):
                    if not array_item:
                        continue
                    array_client_id = initial_data[field][pos].get("client_id", f"NOT_FOUND_{pos}")
                    array_errors.append(
                        ArrayNestedErrorType(
                            client_id=array_client_id,
                            object_errors=_serializer_error_to_error_types(
                                array_item,
                                initial_data[field][pos],
                            ),
                            messages=None,
                        ),
                    )
                err = MutationCustomErrorType(
                    client_id=node_client_id,
                    field=to_camel_case(field),
                    array_errors=array_errors,
                    object_errors=None,
                    messages=None,
                )
                error_types.append(err)
        else:
            err = MutationCustomErrorType(
                field=to_camel_case(field),
                messages=" ".join(str(msg) for msg in value or []),
                array_errors=None,
                object_errors=None,
            )
            error_types.append(err)
    return error_types


def mutation_is_not_valid(serializer: serializers.Serializer) -> CustomErrorType | None:
    """Return a CustomErrorType if serializer is invalid, else None."""
    if not serializer.is_valid():
        errors = _serializer_error_to_error_types(serializer.errors, serializer.initial_data)  # type: ignore[reportArgumentType]
        return CustomErrorType([dict(each) for each in errors])
    return None
