from __future__ import annotations

import enum
import typing as t
from functools import cached_property

import graphql
from graphql import GraphQLResolveInfo

from ..validators import DataValidatorCallable
from ..validators import ValidationError
from ..validators import ValueValidatorCallable


class Node(abc.ABC):
    _graphql_node: t.Any | None = None

    @abc.abstractmethod
    def _find_nodes(self) -> t.Iterable[str | Type]:
        pass

    @abc.abstractmethod
    def _apply_types(self, type_map: dict[str, NamedType]) -> None:
        pass

    @abc.abstractmethod
    def _make_graphql_node(self) -> t.Any:
        pass

    def _to_graphql(self) -> t.Any:
        if self._graphql_node is None:
            self._graphql_node = self._make_graphql_node()

        return self._graphql_node


class Type(Node, abc.ABC):  # noqa: B024
    @cached_property
    def non_null(self) -> NonNull:
        return NonNull(self)

    @cached_property
    def list(self) -> List:
        return List(self)


class NamedType(Type, abc.ABC):  # noqa: B024
    name: str

    def __init__(self, name: str, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self.name = name

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"


class ResolverCallable(t.Protocol):
    def __call__(
        self, parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        ...


def resolve_attr(parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any) -> t.Any:
    return getattr(parent, info.field_name)


def resolve_item(parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any) -> t.Any:
    return parent.get(info.field_name)


_VCT = t.TypeVar("_VCT")
_IT = t.TypeVar("_IT", "Argument", "InputObject")


class _BaseValidatorNode(Node, t.Generic[_VCT], abc.ABC):  # noqa: B024
    def __init__(self, validators: list[_VCT] | None = None, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)

        if validators is None:
            validators = []

        self.validators: list[_VCT] = validators

    def validator(self, f: _VCT) -> _VCT:
        self.validators.append(f)
        return f


class _DataValidatorNode(
    _BaseValidatorNode[DataValidatorCallable], t.Generic[_IT], abc.ABC
):
    @property
    @abc.abstractmethod
    def _items_to_validate(self) -> dict[str, _IT]:
        """A map of names to objects with a ``validators`` list.

        This is necessary since ``Field`` uses ``args`` and
        ``InputObject`` uses ``fields``.
        """
        pass

    def validate(self, info: GraphQLResolveInfo, data: dict[str, t.Any]) -> None:
        # Empty is top-level. Others are Argument/InputField names.
        errors: dict[str, list[t.Any]] = {"": []}

        for name, item in self._items_to_validate.items():
            if name not in data:
                continue

            try:
                item.validate(info, data[name], data)
            except ValidationError as e:
                errors[name] = e.message

        for f in self.validators:
            try:
                f(info, data)
            except ValidationError as e:
                if isinstance(e.message, dict):
                    for k, v in e.message.items():
                        if k not in errors:
                            errors[k] = []

                        if isinstance(v, list):
                            errors[k].extend(v)
                        else:
                            errors[k].append(v)
                elif isinstance(e.message, list):
                    errors[""].extend(e.message)
                else:
                    errors[""].append(e.message)

        if not errors[""]:
            del errors[""]

        if errors:
            raise ValidationError(errors)


def _validate_value(
    type: Type,
    validators: list[ValueValidatorCallable],
    info: GraphQLResolveInfo,
    value: t.Any,
    data: dict[str, t.Any],
) -> None:
    # This is defined outside _ValueValidatorNode.validate because of how it's
    # recursively called for nested lists of validators.
    errors = []

    # Unwrap non-null to get named type or list. If the unwrapped type is an
    # InputObject, it also has validation.
    if isinstance(type, NonNull):
        type = type.type

    if isinstance(type, InputObject):
        try:
            type.validate(info, value)
        except ValidationError as e:
            errors.append(e.message)

    nested_type = None

    for f in validators:
        # A list in the validator list means apply that sub-list of validators to each
        # item in the value.
        if isinstance(f, list):
            # Unwrap a list type to the next relevant type, either another list or a
            # named type. Only do this once, if there are multiple validator lists this
            # will be the same type for all of them.
            if nested_type is None:
                nested_type = type

                while isinstance(nested_type, Wrapping):
                    nested_type = nested_type.type

                    if isinstance(nested_type, List):
                        break

            list_errors = []

            # Call each sub-list validator for each item, recursively.
            for item in value:
                try:
                    _validate_value(nested_type, f, info, item, data)
                except ValidationError as e:
                    if isinstance(e.message, list):
                        list_errors.extend(e.message)
                    else:
                        list_errors.append(e.message)
                else:
                    # Placeholder for items that had no errors.
                    list_errors.append(None)

            # If at least one item had errors (not None), validation failed.
            if any(list_errors):
                errors.append(list_errors)

        # A function in the validator list. Nested lists will eventually end up here.
        else:
            try:
                f(info, value, data)
            except ValidationError as e:
                if isinstance(e.message, list):
                    errors.extend(e.message)
                else:
                    errors.append(e.message)

    if errors:
        raise ValidationError(errors)


class _ValueValidatorNode(_BaseValidatorNode[ValueValidatorCallable]):
    """Implement ``validate`` for item nodes. Their validators take a value and the full
    data.
    """

    type: Type

    def validate(
        self, info: GraphQLResolveInfo, value: t.Any, data: dict[str, t.Any]
    ) -> None:
        """Validate a given value by calling each validator in :attr:`validators` on
        this item's value.

        :param info: GraphQL resolve info. Mainly useful for ``info.context``.
        :param value: The value being validated.
        :param data: All args/input fields being validated, of which this object is one.
        """
        _validate_value(self.type, self.validators, info, value, data)


_OT = t.TypeVar("_OT", bound=graphql.GraphQLNamedType)


class _BaseObject(NamedType, t.Generic[_OT]):
    _graphql_class: t.ClassVar[type[_OT]]

    def __init__(
        self,
        name: str,
        fields: dict[str, str | Type | Field] | None = None,
        interfaces: list[str | Interface] | None = None,
        description: str | None = None,
    ) -> None:
        super().__init__(name=name)
        self.fields: dict[str, Field] = _expand_type_shortcut(fields, Field)

        if interfaces is None:
            interfaces = []

        self.interfaces: list[str | Interface] = interfaces
        self.description = description

    def field(
        self,
        name: str,
        type: str | Type,
        args: dict[str, Argument] | None = None,
        validators: list[DataValidatorCallable] | None = None,
        description: str | None = None,
        deprecation: str | None = None,
    ) -> t.Callable[[ResolverCallable], ResolverCallable]:
        def decorator(f: ResolverCallable) -> ResolverCallable:
            self.fields[name] = Field(
                type=type,
                args=args,
                validators=validators,
                resolve=f,
                description=description,
                deprecation=deprecation,
            )
            return f

        return decorator

    def _find_nodes(self) -> t.Iterator[str | Type]:
        yield from self.fields.values()
        yield from self.interfaces

    def _apply_types(self, type_map: dict[str, NamedType]) -> None:
        _list_to_types(self.interfaces, type_map)

    def _make_graphql_node(self) -> _OT:
        return self._graphql_class(
            name=self.name,
            fields=lambda: {k: v._to_graphql() for k, v in self.fields.items()},
            interfaces=lambda: [v._to_graphql() for v in self.interfaces],
            description=self.description,
        )


class Object(_BaseObject[graphql.GraphQLObjectType]):
    _graphql_class = graphql.GraphQLObjectType


class Interface(_BaseObject[graphql.GraphQLInterfaceType]):
    _graphql_class = graphql.GraphQLInterfaceType


class Union(NamedType):
    def __init__(
        self,
        name: str,
        types: dict[type[t.Any], str | Object] | None = None,
        description: str | None = None,
    ) -> None:
        super().__init__(name=name)
        self.types: list[str | Object] = []
        self.py_to_name: dict[type[t.Any], str] = {}
        self.description = description

        if types is not None:
            for py_type, gql_type in types.items():
                self.add_type(py_type, gql_type)

    def add_type(
        self, py_type: type[t.Any], gql_type: str | Object | None = None
    ) -> None:
        if gql_type is None:
            gql_type = py_type.__name__

        self.types.append(gql_type)

        if isinstance(gql_type, Object):
            gql_name = gql_type.name
        else:
            gql_name = gql_type

        self.py_to_name[py_type] = gql_name

    def resolve_type(
        self, value: t.Any, info: GraphQLResolveInfo, node: graphql.GraphQLUnionType
    ) -> str:
        return self.py_to_name[type(value)]

    def _find_nodes(self) -> t.Iterator[str | Node]:
        yield from self.types

    def _apply_types(self, type_map: dict[str, NamedType]) -> None:
        _list_to_types(self.types, type_map)

    def _make_graphql_node(self) -> graphql.GraphQLUnionType:
        return graphql.GraphQLUnionType(
            name=self.name,
            types=lambda: [o._to_graphql() for o in self.types],
            resolve_type=self.resolve_type,
            description=self.description,
        )


class Field(_DataValidatorNode["Argument"]):
    def __init__(
        self,
        type: str | Type,
        args: dict[str, str | Type | Argument] | None = None,
        validators: list[DataValidatorCallable] | None = None,
        resolve: ResolverCallable = resolve_attr,
        description: str | None = None,
        deprecation: str | None = None,
    ) -> None:
        super().__init__(validators=validators)
        self.type = type
        self.args: dict[str, Argument] = _expand_type_shortcut(args, Argument)
        self._pre_resolve: ResolverCallable | None = None
        self._resolve = resolve
        self.description = description
        self.deprecation = deprecation

    def pre_resolver(self, f: ResolverCallable) -> ResolverCallable:
        self._pre_resolve = f
        return f

    def resolver(self, f: ResolverCallable) -> ResolverCallable:
        self._resolve = f
        return f

    def resolve(self, parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any):
        try:
            if self._pre_resolve is not None:
                self._pre_resolve(parent, info, **kwargs)

            self.validate(info, kwargs)
            return self._resolve(parent, info, **kwargs)
        except ValidationError as e:
            if isinstance(e.message, str):
                m = {"": [e.message]}
            elif isinstance(e.message, list):
                m = {"": e.message}
            else:
                m = e.message

            raise graphql.GraphQLError(
                "magql argument validation", original_error=e, extensions=m
            ) from None

    @property
    def _items_to_validate(self) -> dict[str, Argument]:
        return self.args

    def _find_nodes(self):
        yield self.type
        yield from self.args.values()

    def _apply_types(self, type_map: dict[str, NamedType]) -> None:
        self.type = _to_type(self.type, type_map)

    def _make_graphql_node(self) -> graphql.GraphQLField:
        return graphql.GraphQLField(
            type_=self.type._to_graphql(),
            args={name: arg._to_graphql() for name, arg in self.args.items()},
            resolve=self.resolve,
            description=self.description,
            deprecation_reason=self.deprecation,
        )


class Argument(_ValueValidatorNode):
    def __init__(
        self,
        type: str | Type,
        default: t.Any = graphql.Undefined,
        validators: list[ValueValidatorCallable] | None = None,
        description: str | None = None,
        deprecation: str | None = None,
    ) -> None:
        super().__init__(validators=validators)
        self.type = type
        self.default = default
        self.description = description
        self.deprecation = deprecation

    def _find_nodes(self) -> t.Iterable[str | Type]:
        yield self.type

    def _apply_types(self, type_map: dict[str, NamedType]) -> None:
        self.type = _to_type(self.type, type_map)

    def _make_graphql_node(self) -> graphql.GraphQLArgument:
        return graphql.GraphQLArgument(
            type_=self.type._to_graphql(),
            default_value=self.default,
            description=self.description,
            deprecation_reason=self.deprecation,
        )


class InputObject(NamedType, _DataValidatorNode["InputField"]):
    def __init__(
        self,
        name: str,
        fields: dict[str, str | Type | InputField] | None = None,
        validators: list[DataValidatorCallable] | None = None,
        description: str | None = None,
    ) -> None:
        super().__init__(name=name, validators=validators)
        self.fields: dict[str, InputField] = _expand_type_shortcut(fields, InputField)
        self.description = description

    @property
    def _items_to_validate(self) -> dict[str, InputField]:
        return self.fields

    def _find_nodes(self) -> t.Iterator[str | Type]:
        yield from self.fields.values()

    def _apply_types(self, type_map: dict[str, NamedType]) -> None:
        pass

    def _make_graphql_node(self) -> graphql.GraphQLInputObjectType:
        return graphql.GraphQLInputObjectType(
            name=self.name,
            fields=lambda: {k: v._to_graphql() for k, v in self.fields.items()},
            description=self.description,
        )


class InputField(_ValueValidatorNode):
    def __init__(
        self,
        type: str | Type,
        default: t.Any = graphql.Undefined,
        validators: list[ValueValidatorCallable] | None = None,
        description: str | None = None,
        deprecation: str | None = None,
    ) -> None:
        super().__init__(validators=validators)
        self.type = type
        self.default = default
        self.description = description
        self.deprecation = deprecation

    def _find_nodes(self) -> t.Iterable[str | Type]:
        yield self.type

    def _apply_types(self, type_map: dict[str, NamedType]) -> None:
        self.type = _to_type(self.type, type_map)

    def _make_graphql_node(self) -> graphql.GraphQLInputField:
        return graphql.GraphQLInputField(
            type_=self.type._to_graphql(),
            default_value=self.default,
            description=self.description,
            deprecation_reason=self.deprecation,
        )


class Enum(NamedType):
    def __init__(
        self,
        name: str,
        values: t.Union[list[str], dict[str, t.Any], type[enum.Enum]],
        description: str | None = None,
    ) -> None:
        super().__init__(name=name)

        if isinstance(values, list):
            values = {v: v for v in values}

        # GraphQL maps enum names to values, map to objects instead.
        elif isinstance(values, enum.EnumMeta):
            values = values.__members__

        self.values: dict[str, t.Any] = values
        self.description = description

    def _find_nodes(self) -> t.Iterator[str | Type]:
        yield from ()

    def _apply_types(self, type_map: dict[str, NamedType]) -> None:
        pass

    def _make_graphql_node(self) -> graphql.GraphQLEnumType:
        return graphql.GraphQLEnumType(
            name=self.name,
            values=self.values,
            description=self.description,
        )


class Scalar(NamedType):
    def __init__(
        self,
        name: str,
        serialize: t.Callable[[t.Any], t.Any] | None = None,
        parse_value: t.Callable[[t.Any], t.Any] | None = None,
        description: str | None = None,
        specified_by: str | None = None,
    ) -> None:
        super().__init__(name=name)

        if serialize is None:
            serialize = self.serialize

        self.serialize = serialize

        if parse_value is None:
            parse_value = self.parse_value

        self.parse_value = parse_value
        self.description = description
        self.specified_by = specified_by

    @staticmethod
    def serialize(value: t.Any) -> t.Any:
        return value

    @staticmethod
    def parse_value(value: t.Any) -> t.Any:
        return value

    def _find_nodes(self) -> t.Iterator[str | Type]:
        yield from ()

    def _apply_types(self, type_map: dict[str, NamedType]) -> None:
        pass

    def _make_graphql_node(self) -> graphql.GraphQLScalarType:
        return graphql.GraphQLScalarType(
            name=self.name,
            serialize=self.serialize,
            parse_value=self.parse_value,
            description=self.description,
            specified_by_url=self.specified_by,
        )


class Wrapping(Type):
    _graphql_class: t.ClassVar[type[graphql.GraphQLWrappingType]]

    def __init__(self, type: str | Type) -> None:
        super().__init__()
        self.type = type

    def _find_nodes(self) -> t.Iterator[str | Type]:
        yield self.type

    def _apply_types(self, type_map: dict[str, NamedType]) -> None:
        self.type = _to_type(self.type, type_map)

    def _make_graphql_node(self) -> graphql.GraphQLWrappingType:
        return self._graphql_class(self.type._to_graphql())

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.type!r}>"


class NonNull(Wrapping):
    _graphql_class = graphql.GraphQLNonNull


class List(Wrapping):
    _graphql_class = graphql.GraphQLList


_ST = t.TypeVar("_ST", Field, Argument, InputField)


def _expand_type_shortcut(
    items: dict[str, str | Type | _ST] | None, cls: type[_ST]
) -> dict[str, _ST]:
    if items is None:
        return {}

    out = {}

    for k, v in items.items():
        if isinstance(v, cls):
            out[k] = v
        else:
            out[k] = cls(v)

    return out


def _to_type(value: str | Type, type_map: dict[str, NamedType]) -> str | Type:
    if isinstance(value, str):
        real = type_map.get(value)

        if real is not None:
            return real

    return value


def _list_to_types(values: list[str | Type], type_map: dict[str, NamedType]) -> None:
    for i, value in enumerate(values):
        values[i] = _to_type(value, type_map)
