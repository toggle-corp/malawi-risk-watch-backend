import typing
from dataclasses import Field, is_dataclass

import strawberry


class DataclassInstance(typing.Protocol):
    __dataclass_fields__: typing.ClassVar[dict[str, Field[typing.Any]]]


InputDataType = DataclassInstance | tuple[typing.Any] | list[typing.Any] | typing.Any


def parse_input_data(
    data: InputDataType,
    dataclass_transformer: typing.Callable[[DataclassInstance], tuple[bool, InputDataType]] | None = None,
) -> typing.Any:
    """Convert a Strawberry input object into a plain dict, stripping UNSET values.

    strawberry.asdict doesn't handle nested objects or strawberry.UNSET correctly,
    so we recurse manually.
    """
    if type(data) is tuple:
        return [item for item in (parse_input_data(d, dataclass_transformer) for d in data) if item is not None]

    if type(data) is list:
        return [item for item in (parse_input_data(d, dataclass_transformer) for d in data) if item is not None]

    if not is_dataclass(data) or isinstance(data, type):
        return data

    if dataclass_transformer:
        handled, update = dataclass_transformer(data)
        if handled:
            return parse_input_data(update, dataclass_transformer)

    native_dict = {}
    for key, value in data.__dict__.items():
        if value == strawberry.UNSET:
            continue
        native_dict[key] = parse_input_data(value, dataclass_transformer)
    return native_dict
