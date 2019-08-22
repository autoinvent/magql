from functools import singledispatch

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
from graphql import GraphQLSchema
from graphql import GraphQLString
from graphql import GraphQLUnionType

from magql.definitions import MagqlArgument
from magql.definitions import MagqlBoolean
from magql.definitions import MagqlEnumType
from magql.definitions import MagqlField
from magql.definitions import MagqlFloat
from magql.definitions import MagqlID
from magql.definitions import MagqlInputField
from magql.definitions import MagqlInputObjectType
from magql.definitions import MagqlInt
from magql.definitions import MagqlList
from magql.definitions import MagqlNonNull
from magql.definitions import MagqlObjectType
from magql.definitions import MagqlString
from magql.definitions import MagqlUnionType
from magql.definitions import MagqlWrappingType


class Convert:
    def __init__(self, manager_list):
        # type_map maps magql_names to GraphQL and is needed to translate
        # MagqlTypes to GraphQLTypes
        self.gql_queries = {}
        self.gql_mutations = {}

        self.type_map = {
            "String": GraphQLString,
            "Int": GraphQLInt,
            "Boolean": GraphQLBoolean,
            "Float": GraphQLFloat,
            "ID": GraphQLID,
        }

        self.generate_type_map(manager_list)

        for manager in manager_list:
            if manager:
                self.convert_manager(manager)

    # TODO: Update convert_str_leafs and convert_type to either recursive or
    # functions on MagqlTypes
    @staticmethod
    def convert_type(ret_type, magql_type_map):
        wrapping_types_stack2 = []
        while isinstance(ret_type, MagqlWrappingType):
            wrapping_types_stack2.append(type(ret_type))
            ret_type = ret_type.type_
        if isinstance(ret_type, str):
            ret_type = magql_type_map[ret_type]
        while wrapping_types_stack2:
            ret_type = wrapping_types_stack2.pop()(ret_type)
        return ret_type

    @staticmethod
    def convert_str_leafs(type_, magql_type_map):
        wrapping_types_stack = []
        while isinstance(type_, MagqlWrappingType):
            wrapping_types_stack.append(type(type_))
            type_ = type_.type_
        if isinstance(type_, MagqlEnumType):
            return

        if isinstance(type_, MagqlUnionType):
            return
        for field_name, field in type_.fields.items():
            if not (
                isinstance(field, MagqlField) or isinstance(field, MagqlInputField)
            ):
                raise Exception(
                    f"Expected type MagqlField, got type {type(field)} "
                    f"for field: {field_name}\n Did you "
                    "forget to wrap your field with MagqlField?"
                )

            field.type_name = Convert.convert_type(field.type_name, magql_type_map)
            if not isinstance(field, MagqlInputField):
                for arg_name, arg in field.args.items():
                    field.args[arg_name] = Convert.convert_type(
                        arg.type_, magql_type_map
                    )

    def generate_type_map(self, managers):
        magql_type_map = {
            "String": MagqlString(),
            "Int": MagqlInt(MagqlInt.parse_value_accepts_string),
            "Boolean": MagqlBoolean(),
            "Float": MagqlFloat(MagqlFloat.parse_value_accepts_string),
            "ID": MagqlID(),
        }
        for manager in managers:
            if not manager:
                continue
            for type_name, type_ in manager.magql_types.items():
                magql_type_map[type_name] = type_
        for manager in managers:
            if not manager:
                continue
            for _type_name, type_ in manager.magql_types.items():
                Convert.convert_str_leafs(type_, magql_type_map)
            # Convert.convert_str_leafs(manager.query, magql_type_map)
            # Convert.convert_str_leafs(manager.mutation, magql_type_map)

        for manager in managers:
            if manager:
                self.convert_types(manager)

    def convert_types(self, manager):
        for _magql_name, magql_type in manager.magql_types.items():
            convert(magql_type, self.type_map)
        for _magql_name, magql_type in manager.magql_types.items():
            convert(magql_type, self.type_map)

    def generate_mutations(self, manager):
        for _mutation_name, magql_field in manager.mutation.fields.items():
            for _argument_name, argument in magql_field.args.items():
                convert(argument, self.type_map)

            if magql_field.type_name not in self.type_map:
                pass

    def convert_manager(self, manager):
        for query_name, query in manager.query.fields.items():
            self.gql_queries[query_name] = convert(query, self.type_map)

        for mut_name, mutation in manager.mutation.fields.items():
            self.gql_mutations[mut_name] = convert(mutation, self.type_map)

    def generate_schema(self):
        query = GraphQLObjectType("Query", self.gql_queries)
        mutation = GraphQLObjectType("Mutation", self.gql_mutations)
        return GraphQLSchema(query, mutation)


# Convert needs all strings to be converted to MagqlTypes
@singledispatch
def convert(type, type_map):
    print(f"Cannot find type: {type}")
    return type


# TODO: Merge these two functions
@convert.register(MagqlObjectType)
def _(magql_object, type_map):
    magql_name = magql_object.name
    if magql_name in type_map:
        return type_map[magql_name]
    type_map[magql_name] = GraphQLObjectType(magql_name, {})
    for field_name, field in magql_object.fields.items():
        type_map[magql_name].fields[field_name] = convert(field, type_map)
    return type_map[magql_name]


@convert.register(MagqlInputObjectType)
def _(magql_object, type_map):
    magql_name = magql_object.name

    if magql_name in type_map:
        return type_map[magql_name]
    type_map[magql_name] = GraphQLInputObjectType(magql_name, {})
    for field_name, field in magql_object.fields.items():
        type_map[magql_name].fields[field_name] = convert(field, type_map)
    return type_map[magql_name]


@convert.register(MagqlField)
def _(magql_field, type_map):
    gql_args = {}
    for arg_name, arg in magql_field.args.items():
        gql_args[arg_name] = convert(arg, type_map)
    # TODO: add type_ in addition to type_name
    field_type = convert(magql_field.type_name, type_map)
    return GraphQLField(field_type, gql_args, magql_field.resolve)


@convert.register(MagqlInputField)
def _(magql_field, type_map):
    field_type = convert(magql_field.type_name, type_map)
    # Enum
    return GraphQLInputField(field_type)


@convert.register(MagqlNonNull)
def _(magql_nonnull, type_map):
    return GraphQLNonNull(convert(magql_nonnull.type_, type_map))


@convert.register(MagqlList)
def _(magql_list, type_map):
    return GraphQLList(convert(magql_list.type_, type_map))


@convert.register(str)
def _(str_, type_map):
    if str_ in type_map:
        return type_map[str_]
    else:
        raise KeyError(f"String, {str_}, not in registered MagqlTypes")


@convert.register(MagqlEnumType)
def _(magql_enum, type_map):
    if magql_enum.name in type_map:
        return type_map[magql_enum.name]
    enum_type = GraphQLEnumType(magql_enum.name, magql_enum.values)
    type_map[magql_enum.name] = enum_type
    return enum_type


@convert.register(MagqlArgument)
def _(magql_arg, type_map):
    return GraphQLArgument(convert(magql_arg.type_, type_map), magql_arg.default_value)


@convert.register(MagqlString)
def _(magql_string, type_map):
    return GraphQLString


@convert.register(MagqlID)
def _(magql_id, type_map):
    return GraphQLID


@convert.register(MagqlInt)
def _(magql_int, type_map):
    gql_int = GraphQLInt
    if magql_int.parse_value:
        gql_int.parse_value = magql_int.parse_value
    return gql_int


@convert.register(MagqlBoolean)
def _(magql_boolean, type_map):
    return GraphQLBoolean


@convert.register(MagqlFloat)
def _(magql_float, type_map):
    gql_float = GraphQLFloat

    if magql_float.parse_value:
        gql_float.parse_value = magql_float.parse_value
    return gql_float


@convert.register(MagqlUnionType)
def _(magql_union, type_map):
    if magql_union.name in type_map:
        return type_map[magql_union.name]
    types = []

    for type in magql_union.types:
        if isinstance(type, str):
            types.append(type_map[type])
        else:
            types.append(type)
    gql_union = GraphQLUnionType(
        magql_union.name,
        types,
        # magql_union.resolve_types(magql_union.table_types, type_map),
        magql_union.resolve_types,
    )

    type_map[magql_union.name] = gql_union
    return gql_union
