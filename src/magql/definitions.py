from inflection import camelize


class MagqlObjectType:
    def __init__(self, name, fields=None, description=None):
        self.name = name
        # dict of field_name to MagqlField
        self.fields = fields if fields is not None else {}
        self.description = description

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
    def __init__(self, name, values=None):
        self.name = name
        self.values = values if values else {}


class MagqlInt:
    pass


class MagqlFloat:
    pass


class MagqlBoolean:
    pass


class MagqlString:
    pass


class MagqlID:
    pass
