from inflection import camelize
from inflection import pluralize
from marshmallow_sqlalchemy import ModelSchema
from sqlalchemy import DECIMAL
from sqlalchemy import inspect
from sqlalchemy_utils import get_mapper

from magql.definitions import js_camelize
from magql.definitions import MagqlArgument
from magql.definitions import MagqlEnumType
from magql.definitions import MagqlField
from magql.definitions import MagqlInputField
from magql.definitions import MagqlInputObjectType
from magql.definitions import MagqlList
from magql.definitions import MagqlNonNull
from magql.definitions import MagqlObjectType
from magql.definitions import MagqlUnionType
from magql.magql_filter import RelFilter
from magql.magql_type import get_magql_filter_type
from magql.magql_type import get_magql_required_type
from magql.magql_type import get_magql_type
from magql.resolver_factory import CamelResolver
from magql.resolver_factory import CheckDeleteResolver
from magql.resolver_factory import CheckDeleteUnionResolver
from magql.resolver_factory import CreateResolver
from magql.resolver_factory import DECIMALResolver
from magql.resolver_factory import DeleteResolver
from magql.resolver_factory import EnumResolver
from magql.resolver_factory import ManyResolver
from magql.resolver_factory import Resolver
from magql.resolver_factory import SingleResolver
from magql.resolver_factory import UpdateResolver


def is_rel_required(rel):
    calc_keys = rel._calculated_foreign_keys
    fk = rel._user_defined_foreign_keys.union(calc_keys).pop()
    return not fk.nullable


class MagqlTableManagerCollection:
    def __init__(self, tables, managers=None):
        self.manager_map = {}
        for _table_name, table in tables.items():
            if managers and table in managers:
                self.manager_map[table] = managers[table]
            else:
                self.generate_manager(table)
        for _table, manager in self.manager_map.items():
            manager.add_rels(self.manager_map)

        self.generate_check_delete()

    def generate_check_delete(self):
        check_delete_manager = MagqlManager("checkDelete")

        types = [
            manager.magql_name for _magql_name, manager in self.manager_map.items()
        ]

        table_types = {}
        for _magql_name, manager in self.manager_map.items():
            if isinstance(manager, MagqlTableManager):
                table_types[manager.magql_name] = manager.table

        check_delete_manager.magql_types["CheckDeleteUnion"] = MagqlUnionType(
            "CheckDeleteUnion", types, CheckDeleteUnionResolver, table_types
        )

        check_delete_manager.query.fields["checkDelete"] = MagqlField(
            MagqlList("CheckDeleteUnion"),
            {
                "tableName": MagqlArgument("String"),
                "id": MagqlArgument(MagqlNonNull("Int")),
            },
            CheckDeleteResolver(self.manager_map),
        )
        self.manager_map["checkDelete"] = check_delete_manager

    def generate_manager(self, table):
        try:
            get_mapper(table)
        except ValueError:
            print(f"No Mapper for table {table.name}")
            return
        self.manager_map[table] = MagqlTableManager(table)


class MagqlManager:
    def __init__(self, magql_name):
        self.query = MagqlObjectType("Query")
        self.mutation = MagqlObjectType("Mutation")
        self.magql_types = {}
        self.magql_name = magql_name


class MagqlTableManager(MagqlManager):
    def __init__(
        self,
        table,
        magql_name=None,
        magql_field_name=None,
        magql_field_name_plural=None,
    ):
        # Throws ValueError if it cannot find a table
        self.table_class = get_mapper(table).class_

        self.query = MagqlObjectType("Query")
        self.mutation = MagqlObjectType("Mutation")
        self.table = table
        self.table_name = table.name
        self.magql_name = (
            magql_name if magql_name is not None else camelize(self.table_name)
        )  # magql_object_name
        self.magql_field_name = magql_field_name
        self.magql_field_name_plural = magql_field_name_plural

        # convert to list of magql types than will be converted
        self.magql_types = {}
        self._generate_validation_schema()
        self.gen_magql_fields()

    # def create_resolver(self):
    #     return

    def single_query_name(self):
        return js_camelize(self.table.name)

    def many_query_name(self):
        return js_camelize(pluralize(self.table.name))

    def _generate_validation_schema(self):

        # validation_schema_overrides =get_validator_overrides(table_class)

        validation_schema_overrides = {
            "Meta": type("Meta", (object,), {"model": self.table_class})  # noqa: E501
        }

        self.validation_schema = type(
            self.magql_name + "Schema", (ModelSchema,), validation_schema_overrides
        )

    def gen_magql_fields(self):

        primary_key = tuple(
            map(lambda x: x.name, inspect(self.table_class).primary_key)
        )

        self.mutation.fields["create" + self.magql_name] = MagqlField(
            self.magql_name + "Payload",
            {"input": MagqlArgument(MagqlNonNull(self.magql_name + "InputRequired"))},
            CreateResolver(self.table, self.validation_schema, primary_key),
        )
        self.mutation.fields["delete" + self.magql_name] = MagqlField(
            self.magql_name + "Payload",
            {"id": MagqlArgument(MagqlNonNull("Int"))},
            DeleteResolver(self.table, self.validation_schema),
        )
        self.mutation.fields["update" + self.magql_name] = MagqlField(
            self.magql_name + "Payload",
            {
                "id": MagqlArgument(MagqlNonNull("Int")),
                "input": MagqlArgument(MagqlNonNull(self.magql_name + "Input")),
            },
            UpdateResolver(self.table, self.validation_schema),
        )

        self.query.fields[self.single_query_name()] = MagqlField(
            self.magql_name,
            {"id": MagqlArgument(MagqlNonNull("Int"))},
            SingleResolver(self.table, self.validation_schema),
        )

        self.query.fields[self.many_query_name()] = MagqlField(
            MagqlList(self.magql_name),
            {
                "filter": MagqlArgument(self.magql_name + "Filter"),
                "sort": MagqlArgument(
                    MagqlList(MagqlNonNull(self.magql_name + "Sort"))
                ),
            },
            ManyResolver(self.table, self.validation_schema),
        )

        base = MagqlObjectType(self.magql_name)
        input = MagqlInputObjectType(self.magql_name + "Input")
        input_required = MagqlInputObjectType(
            self.magql_name + "InputRequired"
        )  # noqa: E501
        filter_ = MagqlInputObjectType(self.magql_name + "Filter")
        sort = MagqlEnumType(self.magql_name + "Sort")

        for col_name, col in self.table.c.items():
            if col.foreign_keys:
                continue
            field_name = js_camelize(col_name)
            magql_type = get_magql_type(col)
            required_magql_type = get_magql_required_type(col)
            base.fields[field_name] = MagqlField(
                magql_type, None, CamelResolver()
            )  # noqa: E501
            # TODO: Organize better method of having different resolvers
            # for different fields, probably move onto magql_type
            if isinstance(magql_type, MagqlEnumType):
                base.fields[field_name].resolve = EnumResolver()
            if isinstance(col.type, DECIMAL):
                base.fields[field_name].resolve = DECIMALResolver()
            if not col.primary_key:
                input.fields[field_name] = MagqlInputField(magql_type)
                input_required.fields[field_name] = MagqlInputField(
                    required_magql_type
                )  # noqa: E501
            filter_.fields[field_name] = MagqlInputField(
                get_magql_filter_type(col, magql_type)
            )
            sort.values[field_name + "_asc"] = (col_name + "_asc",)
            sort.values[field_name + "_desc"] = (col_name + "_desc",)

        self.magql_types[self.magql_name] = base

        self.magql_types[self.magql_name + "Input"] = input
        self.magql_types[self.magql_name + "InputRequired"] = input_required
        self.magql_types[self.magql_name + "Filter"] = filter_
        self.magql_types[self.magql_name + "Sort"] = sort

    # a manager map can be passed in to give information about
    # other managers, such as an overriden name, otherwise a default is used
    def add_rels(self, managers=None):
        try:
            table_mapper = get_mapper(self.table)
        except ValueError:
            print(f"No Mapper for table {self.table.name}")
            return

        for rel_name, rel in table_mapper.relationships.items():
            rel_table = rel.target

            rel_manager = None
            if rel_table in managers:
                rel_manager = managers[rel_table]
            direction = rel.direction.name
            required = is_rel_required(rel)

            field_name = js_camelize(rel_name)

            # use magql name of rel manager if it exists else use default name
            target_name = (
                rel_manager.magql_name if rel_manager else camelize(rel.target.name)
            )

            base_field = target_name
            input_required_field = input_field = "Int"

            if "TOMANY" in direction:
                base_field = MagqlList(base_field)
                input_required_field = MagqlList(input_required_field)
                input_field = MagqlList(input_field)
            elif required:
                input_required_field = MagqlNonNull(input_required_field)

            self.magql_types[self.magql_name + "InputRequired"].fields[
                field_name
            ] = MagqlInputField(
                input_required_field
            )  # noqa: E501
            self.magql_types[self.magql_name + "Input"].fields[
                field_name
            ] = MagqlInputField(input_field)
            self.magql_types[self.magql_name].fields[field_name] = MagqlField(
                base_field, None, Resolver()
            )
            self.magql_types[self.magql_name + "Filter"].fields[
                field_name
            ] = MagqlInputField(RelFilter)

        payload = MagqlNonNull(
            MagqlObjectType(
                self.magql_name + "Payload",
                {
                    "errors": MagqlField(MagqlList("String")),
                    js_camelize(self.table_name): MagqlField(
                        self.magql_name, None, CamelResolver()
                    ),
                },
            )
        )
        self.magql_types[self.magql_name + "Payload"] = payload
