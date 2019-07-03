# from graphql import GraphQLArgument
# from graphql import GraphQLEnumType
# from graphql import GraphQLField
# from graphql import GraphQLInputField
# from graphql import GraphQLInputObjectType
# from graphql import GraphQLInt
# from graphql import GraphQLList
# from graphql import GraphQLNonNull
# from graphql import GraphQLObjectType
# from graphql import GraphQLString
# from inflection import camelize
# from inflection import pluralize
# from marshmallow_sqlalchemy import ModelSchema
# from sqlalchemy_utils import get_mapper
#
# from magql.filter import RelFilter
# from magql.get_type import get_filter_type
# from magql.get_type import get_required_type
# from magql.get_type import get_type
# from magql.resolver_factory import CamelResolver
# from magql.resolver_factory import CreateResolver
# from magql.resolver_factory import DeleteResolver
# from magql.resolver_factory import EnumResolver
# from magql.resolver_factory import ManyResolver
# from magql.resolver_factory import Resolver
# from magql.resolver_factory import SingleResolver
# from magql.resolver_factory import UpdateResolver
# from magql.validator import get_validator_overrides
#
#
# class Manager:  # noqa: E501
#     def __init__(self, query_fields, mutation_fields):
#
#         self.query_fields = query_fields
#         self.mutation_fields = mutation_fields
#
#
# def js_camelize(word):
#     # add config check
#     # disable while camelcasing resolvers aren't added
#     return camelize(word, False)
#
#
# def is_rel_required(rel):
#     calc_keys = rel._calculated_foreign_keys
#     fk = rel._user_defined_foreign_keys.union(calc_keys).pop()
#     return not fk.nullable
#
#
# class TableManager(Manager):
#     def __init__(self, table, rel_managers=None, type_defs=None):
#         """
#             :param table:
#             :param rel_managers: rel_managers is a mapping of tables to
#             managers that is used to set the relationship fields of the gql
#             objects. Only rels that have managers in the dict can and will
#             be added to the gql objects. If it is not passed no rels will
#             be generated. They can be added later.
#             """
#         super(TableManager, self).__init__({}, {})
#         self.type_defs = type_defs
#         self.table = table
#         self._generate_fields()
#         self._generate_gql_types()
#         self._generate_validation_schema()
#         self.add_rels(rel_managers)
#         self.generate_mutation_fields()
#         self.generate_query_fields()
#
#     def single_query_name(self):
#         return js_camelize(self.table.name)
#
#     def many_query_name(self):
#         return js_camelize(pluralize(self.table.name))
#
#     def create_mutation_name(self):
#         return "create" + js_camelize(self.table.name)
#
#     def update_mutation_name(self):
#         return "update" + js_camelize(self.table.name)
#
#     def delete_mutation_name(self):
#         return "delete" + js_camelize(self.table.name)
#
#     def create_resolver(self, resolver):
#         self.mutation_fields[self.create_mutation_name()].resolve = resolver
#
#     def delete_resolver(self, resolver):
#         self.mutation_fields[self.delete_mutation_name()].resolve = resolver
#
#     def update_resolver(self, resolver):
#         self.mutation_fields[self.update_mutation_name()].resolve = resolver
#
#     def single_resolver(self, resolver):
#         self.query_fields[self.single_query_name()].resolve = resolver
#
#     def many_resolver(self, resolver):
#         self.query_fields[self.many_query_name()].resolve = resolver
#
#     # Utilize parse to determine return gql values of the needed items and
#     # merge together with existing schema as necessary, then switch over to
#     # decorators to add the fieldName/ resolver
#     def field(self, *args):
#         def add_field(resolver):
#             # temp = parse(self.type_defs)
#             # field_name = args[0]
#             # field = GraphQLField()
#             # print(field, temp, field_name)
#
#             pass
#
#         return add_field
#
#     def generate_user_defined_fields(self):
#         pass
#
#     def generate_query_fields(self):
#
#         fields = {
#             self.single_query_name(): GraphQLField(
#                 self.base,
#                 {"id": GraphQLArgument(GraphQLNonNull(GraphQLString))},
#                 SingleResolver(self.table),
#             ),
#             self.many_query_name(): GraphQLField(
#                 GraphQLList(self.base),
#                 {
#                     "filter": GraphQLArgument(self.filter_),
#                     "sort": GraphQLArgument(
#                         GraphQLList(GraphQLNonNull(self.sort))
#                     ),  # noqa: E501
#                 },
#                 ManyResolver(self.table),
#             ),
#         }
#         self.query_fields = fields
#
#     def generate_mutation_fields(self):
#         fields = {}
#
#         id_arg = GraphQLArgument(GraphQLNonNull(GraphQLString))
#         input_arg = GraphQLArgument(GraphQLNonNull(self.input_))
#         required_input_arg = GraphQLArgument(
#             GraphQLNonNull(self.input_required)
#         )  # noqa: E501
#
#         create_args = {"input": required_input_arg}
#
#         update_args = {"input": input_arg}
#
#         delete_args = {"id": id_arg}
#         payload = self.payload
#
#         fields[self.create_mutation_name()] = GraphQLField(
#             payload,
#             create_args,
#             CreateResolver(self.table, self.validation_schema),  # noqa: E501
#         )
#         fields[self.delete_mutation_name()] = GraphQLField(
#             payload,
#             update_args,
#             UpdateResolver(self.table, self.validation_schema),  # noqa: E501
#         )
#         fields[self.update_mutation_name()] = GraphQLField(
#             payload,
#             delete_args,
#             DeleteResolver(self.table, self.validation_schema),  # noqa: E501
#         )
#
#         self.mutation_fields = fields
#
#     def add_rels(self, rel_managers):
#         if not rel_managers:
#             return
#         try:
#             table_mapper = get_mapper(self.table)
#         except ValueError:
#             print(f"No Mapper for table {self.table.name}")
#             return
#         for rel_name, rel in table_mapper.relationships.items():
#             direction = rel.direction.name
#             required = is_rel_required(rel)
#
#             # rel_object is used for queries so it must be recursive
#             if rel.target not in rel_managers:
#                 continue
#             rel_object = rel_managers[rel.target].base
#
#             # inputs are for mutations so should not be recursive
#             rel_input = GraphQLInt
#             rel_required_input = GraphQLInt
#
#             if "TOMANY" in direction:
#                 rel_object = GraphQLList(rel_object)
#                 rel_input = GraphQLList(rel_input)
#                 rel_required_input = GraphQLList(rel_required_input)
#             # 'TOMANY' cannot be required
#             elif required:
#                 rel_required_input = GraphQLNonNull(rel_required_input)
#
#             rel_name = js_camelize(rel_name)
#
#             self.input_required.fields[rel_name] = GraphQLInputField(
#                 rel_required_input
#             )  # noqa: E501
#             self.input_.fields[rel_name] = GraphQLInputField(rel_input)
#             self.base.fields[rel_name] = GraphQLField(
#                 rel_object, None, Resolver()
#             )  # noqa: E501
#             self.filter_.fields[rel_name] = GraphQLInputField(RelFilter)
#
#     def _generate_validation_schema(self):
#         try:
#             table_class = get_mapper(self.table).class_
#         except ValueError:
#             print(self.table)
#             return
#
#         validation_schema_overrides = get_validator_overrides(table_class)
#         validation_schema_overrides["Meta"] = type(
#             "Meta", (object,), {"model": table_class}
#         )  # noqa: E501
#
#         camelized = camelize(self.table.name)
#
#         self.validation_schema = type(
#             camelized + "Schema", (ModelSchema,), validation_schema_overrides
#         )  # noqa: E501
#
#     # TODO: Move convert code out of manager
#     def _generate_gql_types(self):
#         camelized = camelize(self.table.name)
#         gql_object = GraphQLObjectType(camelized, self._fields)
#         self.base = gql_object
#         self.filter_ = GraphQLInputObjectType(
#             camelized + "Filter", self._filter_fields
#         )  # noqa: E501
#         self.sort = GraphQLEnumType(camelized + "Sort", self._sort_fields)
#         self.input_ = GraphQLInputObjectType(
#             camelized + "Input", self._input_fields
#         )  # noqa: E501
#         self.input_required = GraphQLInputObjectType(
#             camelized + "InputRequired", self._required_input_fields
#         )
#         self.payload = GraphQLNonNull(
#             GraphQLObjectType(
#                 camelized + "Payload",
#                 {
#                     "error": GraphQLList(GraphQLString),
#                     camelize(self.table.name, False): gql_object,
#                 },
#             )
#         )
#         pass
#
#     def _generate_fields(self):
#         self._fields = {}
#         self._required_input_fields = {}
#         self._input_fields = {}
#         self._filter_fields = {}
#         self._sort_fields = {}
#         for col_name, col in self.table.c.items():
#             if col.foreign_keys:
#                 pass
#             else:
#                 col_name = js_camelize(col_name)
#
#                 base_type = get_type(col)
#                 self._fields[col_name] = GraphQLField(
#                     base_type, None, CamelResolver()
#                 )  # noqa: E501
#
#                 # TODO: Refactor how enums are handled
#                 if isinstance(base_type, GraphQLEnumType):
#                     self._fields[col_name].resolve = EnumResolver()
#                 self._required_input_fields[col_name] = GraphQLInputField(
#                     get_required_type(col, base_type)
#                 )
#                 self._input_fields[col_name] = GraphQLInputField(base_type)
#                 self._filter_fields[col_name] = get_filter_type(col, base_type)
#                 self._sort_fields[col_name + "_asc"] = (col_name + "_asc",)
#                 self._sort_fields[col_name + "_desc"] = (col_name + "_desc",)
#
#
# # TODO: Add Model Manager
# class ModelManager(Manager):
#     def __init__(self, model):
#         pass
