from __future__ import annotations

import typing as t
from functools import wraps

from graphql import GraphQLArgument
from graphql import GraphQLBoolean
from graphql import GraphQLEnumType
from graphql import GraphQLField
from graphql import GraphQLFloat
from graphql import GraphQLID
from graphql import GraphQLInputField
from graphql import GraphQLInputObjectType
from graphql import GraphQLInt
from graphql import GraphQLInterfaceType
from graphql import GraphQLList
from graphql import GraphQLNonNull
from graphql import GraphQLObjectType
from graphql import GraphQLScalarType
from graphql import GraphQLString
from graphql import GraphQLType
from graphql import GraphQLUnionType
from graphql import GraphQLWrappingType
from graphql.type.scalars import coerce_float
from graphql.type.scalars import coerce_int
from inflection import camelize

RESERVED = [
    "JSON",
    "JSONType",
    "DateTime",
    "Text",
    "Date",
    "UnicodeText",
    "Unicode",
    "UrlType",
    "PhoneNumberType",
    "EmailType",
    "Time",
    "String",
    "VARCHAR",
    "Float",
    "Numeric",
    "Boolean",
    "ChoiceType",
]


class NamingConflictError(Exception):
    def __init__(self, name: str, magql_type: str):
        super().__init__((name, magql_type))
        self.name = name
        self.magql_type = magql_type

    def __str__(self) -> str:
        return f"{self.magql_type} instance cannot use reserved name {self.name}"


def check_name(init: t.Callable) -> t.Callable:
    @wraps(init)
    def wrapper(*args: str) -> None:
        if args[1] in RESERVED:
            raise NamingConflictError(args[1], args[0].__class__.__name__)
        init(*args)

    return wrapper


class MagqlObjectType:
    @check_name
    def __init__(
        self,
        name: str,
        fields: t.Optional[t.Dict[str, t.Any]] = None,
        description: t.Optional[str] = None,
    ):
        self.name = name
        # dict of field_name to MagqlField
        self.fields = fields if fields is not None else {}
        self.description = description

    def field(
        self, field_name: str, return_type: t.Any, args: t.Optional[t.Any] = None
    ) -> t.Callable:
        def decorator(resolve: t.Callable) -> t.Callable:
            self.fields[field_name] = MagqlField(return_type, args, resolve)
            return resolve

        return decorator

    # Convert each value in fields to GQLField
    def convert(self, type_map: t.Dict[str, GraphQLType]) -> GraphQLObjectType:
        if self.name in type_map:
            return t.cast(GraphQLObjectType, type_map[self.name])
        type_map[self.name] = GraphQLObjectType(
            self.name, {}, None, description=self.description
        )
        for field_name, field in self.fields.items():
            t.cast(GraphQLObjectType, type_map[self.name]).fields[
                field_name
            ] = field.convert(type_map)
        return t.cast(GraphQLObjectType, type_map[self.name])


class MagqlField:
    def __init__(
        self,
        type_name: t.Optional[t.Any] = None,
        args: t.Optional[t.Dict[str, MagqlArgument]] = None,
        resolve: t.Optional[t.Callable] = None,
        description: t.Optional[str] = None,
        deprecation_reason: t.Optional[str] = None,
    ):
        self.description = description
        self.deprecation_reason = deprecation_reason

        # String name representing type
        self.type_name = type_name
        self.args = args if args is not None else {}

        self.resolve = resolve

    def convert(
        self,
        type_map: t.Mapping[
            str,
            t.Union[
                GraphQLScalarType,
                GraphQLObjectType,
                GraphQLInterfaceType,
                GraphQLUnionType,
                GraphQLEnumType,
                GraphQLWrappingType,
            ],
        ],
    ) -> GraphQLField:
        gql_args = {}
        for arg_name, arg in self.args.items():
            gql_args[arg_name] = arg.convert(type_map)
        if self.type_name in type_map:
            field_type = type_map[t.cast(str, self.type_name)]
        else:
            field_type = t.cast(t.Any, self.type_name).convert(type_map)
        return GraphQLField(field_type, gql_args, self.resolve)


def js_camelize(word: str) -> str:
    # add config check
    # disable while camelcasing resolvers aren't added
    return camelize(word, False)


class MagqlArgument:  # noqa: E501
    def __init__(self, type_: t.Any, default_value: t.Optional[t.Any] = None):
        self.type_ = type_
        self.default_value = default_value

    def convert(
        self,
        type_map: t.Mapping[
            str,
            t.Union[
                GraphQLScalarType,
                GraphQLObjectType,
                GraphQLInterfaceType,
                GraphQLUnionType,
                GraphQLEnumType,
                GraphQLWrappingType,
            ],
        ],
    ) -> GraphQLArgument:
        if self.type_ in type_map:
            converted_type = type_map[self.type_]
        else:
            converted_type = self.type_.convert(type_map)
        return GraphQLArgument(
            t.cast(
                t.Union[
                    GraphQLScalarType,
                    GraphQLEnumType,
                    GraphQLInputObjectType,
                    GraphQLWrappingType,
                ],
                converted_type,
            ),
            self.default_value,
        )


class MagqlInputObjectType:
    @check_name
    def __init__(
        self,
        name: str,
        fields: t.Optional[t.Dict[str, t.Any]] = None,
        description: t.Optional[str] = None,
    ):
        self.name = name
        self.fields: t.Dict[str, t.Any] = fields if fields is not None else {}
        self.description = description

    def convert(self, type_map: t.Dict[str, GraphQLType]) -> GraphQLInputObjectType:
        if self.name in type_map:
            return t.cast(GraphQLInputObjectType, type_map[self.name])

        type_map[self.name] = GraphQLInputObjectType(self.name, {}, self.description)

        for field_name, field in self.fields.items():
            t.cast(GraphQLInputObjectType, type_map[self.name]).fields[
                field_name
            ] = field.convert(type_map)

        return t.cast(GraphQLInputObjectType, type_map[self.name])


class MagqlInputField:
    def __init__(self, type_name: t.Any, description: t.Optional[str] = None):
        self.type_name = type_name
        self.description = description

    def convert(self, type_map: t.Mapping[str, GraphQLType]) -> GraphQLInputField:
        if self.type_name in type_map:
            field_type = type_map[self.type_name]
        else:
            field_type = self.type_name.convert(type_map)
        return GraphQLInputField(
            t.cast(
                t.Union[
                    GraphQLScalarType,
                    GraphQLEnumType,
                    GraphQLInputObjectType,
                    GraphQLWrappingType,
                ],
                field_type,
            )
        )


class MagqlWrappingType:
    pass


class MagqlNonNull(MagqlWrappingType):  # noqa: E501
    def __init__(self, type_: t.Any):
        self.type_ = type_

    def convert(self, type_map: t.Dict[str, GraphQLType]) -> GraphQLNonNull:
        if self.type_ in type_map:
            return GraphQLNonNull(type_map[self.type_])
        return GraphQLNonNull(self.type_.convert(type_map))


class MagqlList(MagqlWrappingType):  # noqa: E501
    def __init__(self, type_: t.Any):
        self.type_ = type_

    def convert(self, type_map: t.Dict[str, GraphQLType]) -> GraphQLList:
        if self.type_ in type_map:
            converted_type = type_map[self.type_]
        else:
            converted_type = self.type_.convert(type_map)
        return GraphQLList(converted_type)


class MagqlEnumType:
    @check_name
    def __init__(self, name: str, values: t.Optional[t.Dict[str, t.Any]] = None):
        self.name = name
        self.values = values if values else {}

    def convert(self, type_map: t.Dict[str, GraphQLType]) -> GraphQLEnumType:
        if self.name in type_map:
            return t.cast(GraphQLEnumType, type_map[self.name])
        type_map[self.name] = GraphQLEnumType(self.name, self.values)
        return t.cast(GraphQLEnumType, type_map[self.name])


class MagqlUnionType:  # noqa: B903
    @check_name
    def __init__(
        self,
        name: str,
        types: t.List[t.Union[str, GraphQLObjectType]],
        resolve_type: t.Optional[t.Callable],
    ):
        self.name = name

        # List of magql_types or magql_names
        self.types = types

        self.resolve_types = resolve_type

    def convert(self, type_map: t.Dict[str, GraphQLType]) -> GraphQLUnionType:
        if self.name in type_map:
            return t.cast(GraphQLUnionType, type_map[self.name])
        types: t.List[GraphQLObjectType] = []

        for enum_type in self.types:
            if isinstance(enum_type, str):
                types.append(t.cast(GraphQLObjectType, type_map[enum_type]))
            else:
                types.append(enum_type)
        type_map[self.name] = GraphQLUnionType(self.name, types, self.resolve_types)
        return t.cast(GraphQLUnionType, type_map[self.name])


class MagqlInt:
    def __init__(self, parse_value: t.Optional[t.Callable] = None):
        self.parse_value = parse_value

    @staticmethod
    def parse_value_accepts_string(value: str) -> int:
        try:
            converted_value = int(value)
        except ValueError:
            converted_value = coerce_int(value)
        return converted_value

    def convert(self, type_map: t.Mapping[str, GraphQLType]) -> GraphQLScalarType:
        gql_int = GraphQLInt
        if self.parse_value:
            gql_int.parse_value = self.parse_value  # type: ignore
        return gql_int


class MagqlFloat:
    def __init__(self, parse_value: t.Optional[t.Callable] = None):
        self.parse_value = parse_value

    @staticmethod
    def parse_value_accepts_string(value: str) -> float:
        try:
            converted_value = float(value)
        except ValueError:
            converted_value = coerce_float(value)
        return converted_value

    def convert(self, type_map: t.Mapping[str, GraphQLType]) -> GraphQLScalarType:
        gql_float = GraphQLFloat
        if self.parse_value:
            gql_float.parse_value = self.parse_value  # type: ignore
        return gql_float


class MagqlFile:
    pass


class MagqlBoolean:
    def convert(self, type_map: t.Mapping[str, GraphQLType]) -> GraphQLScalarType:
        return GraphQLBoolean


class MagqlString:
    def convert(self, type_map: t.Mapping[str, GraphQLType]) -> GraphQLScalarType:
        return GraphQLString


class MagqlID:
    def convert(self, type_map: t.Mapping[str, GraphQLType]) -> GraphQLScalarType:
        return GraphQLID
