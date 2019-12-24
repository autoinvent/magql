from functools import wraps

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
    "FLOAT",
    "DECIMAL",
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
        RESERVED.append(args[1])
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
    # def convert(self):
    #     gql_fields = {}
    #     for field_name, field in self.fields.items():
    #         gql_fields[field_name] = field.convert()
    #
    #     return GraphQLObjectType(
    #         self.name, gql_fields, None, self.description
    #     )  # noqa: E501


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


def js_camelize(word):
    # add config check
    # disable while camelcasing resolvers aren't added
    return camelize(word, False)


class MagqlArgument:  # noqa: E501
    def __init__(self, type_, default_value=None):
        self.type_ = type_
        self.default_value = default_value


class MagqlInputObjectType:
    @check_name
    def __init__(self, name, fields=None, description=None):
        self.name = name
        self.fields = fields if fields is not None else {}
        self.description = description


class MagqlInputField:  # noqa: E501
    def __init__(self, type_name, description=None):
        self.type_name = type_name
        self.description = description


class MagqlWrappingType:
    pass


class MagqlNonNull(MagqlWrappingType):  # noqa: E501
    def __init__(self, type_):
        self.type_ = type_


class MagqlList(MagqlWrappingType):  # noqa: E501
    def __init__(self, type_):
        self.type_ = type_


class MagqlEnumType:
    @check_name
    def __init__(self, name, values=None):
        self.name = name
        self.values = values if values else {}


class MagqlUnionType:  # noqa: B903
    @check_name
    def __init__(self, name, types, resolve_type):
        self.name = name

        # List of magql_types or magql_names
        self.types = types

        self.resolve_types = resolve_type


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


class MagqlFile:
    pass


class MagqlBoolean:
    pass


class MagqlString:
    pass


class MagqlID:
    pass
