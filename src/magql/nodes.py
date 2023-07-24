from __future__ import annotations

import enum
import typing as t
from functools import cached_property

import graphql
from graphql import GraphQLResolveInfo

from .validators import DataValidatorCallable
from .validators import ValidationError
from .validators import ValueValidatorCallable


class Node:
    """Base class of every construct present in a schema. Provides the interface for
    converting Magql instances to GraphQL-Core instances.
    """

    _graphql_node: t.Any | None = None
    """Cached result of :meth:`_to_graphql`."""

    def _find_nodes(self) -> t.Iterable[str | Node]:
        """Iterate over all the nodes that this node references directly. Used by
        :meth:`.Schema._find_nodes` to perform a breadth-first traversal of the graph.
        """
        raise NotImplementedError

    def _apply_types(self, type_map: dict[str, NamedType | None]) -> None:
        """Replace any forward references (string names) with the actual type object
        if it is present in the type map. Used by :meth:`.Schema._find_nodes` after
        collecting all known types.

        :param type_map: Map of type names to type objects.
        """
        raise NotImplementedError

    def _make_graphql_node(self) -> t.Any:
        """Create a GraphQL-Core object from this Magql object. This is implemented by
        each node subclass. It should not be called directly, only through
        :meth:`_to_graphql` which uses caching.
        """
        raise NotImplementedError

    def _to_graphql(self) -> t.Any:
        """Create a GraphQL-Core object from this Magql object. Will return the same
        GraphQL instance each time it is called. Used by :meth:`.Schema.to_graphql` to
        recursively convert all nodes. Calls :meth:`_make_graphql_node`, which should
        call this recursively to convert any child nodes first.
        """
        if self._graphql_node is None:
            self._graphql_node = self._make_graphql_node()

        return self._graphql_node


class Type(Node):
    """Base class of every node that is usable as a type in a schema."""

    @cached_property
    def non_null(self) -> NonNull:
        """Wrap this type in :class:`NonNull`, indicating that the value may not be null
        and must be of this type. Will return the same instance every time it is
        accessed.
        """
        return NonNull(self)

    @cached_property
    def list(self) -> List:
        """Wrap this type in :class:`List`, indicating that the value is a list of items
        of this type. Will return the same instance every time it is accessed.
        """
        return List(self)


class NamedType(Type):
    """Base class of every type that can be referenced by name, which is everything
    except the wrapping types.

    :param name: The name used to refer to this type.
    """

    name: str
    """The name used to refer to this type."""

    def __init__(self, name: str, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self.name: str = name

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"


class ResolverCallable(t.Protocol):
    """The signature that all resolver functions must have."""

    def __call__(
        self, parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        ...


def resolve_attr(parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any) -> t.Any:
    """Resolve a field by getting the attribute of the same name from the parent.
    Equivalent to ``parent.field_name``.

    This is the default resolver.
    """
    return getattr(parent, info.field_name)


def resolve_item(parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any) -> t.Any:
    """Resolve a field by getting the key of the same name from the parent. Equivalent
    to ``parent["field_name"]``.
    """
    return parent.get(info.field_name)


_VCT = t.TypeVar("_VCT")


class _BaseValidatorNode(Node, t.Generic[_VCT]):
    """Common behavior for :class:`_DataValidatorNode` and :class:`_ValueValidatorNode`.

    :param validators: A list of functions that perform validation.
    """

    def __init__(self, validators: list[_VCT] | None = None, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)

        if validators is None:
            validators = []

        self.validators: list[_VCT] = validators
        """A list of functions that perform validation. More can be added by using the
        :meth:`validator` decorator or adding to the list.
        """

    def validator(self, f: _VCT) -> _VCT:
        """Decorate a function to append to the list of validators."""
        self.validators.append(f)
        return f

    # validate method not defined here because the API differs for data and value.


class _DataValidatorNode(_BaseValidatorNode[DataValidatorCallable]):
    """Base class for nodes that validate a collection of values."""

    @property
    def _items_to_validate(self) -> dict[str, Argument] | dict[str, InputField]:
        """A map of names to objects with a ``validators`` list.

        This is necessary since :class:`Field` uses :attr:`~Field.args` and
        :class:`InputObject` uses :attr:`~InputObject.fields`.
        """
        raise NotImplementedError

    def validate(self, info: GraphQLResolveInfo, data: dict[str, t.Any]) -> None:
        # Empty is top-level. Others are Argument/InputField names.
        errors: dict[str, list[t.Any]] = {"": []}

        # Validate individual values in the collection first. Child nodes will call
        # validate on their children first as well, resulting in depth-first validation.
        for name, item in self._items_to_validate.items():
            if name not in data:
                continue

            try:
                item.validate(info, data[name], data)
            except ValidationError as e:
                # Should always be a list here.
                errors[name] = e.message  # type: ignore[assignment]

        # Call this node's validators on the collection of values, after the individual
        # values have been validated.
        for f in self.validators:
            try:
                f(info, data)
            except ValidationError as e:
                # A dict of messages for individual fields.
                if isinstance(e.message, dict):
                    for k, v in e.message.items():
                        # Validating the individual field earlier didn't set any
                        # messages, start a list now.
                        if k not in errors:
                            errors[k] = []

                        # A list of messages, extend the existing list.
                        if isinstance(v, list):
                            errors[k].extend(v)
                        # A single message, append to the existing list.
                        else:
                            errors[k].append(v)
                # A list of top-level messages, extend the existing list.
                elif isinstance(e.message, list):
                    errors[""].extend(e.message)
                # A single top-level message, append to the existing list.
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
    """The implementation of :meth:`_ValueValidatorNode.validate`. This is defined as
    a separate function because of how it's called recursively for nested list types.
    A list in the validator list indicates that the list type should be unwrapped one
    level then have the validators applied to each item. Lists can be arbitrarily
    nested, so this can happen recursively.
    """
    errors = []

    # Unwrap non-null to get named type or list. If the unwrapped type is an
    # InputObject, it also has validation.
    if isinstance(type, NonNull):
        type = type.type  # type: ignore[assignment]

    # If this is an InputObject instead of a scalar, need to start the data validator
    # process again for it, so it can run InputField validators, etc.
    if isinstance(type, InputObject):
        try:
            type.validate(info, value)
        except ValidationError as e:
            # Should always be a dict here.
            errors.append(e.message)

    nested_type: Type | None = None

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
                    nested_type = nested_type.type  # type: ignore[assignment]

                    if isinstance(nested_type, List):
                        break

            # List of errors for this item in the list.
            list_errors = []

            # Call each sub-list validator for each item, recursively.
            for item in value:
                try:
                    _validate_value(nested_type, f, info, item, data)  # pyright: ignore
                except ValidationError as e:
                    # A list of messages, extend the list.
                    if isinstance(e.message, list):
                        list_errors.extend(e.message)
                    # A single message, append to the list.
                    else:
                        list_errors.append(e.message)
                else:
                    # Placeholder for item that had no errors.
                    list_errors.append(None)

            # If at least one item had errors (not None), validation failed.
            if any(list_errors):
                errors.append(list_errors)

        # A function in the validator list. The nested list behavior above will
        # eventually end up here.
        else:
            try:
                f(info, value, data)
            except ValidationError as e:
                # A list of messages, extend the list.
                if isinstance(e.message, list):
                    errors.extend(e.message)
                # A single message, append to the list.
                else:
                    errors.append(e.message)

    if errors:
        raise ValidationError(errors)


class _ValueValidatorNode(_BaseValidatorNode[ValueValidatorCallable]):
    """Base class for nodes that validate a single value."""

    type: str | Type
    """The type of the value passed to this argument. May be the name of a type
    defined elsewhere.
    """

    def validate(
        self, info: GraphQLResolveInfo, value: t.Any, data: dict[str, t.Any]
    ) -> None:
        """Validate a given value by calling each validator in :attr:`validators` on
        this item's value.

        :param info: GraphQL resolve info. Mainly useful for ``info.context``.
        :param value: The value being validated.
        :param data: All input items being validated, of which this is one item.
        """
        _validate_value(
            self.type, self.validators, info, value, data  # type: ignore[arg-type]
        )


class _BaseObject(NamedType):
    """Shared implementation for :class:`Object` and :class:`Union`. The only difference
    between the two is what GraphQL-Core class they create.
    """

    _graphql_class: t.ClassVar[
        type[graphql.GraphQLObjectType] | type[graphql.GraphQLInterfaceType]
    ]
    """The GraphQL class to create."""

    def __init__(
        self,
        name: str,
        fields: dict[str, str | Type | Field] | None = None,
        interfaces: list[str | Interface] | None = None,
        description: str | None = None,
    ) -> None:
        super().__init__(name=name)

        self.fields: dict[str, Field] = _expand_type_shortcut(fields, Field)
        """Dictionary mapping field names to instances. Type names or instances passed
        in have been converted to full field instances.
        """

        if interfaces is None:
            interfaces = []

        self.interfaces: list[str | Interface] = interfaces
        """List of :class:`Interface` instances that this type implements. Each item may
        be the name of a type defined elsewhere.
        """

        self.description: str | None = description
        """Help text to show in the schema."""

    def field(
        self,
        name: str,
        type: str | Type,
        args: dict[str, str | Type | Argument] | None = None,
        validators: list[DataValidatorCallable] | None = None,
        description: str | None = None,
        deprecation: str | None = None,
    ) -> t.Callable[[ResolverCallable], ResolverCallable]:
        """Shortcut to add a field to the object by decorating a resolver function.

        :param name: The name of the field on the object.
        :param type: The type of the value returned by this field's resolver. May be the
            string name of a type defined elsewhere.
        :param args: Arguments available to this field's resolver. Each value may be the
            string name of a type, or a type instance, instead of the full argument
            instance.
        :param validators: Data validators applied to the collection of arguments.
        :param description: Help text to show in the schema.
        :param deprecation: Deprecation message to show in the schema.
        """

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

    def _find_nodes(self) -> t.Iterator[str | Node]:
        yield from self.fields.values()
        yield from self.interfaces

    def _apply_types(self, type_map: dict[str, NamedType | None]) -> None:
        _list_to_types(self.interfaces, type_map)  # type: ignore[arg-type]

    def _make_graphql_node(self) -> t.Any:
        return self._graphql_class(
            name=self.name,
            fields=lambda: {k: v._to_graphql() for k, v in self.fields.items()},
            interfaces=lambda: [
                v._to_graphql() for v in self.interfaces  # type: ignore[union-attr]
            ],
            description=self.description,
            extensions={"magql_node": self},
        )


class Object(_BaseObject):
    """A named collection of fields. Can be used as the type of a field. Cannot be used
    as the type of an argument, use :class:`InputObject` instead.

    :param name: The name used to refer to this type.
    :param fields: Fields within this object. Each value may be the name of a type
        defined elsewhere, or a type instance, instead of a full field instance.
    :param interfaces: Interfaces providing more fields for this object. Each item may
        be the name of an :class:`Interface` defined elsewhere.
    :param description: Help text to show in the schema.
    """

    _graphql_class = graphql.GraphQLObjectType


class Interface(_BaseObject):
    """A named collection of fields that can are shared between multiple objects. Cannot
    be used as the type of a field.

    :param name: The name used to refer to this type.
    :param fields: Fields within this interface. Each value may be the name of a type
        defined elsewhere, or a type instance, instead of a full field instance.
    :param interfaces: Interfaces providing more fields for this interface. Each item
        may be the name of an :class:`Interface` defined elsewhere.
    :param description: Help text to show in the schema.
    """

    _graphql_class = graphql.GraphQLInterfaceType


class Union(NamedType):
    """A named group of objects. Can be used as the type of a field; when resolved the
    field must be one of the objects.

    :param name: The name used to refer to this type.
    :param types: Maps Python classes to Magql :class:`Object` types. Each value may be
        the name of a type defined elsewhere.
    :param description: Help text to show in the schema.
    """

    def __init__(
        self,
        name: str,
        types: dict[type[t.Any], str | Object] | None = None,
        description: str | None = None,
    ) -> None:
        super().__init__(name=name)

        self.types: list[str | Object] = []
        """List of :class:`Object` types in this union. Each value may be the name of a
        type defined elsewhere.

        Use :meth:`add_type` instead of modifying this directly.
        """

        self.py_to_name: dict[type[t.Any], str] = {}
        """Map of Python classes to type names. Used to tell GraphQL what type from the
        union to use when resolving the value.

        Use :meth:`add_type` instead of modifying this directly.
        """

        self.description: str | None = description
        """Help text to show in the schema."""

        if types is not None:
            for py_type, gql_type in types.items():
                self.add_type(py_type, gql_type)

    def add_type(
        self, py_type: type[t.Any], gql_type: str | Object | None = None
    ) -> None:
        """Add a new type to this union. The given Python class will be resolved to the
        given GraphQL type.

        :param py_type: The Python side of the type.
        :param gql_type: The GraphQL side of the type.
        """
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
        """Resolves the Python value returned by a field's resolver to a specific object
        name within this union.

        :param value: The value returned by the field's resolver.
        :param info: GraphQL resolve info. Mainly useful for ``info.context``.
        :param node: The GraphQL union being resolved.
        """
        return self.py_to_name[type(value)]

    def _find_nodes(self) -> t.Iterator[str | Node]:
        yield from self.types

    def _apply_types(self, type_map: dict[str, NamedType | None]) -> None:
        _list_to_types(self.types, type_map)  # type: ignore[arg-type]

    def _make_graphql_node(self) -> graphql.GraphQLUnionType:
        return graphql.GraphQLUnionType(
            name=self.name,
            types=[o._to_graphql() for o in self.types],  # type: ignore[union-attr]
            resolve_type=self.resolve_type,  # type: ignore[arg-type]
            description=self.description,
            extensions={"magql_node": self},
        )


class Field(_DataValidatorNode):
    """A field on an :class:`Object`.

    Each field has a resolver function to get its value from the parent object. Magql
    adds a validation system for the arguments before calling the resolver with those
    arguments.

    The default resolver, :func:`resolve_attr`, looks up the field name as an attribute
    on the parent. If the parent is a dict, use :func:`resolve_item` instead to use the
    field name as a key.

    :param type: The type of the value returned by this field's resolver. May be the
        name of a type defined elsewhere.
    :param args: Arguments available to this field's resolver. Each value may be the
        name of a type, or a type instance, instead of the full argument instance.
    :param validators: Data validators applied to the collection of arguments.
    :param resolve: The function to use to resolve this field, returning a value to the
        query. Defaults to attribute lookup by the name of the field in the object.
    :param description: Help text to show in the schema.
    :param deprecation: Deprecation message to show in the schema.
    """

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

        self.type: str | Type = type
        """The type of the value returned by this field's resolver. May be the name of a
        type defined elsewhere.
        """

        self.args: dict[str, Argument] = _expand_type_shortcut(args, Argument)
        """Arguments available to this field's resolver. Type names or instances passed
        in have been converted to full argument instances.
        """

        self._pre_resolve: ResolverCallable | None = None
        self._resolve: ResolverCallable = resolve

        self.description: str | None = description
        """Help text to show in the schema."""

        self.deprecation: str | None = deprecation
        """Deprecation message to show in the schema."""

    def pre_resolver(self, f: ResolverCallable) -> ResolverCallable:
        """Call the decorated function at the beginning of the resolve process, before
        validating arguments or resolving the value.

        This is useful to check permissions or log access. Raise a
        :exc:`ValidationError` to stop with an error instead.
        """
        self._pre_resolve = f
        return f

    def resolver(self, f: ResolverCallable) -> ResolverCallable:
        """Call the decorated function to resolve the value of the field.

        Raise a :exc:`ValidationError` to stop with an error instead.
        """
        self._resolve = f
        return f

    def resolve(
        self, parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        """The full resolver behavior provided by Magql. If a :meth:`pre_resolve`
        function was registered, it is called first. Then :meth:`validate` validates the
        input arguments. Finally, the resolver is called to get a value. Any part of
        this process can raise a :exc:`ValidationError` to stop with an error instead.

        Do not override this function. Instead, use :meth:`resolver`, :meth:`validator`,
        and :meth:`pre_resolver` to modify the behavior.
        """
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

    def _find_nodes(self) -> t.Iterator[str | Node]:
        yield self.type
        yield from self.args.values()

    def _apply_types(self, type_map: dict[str, NamedType | None]) -> None:
        self.type = _to_type(self.type, type_map)

    def _make_graphql_node(self) -> graphql.GraphQLField:
        return graphql.GraphQLField(
            type_=self.type._to_graphql(),  # type: ignore[union-attr]
            args={name: arg._to_graphql() for name, arg in self.args.items()},
            resolve=self.resolve,
            description=self.description,
            deprecation_reason=self.deprecation,
            extensions={"magql_node": self},
        )


class Argument(_ValueValidatorNode):
    """An input argument to a :class:`Field` resolver.

    :param type: The type of the value passed to this argument. May be the name of a
        type defined elsewhere.
    :param default: The default Python value to use if input is not provided. By
        default, it will not be passed to the resolver, which is not the same as a
        default of ``None``.
    :param validators: Value validators applied to the input value.
    :param description: Help text to show in the schema.
    :param deprecation: Deprecation message to show in the schema.
    """

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

        self.default: t.Any = default
        """The default Python value to use if input is not provided. By default, it will
        not be passed to the resolver, which is not the same as a default of ``None``.
        """

        self.description: str | None = description
        """Help text to show in the schema."""

        self.deprecation: str | None = deprecation
        """Deprecation message to show in the schema."""

    def _find_nodes(self) -> t.Iterable[str | Node]:
        yield self.type

    def _apply_types(self, type_map: dict[str, NamedType | None]) -> None:
        self.type = _to_type(self.type, type_map)

    def _make_graphql_node(self) -> graphql.GraphQLArgument:
        return graphql.GraphQLArgument(
            type_=self.type._to_graphql(),  # type: ignore[union-attr]
            default_value=self.default,
            description=self.description,
            deprecation_reason=self.deprecation,
            extensions={"magql_node": self},
        )


class InputObject(NamedType, _DataValidatorNode):
    """A named collection of input fields. Can be used as the type of an argument.
    Cannot be used as the type of a field, use :class:`Object` instead.

    Allows using a JSON object as the input value to an argument.

    :param name: The name used to refer to this type.
    :param fields: Fields within this object. Each value may be the name of a type
        defined elsewhere, or a type instance, instead of a full field instance.
    :param validators: Data validators applied to the collection of input fields.
    :param description: Help text to show in the schema.
    """

    def __init__(
        self,
        name: str,
        fields: dict[str, str | Type | InputField] | None = None,
        validators: list[DataValidatorCallable] | None = None,
        description: str | None = None,
    ) -> None:
        super().__init__(name=name, validators=validators)

        self.fields: dict[str, InputField] = _expand_type_shortcut(fields, InputField)
        """Fields within this object. Type names or instances passed in have been
        converted to full input field instances.
        """

        self.description: str | None = description
        """Help text to show in the schema."""

    @property
    def _items_to_validate(self) -> dict[str, InputField]:
        return self.fields

    def _find_nodes(self) -> t.Iterator[str | Node]:
        yield from self.fields.values()

    def _apply_types(self, type_map: dict[str, NamedType | None]) -> None:
        pass

    def _make_graphql_node(self) -> graphql.GraphQLInputObjectType:
        return graphql.GraphQLInputObjectType(
            name=self.name,
            fields=lambda: {k: v._to_graphql() for k, v in self.fields.items()},
            description=self.description,
            extensions={"magql_node": self},
        )


class InputField(_ValueValidatorNode):
    """An input field within an :class:`InputObject`.

    :param type: The type of the value passed to this field. May be the name of a
        type defined elsewhere.
    :param default: The default Python value to use if input is not provided. By
        default, it will not be present in the dict, which is not the same as a default
        of ``None``.
    :param validators: Value validators applied to the input value.
    :param description: Help text to show in the schema.
    :param deprecation: Deprecation message to show in the schema.
    """

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

        self.default: t.Any = default
        """The default Python value to use if input is not provided. By default, it will
        not be present in the dict, which is not the same as a default of ``None``.
        """

        self.description: str | None = description
        """Help text to show in the schema."""

        self.deprecation: str | None = deprecation
        """Deprecation message to show in the schema."""

    def _find_nodes(self) -> t.Iterable[str | Node]:
        yield self.type

    def _apply_types(self, type_map: dict[str, NamedType | None]) -> None:
        self.type = _to_type(self.type, type_map)

    def _make_graphql_node(self) -> graphql.GraphQLInputField:
        return graphql.GraphQLInputField(
            type_=self.type._to_graphql(),  # type: ignore[union-attr]
            default_value=self.default,
            description=self.description,
            deprecation_reason=self.deprecation,
            extensions={"magql_node": self},
        )


class Enum(NamedType):
    """A set of possible values for a field or argument. The values are essentially
    strings in the schema, but when used as input or output they can map to other Python
    types.

    :param name: The name used to refer to this type.
    :param values: The possible string values mapped to Python values. A list of strings
        will use the same value on both sides. A Python :class:~enum.Enum` will use the
        member names mapped to the instances.
    :param description: Help text to show in the schema.
    """

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
            values = values.__members__.copy()

        self.values: dict[str, t.Any] = values  # pyright: ignore
        """Maps string values used by GraphQL to Python values seen by the resolver. A
        list or :class:`~enum.Enum` passed in has been converted to a dict.
        """

        self.description: str | None = description
        """Help text to show in the schema."""

    def _find_nodes(self) -> t.Iterator[str | Node]:
        yield from ()

    def _apply_types(self, type_map: dict[str, NamedType | None]) -> None:
        pass

    def _make_graphql_node(self) -> graphql.GraphQLEnumType:
        return graphql.GraphQLEnumType(
            name=self.name,
            values=self.values,
            description=self.description,
            extensions={"magql_node": self},
        )


def _identity(value: t.Any) -> t.Any:
    return value


class Scalar(NamedType):
    """A plain value, as opposed to an object with nested fields.

    Values are serialized when sent between client and server. The serialization format
    (typically JSON) may not be able to represent a type directly, so the scalar must be
    able to convert to and from the Python value.

    :param name: The name used to refer to this type.
    :param serialize: A function that converts a Python value to a format appropriate
        for the output serialization format. By default the value is returned unchanged.
    :param parse_value: A function that converts a value in the input serialization
        format to Python. By default the value is returned unchanged.
    :param description: Help text to show in the schema.
    :param specified_by: A reference to the specification defining this type. Shown
        alongside ``description`` in the schema.
    """

    def __init__(
        self,
        name: str,
        serialize: t.Callable[[t.Any], t.Any] = _identity,
        parse_value: t.Callable[[t.Any], t.Any] = _identity,
        description: str | None = None,
        specified_by: str | None = None,
    ) -> None:
        super().__init__(name=name)

        self.serialize: t.Callable[[t.Any], t.Any] = serialize
        """Convert a Python value to the output serialization format."""

        self.parse_value: t.Callable[[t.Any], t.Any] = parse_value
        """Convert a value in the input serialization format to Python."""

        self.description: str | None = description
        """Help text to show in the schema."""

        self.specified_by: str | None = specified_by
        """A reference to the specification defining this type. Shown alongside
        :attr:`description` in the schema.
        """

    def _find_nodes(self) -> t.Iterator[str | Node]:
        yield from ()

    def _apply_types(self, type_map: dict[str, NamedType | None]) -> None:
        pass

    def _make_graphql_node(self) -> graphql.GraphQLScalarType:
        return graphql.GraphQLScalarType(
            name=self.name,
            serialize=self.serialize,
            parse_value=self.parse_value,
            description=self.description,
            specified_by_url=self.specified_by,
            extensions={"magql_node": self},
        )


class Wrapping(Type):
    """Shared implementation for :class:`NonNull` and :class:`List`. The only difference
    between the two is what GraphQL-Core class they create.
    """

    _graphql_class: t.ClassVar[type[graphql.GraphQLWrappingType[t.Any]]]
    """The GraphQL class to create."""

    def __init__(self, type: str | Type) -> None:
        super().__init__()

        self.type: str | Type = type
        """The wrapped type. May be the name of a type defined elsewhere."""

    def _find_nodes(self) -> t.Iterator[str | Node]:
        yield self.type

    def _apply_types(self, type_map: dict[str, NamedType | None]) -> None:
        self.type = _to_type(self.type, type_map)

    def _make_graphql_node(self) -> graphql.GraphQLWrappingType[t.Any]:
        return self._graphql_class(self.type._to_graphql())  # type: ignore[union-attr]

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.type!r}>"


class NonNull(Wrapping):
    """Indicates that null may not be used in place of a value of the wrapped type.

    If you have a type object already, use its :attr:`~Type.non_null` property. Creating
    this class directly is useful when you need to reference the type by name instead.

    :param type: The wrapped type. May be the name of a type defined elsewhere.
    """

    _graphql_class = graphql.GraphQLNonNull


class List(Wrapping):
    """Indicates that the value is a list of values of the wrapped type.

    If you have a type object already, use its :attr:`~Type.list` property. Creating
    this class directly is useful when you need to reference the type by name instead.

    When defining a list type, consider whether the value should be marked as non-null
    as well, and if items will always be non-null.

    Arbitrarily nested list types can be created.

    If you provide a single value as input, GraphQL-Core will wrap it in a list.
    However, its behavior when doing this for nested list types may be unexpected.

    :param type: The wrapped type. May be the name of a type defined elsewhere.
    """

    _graphql_class = graphql.GraphQLList


_ST = t.TypeVar("_ST", Field, Argument, InputField)


def _expand_type_shortcut(
    items: dict[str, str | Type | _ST] | None, cls: type[_ST]
) -> dict[str, _ST]:
    """Create the expected node instance for each value that is a type name or instance.

    For example, the following are equivalent:

    .. code-block:: python

        nodes.Field(args={"name": nodes.Argument(scalars.String)})
        nodes.Field(args={"name": scalars.String})
        nodes.Field(args={"name": "String"})

    :param items: Mapping with values that can be type shortcuts.
    :param cls: Node class to create for each value.
    """
    if items is None:
        return {}

    out = {}

    for k, v in items.items():
        if isinstance(v, cls):
            out[k] = v
        else:
            out[k] = cls(v)  # type: ignore[arg-type]

    return out


def _to_type(value: str | Type, type_map: dict[str, NamedType | None]) -> str | Type:
    """Used during :meth:`Node._apply_types` to turn a type name into the defined
    instance. Will also use list ``[]`` and non-null ``!`` syntax to apply wrappers.

    :param value: An instance to return, or a name to resolve if possible.
    :param type_map: Maps names to type instances.
    """
    if not isinstance(value, str):
        return value

    wrappers: list[type[Wrapping]] = []

    while True:
        if value[-1] == "!":
            value = value[:-1]
            wrappers.append(NonNull)
        elif value[0] == "[":
            value = value[1:-1]
            wrappers.append(List)
        else:
            break

    out: str | Type | None = type_map.get(value)

    if out is None:
        out = value

    while wrappers:
        w = wrappers.pop()
        out = w(out)

    return out


def _list_to_types(
    values: list[str | Type], type_map: dict[str, NamedType | None]
) -> None:
    """Call :func:`_to_type` on each item in a list, replacing names with their resolved
    type in the list.

    :param values: List of types to resolve in place.
    :param type_map: Maps names to type instances.
    """
    for i, value in enumerate(values):
        values[i] = _to_type(value, type_map)
