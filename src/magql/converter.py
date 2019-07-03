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
from magql.definitions import MagqlWrappingType


class Convert:
    def __init__(self, manager_collection):
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

        managers = manager_collection.manager_map

        self.generate_type_map(managers)

        for _magql_name, manager in managers.items():

            self.convert_manager(manager)

    def generate_type_map(self, managers):
        magql_type_map = {
            "String": MagqlString(),
            "Int": MagqlInt(),
            "Boolean": MagqlBoolean(),
            "Float": MagqlFloat(),
            "ID": MagqlID(),
        }
        for _magql_name, manager in managers.items():
            for type_name, type_ in manager.magql_types.items():
                magql_type_map[type_name] = type_
        for _magql_name, manager in managers.items():
            for _type_name, type_ in manager.magql_types.items():
                wrapping_types_stack = []
                while isinstance(type_, MagqlWrappingType):
                    wrapping_types_stack.append(type(type_))
                    type_ = type_.type_
                if isinstance(type_, MagqlEnumType):
                    continue
                for _field_name, field in type_.fields.items():
                    wrapping_types_stack2 = []
                    ret_field = field.type_name
                    while isinstance(ret_field, MagqlWrappingType):
                        wrapping_types_stack2.append(type(ret_field))
                        ret_field = ret_field.type_
                    if isinstance(ret_field, str):
                        ret_field = magql_type_map[ret_field]
                        while wrapping_types_stack2:
                            ret_field = wrapping_types_stack2.pop()(ret_field)
                        field.type_name = ret_field
        for _magql_name, manager in managers.items():
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
        raise KeyError("String name not in type_map")


@convert.register(MagqlEnumType)
def _(enum, type_map):
    if enum.name in type_map:
        return type_map[enum.name]
    enum_type = GraphQLEnumType(enum.name, enum.values)
    type_map[enum.name] = enum_type
    return enum_type


@convert.register(MagqlArgument)
def _(arg, type_map):
    return GraphQLArgument(convert(arg.type_, type_map), arg.default_value)


@convert.register(MagqlString)
def _(arg, type_map):
    return GraphQLString


@convert.register(MagqlID)
def _(arg, type_map):
    return GraphQLID


@convert.register(MagqlInt)
def _(arg, type_map):
    return GraphQLInt


@convert.register(MagqlBoolean)
def _(arg, type_map):
    return GraphQLBoolean


@convert.register(MagqlFloat)
def _(arg, type_map):
    return GraphQLFloat
