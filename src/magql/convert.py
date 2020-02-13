from graphql import GraphQLBoolean
from graphql import GraphQLFloat
from graphql import GraphQLID
from graphql import GraphQLInt
from graphql import GraphQLObjectType
from graphql import GraphQLSchema
from graphql import GraphQLString

from .definitions import MagqlBoolean
from .definitions import MagqlEnumType
from .definitions import MagqlField
from .definitions import MagqlFile
from .definitions import MagqlFloat
from .definitions import MagqlID
from .definitions import MagqlInputField
from .definitions import MagqlInt
from .definitions import MagqlString
from .definitions import MagqlUnionType
from .definitions import MagqlWrappingType


class Convert:
    """
    The Convert class is responsible for taking in a finalized magql
    schema and turning it into a graphql schema. Takes in the magql
    schema in the form of a list of managers. The magql schema from
    each manager is extracted and built into one magql schema. That
    schema is then converted to a graphql schema once
    :func:`generate_schema` is called.
    """

    def __init__(self, manager_list):
        """
        Generates a graphql schema based on the passed list of managers
        :param manager_list: A list of managers from which the Magql
        schema is extracted and turned into a graphql schema
        """
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
        """
        Creates a mapping of String representations of Magql Types to
        the Magql types. Then converts the magql_types to grapqhl types.
        :param managers: The list of managers used to generate the
        GraphQL schema
        """
        magql_type_map = {
            "String": MagqlString(),
            "Int": MagqlInt(MagqlInt.parse_value_accepts_string),
            "Boolean": MagqlBoolean(),
            "Float": MagqlFloat(MagqlFloat.parse_value_accepts_string),
            "File": MagqlFile(),
            "ID": MagqlID(),
        }
        # Gather all magql types in magql_type_map
        for manager in managers:
            if not manager:
                continue
            for type_name, type_ in manager.magql_types.items():
                magql_type_map[type_name] = type_
        # replace string type representations with references to correct type
        for manager in managers:
            if not manager:
                continue
            for _type_name, type_ in manager.magql_types.items():
                Convert.convert_str_leafs(type_, magql_type_map)
            Convert.convert_str_leafs(manager.query, magql_type_map)
            Convert.convert_str_leafs(manager.mutation, magql_type_map)

        # TODO: Look into whether this convert_types is necessary and,
        # if it is whether or not it should be here
        for manager in managers:
            if manager:
                self.convert_types(manager)

    def convert_types(self, manager):
        for _magql_name, magql_type in manager.magql_types.items():
            magql_type.convert(self.type_map)
        for _magql_name, magql_type in manager.magql_types.items():
            magql_type.convert(self.type_map)

    def generate_mutations(self, manager):
        for _mutation_name, magql_field in manager.mutation.fields.items():
            for _argument_name, argument in magql_field.args.items():
                argument.convert(self.type_map)

            if magql_field.type_name not in self.type_map:
                pass

    def convert_manager(self, manager):
        # TODO: Consider moving the conversion of the query into the
        #  manager
        for query_name, query in manager.query.fields.items():
            self.gql_queries[query_name] = query.convert(self.type_map)

        for mut_name, mutation in manager.mutation.fields.items():
            self.gql_mutations[mut_name] = mutation.convert(self.type_map)

    def generate_schema(self):
        """
        Finalizes the GraphQL schema by generating the GraphQLSchema
        :return: The finalized GraphQL schema
        """
        query = GraphQLObjectType("Query", self.gql_queries)
        mutation = GraphQLObjectType("Mutation", self.gql_mutations)
        return GraphQLSchema(query, mutation)
