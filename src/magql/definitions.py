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
from graphql import GraphQLList
from graphql import GraphQLNonNull
from graphql import GraphQLObjectType
from graphql import GraphQLString
from graphql import GraphQLUnionType
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
    def __init__(self, name, magql_type):
        super().__init__((name, magql_type))
        self.name = name
        self.magql_type = magql_type

    def __str__(self):
        return f"{self.magql_type} instance cannot use reserved name {self.name}"


def check_name(init):
    @wraps(init)
    def wrapper(*args):
        if args[1] in RESERVED:
            raise NamingConflictError(args[1], args[0].__class__.__name__)
        init(*args)

    return wrapper


class MagqlObjectType:
    @check_name
    def __init__(self, name, fields=None, description=None):
        self.name = name
        # dict of field_name to MagqlField
        self.fields = fields if fields is not None else {}
        self.description = description

    def field(self, field_name, return_type, args=None):
        def decorator(resolve):
            self.fields[field_name] = MagqlField(return_type, args, resolve)
            return resolve

        return decorator

    # Convert each value in fields to GQLField
    def convert(self, type_map):
        if self.name in type_map:
            return type_map[self.name]
        type_map[self.name] = GraphQLObjectType(
            self.name, {}, None, description=self.description
        )
        for field_name, field in self.fields.items():
            type_map[self.name].fields[field_name] = field.convert(type_map)
        return type_map[self.name]


class MagqlField:
    def __init__(
        self,
        type_name=None,
        args=None,
        resolve=None,
        description=None,
        deprecation_reason=None,
    ):
        self.description = description
        self.deprecation_reason = deprecation_reason

        # String name representing type
        self.type_name = type_name
        self.args = args if args is not None else {}

        self.resolve = resolve

    def convert(self, type_map):
        gql_args = {}
        for arg_name, arg in self.args.items():
            gql_args[arg_name] = arg.convert(type_map)
        if self.type_name in type_map:
            field_type = type_map[self.type_name]
        else:
            field_type = self.type_name.convert(type_map)
        return GraphQLField(field_type, gql_args, self.resolve)


def js_camelize(word):
    # add config check
    # disable while camelcasing resolvers aren't added
    return camelize(word, False)


class MagqlArgument:  # noqa: E501
    def __init__(self, type_, default_value=None):
        self.type_ = type_
        self.default_value = default_value

    def convert(self, type_map):
        if self.type_ in type_map:
            converted_type = type_map[self.type_]
        else:
            converted_type = self.type_.convert(type_map)
        return GraphQLArgument(converted_type, self.default_value)


class MagqlInputObjectType:
    @check_name
    def __init__(self, name, fields=None, description=None):
        self.name = name
        self.fields = fields if fields is not None else {}
        self.description = description

    def convert(self, type_map):
        if self.name in type_map:
            return type_map[self.name]

        type_map[self.name] = GraphQLInputObjectType(self.name, {}, self.description)

        for field_name, field in self.fields.items():
            type_map[self.name].fields[field_name] = field.convert(type_map)

        return type_map[self.name]


class MagqlInputField:
    def __init__(self, type_name, description=None):
        self.type_name = type_name
        self.description = description

    def convert(self, type_map):
        if self.type_name in type_map:
            field_type = type_map[self.type_name]
        else:
            field_type = self.type_name.convert(type_map)
        return GraphQLInputField(field_type)


class MagqlWrappingType:
    pass


class MagqlNonNull(MagqlWrappingType):  # noqa: E501
    def __init__(self, type_):
        self.type_ = type_

    def convert(self, type_map):
        if self.type_ in type_map:
            return GraphQLNonNull(type_map[self.type_])
        return GraphQLNonNull(self.type_.convert(type_map))


class MagqlList(MagqlWrappingType):  # noqa: E501
    def __init__(self, type_):
        self.type_ = type_

    def convert(self, type_map):
        if self.type_ in type_map:
            converted_type = type_map[self.type_]
        else:
            converted_type = self.type_.convert(type_map)
        return GraphQLList(converted_type)


class MagqlEnumType:
    @check_name
    def __init__(self, name, values=None):
        self.name = name
        self.values = values if values else {}

    def convert(self, type_map):
        if self.name in type_map:
            return type_map[self.name]
        type_map[self.name] = GraphQLEnumType(self.name, self.values)
        return type_map[self.name]


class MagqlUnionType:  # noqa: B903
    @check_name
    def __init__(self, name, types, resolve_type):
        self.name = name

        # List of magql_types or magql_names
        self.types = types

        self.resolve_types = resolve_type

    def convert(self, type_map):
        if self.name in type_map:
            return type_map[self.name]
        types = []

        for enum_type in self.types:
            if isinstance(enum_type, str):
                types.append(type_map[enum_type])
            else:
                types.append(enum_type)
        type_map[self.name] = GraphQLUnionType(self.name, types, self.resolve_types)
        return type_map[self.name]


class MagqlInt:
    def __init__(self, parse_value=None):
        self.parse_value = parse_value

    @staticmethod
    def parse_value_accepts_string(value):
        try:
            converted_value = int(value)
        except ValueError:
            converted_value = coerce_int(value)
        return converted_value

    def convert(self, type_map):
        gql_int = GraphQLInt
        if self.parse_value:
            gql_int.parse_value = self.parse_value
        return gql_int


class MagqlFloat:
    def __init__(self, parse_value=None):
        self.parse_value = parse_value

    @staticmethod
    def parse_value_accepts_string(value):
        try:
            converted_value = float(value)
        except ValueError:
            converted_value = coerce_float(value)
        return converted_value

    def convert(self, type_map):
        gql_float = GraphQLFloat
        if self.parse_value:
            gql_float.parse_value = self.parse_value
        return gql_float


class MagqlFile:
    pass


class MagqlBoolean:
    def convert(self, type_map):
        return GraphQLBoolean


class MagqlString:
    def convert(self, type_map):
        return GraphQLString


class MagqlID:
    def convert(self, type_map):
        return GraphQLID
