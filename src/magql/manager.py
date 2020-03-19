import logging

from inflection import camelize
from inflection import pluralize
from sqlalchemy_utils import get_mapper

from magql.definitions import js_camelize
from magql.definitions import MagqlArgument
from magql.definitions import MagqlEnumType
from magql.definitions import MagqlField
from magql.definitions import MagqlInputField
from magql.definitions import MagqlInputObjectType
from magql.definitions import MagqlInt
from magql.definitions import MagqlList
from magql.definitions import MagqlNonNull
from magql.definitions import MagqlObjectType
from magql.definitions import MagqlUnionType
from magql.filter import RelFilter
from magql.resolver_factory import CamelResolver
from magql.resolver_factory import CheckDeleteResolver
from magql.resolver_factory import CountResolver
from magql.resolver_factory import CreateResolver
from magql.resolver_factory import DeleteResolver
from magql.resolver_factory import EnumResolver
from magql.resolver_factory import ManyResolver
from magql.resolver_factory import Resolver
from magql.resolver_factory import ResultResolver
from magql.resolver_factory import SingleResolver
from magql.resolver_factory import SQLAlchemyTableUnionResolver
from magql.resolver_factory import UpdateResolver
from magql.type import get_magql_filter_type
from magql.type import get_magql_required_type
from magql.type import get_magql_type


def is_rel_required(rel):
    calc_keys = rel._calculated_foreign_keys
    fk = rel._user_defined_foreign_keys.union(calc_keys).pop()
    return not fk.nullable


# TODO: refactor ManagerCollection so it seamlessly integrates regular
# and table managers
class MagqlTableManagerCollection:
    """
    The MagqlTableManagerCollection creates a grouping of related
    managers from the tables that are passed in, if a corresponding
    manager is not already created.
    """

    def __init__(
        self,
        tables,
        managers=None,
        create_resolver=CreateResolver,
        update_resolver=UpdateResolver,
        delete_resolver=DeleteResolver,
        single_resolver=SingleResolver,
        many_resolver=ManyResolver,
    ):
        """
        Creates the managers needed to manange the Magql schema,
        if they have not already been created.
        :param tables: A list of tables to create managers for
        :param managers: A mapping of tables to pre-existing managers
        :param create_resolver: The class to use as the create resolver
        :param update_resolver: The class to use as the update resolver
        :param delete_resolver: The class to use as the delete resolver
        :param single_resolver: The class to use as the single resolver
        :param many_resolver: The class to use as the many resolver
        """
        self.create_resolver = create_resolver
        self.update_resolver = update_resolver
        self.delete_resolver = delete_resolver
        self.single_resolver = single_resolver
        self.many_resolver = many_resolver

        self.manager_map = {}
        for table_name, table in tables.items():
            if managers and table_name in managers:
                manager = managers[table_name]
            else:
                manager = self.generate_manager(table)

            # skip tables that do not have a manager
            if manager:
                manager.to_magql()

            self.manager_map[table_name] = manager

        for _table_name, manager in self.manager_map.items():
            if manager:
                manager.add_rels(self.manager_map)

        self.magql_name_to_table = {}
        self.generate_check_delete()
        self.generate_pagination()

    def generate_check_delete(self):
        check_delete_manager = MagqlManager("checkDelete")

        self.magql_names = []
        for _table_name, manager in self.manager_map.items():
            if manager:
                self.magql_names.append(manager.magql_name)

        for _table_name, manager in self.manager_map.items():
            if isinstance(manager, MagqlTableManager) and manager:
                self.magql_name_to_table[manager.magql_name] = manager.table

        check_delete_manager.magql_types["SQLAlchemyTableUnion"] = MagqlUnionType(
            "SQLAlchemyTableUnion",
            self.magql_names,
            SQLAlchemyTableUnionResolver(self.magql_name_to_table),
        )

        check_delete_manager.query.fields["checkDelete"] = MagqlField(
            MagqlList("SQLAlchemyTableUnion"),
            {
                "tableName": MagqlArgument("String"),
                "id": MagqlArgument(MagqlNonNull("Int")),
            },
            CheckDeleteResolver(list(self.magql_name_to_table.values())),
        )
        self.manager_map["checkDelete"] = check_delete_manager

    def generate_pagination(self):
        page_manager = MagqlManager("PaginationManager")
        page_manager.magql_types["Page"] = MagqlInputObjectType(
            "Page",
            {
                "current": MagqlInputField(MagqlInt()),
                "per_page": MagqlInputField(MagqlInt()),
            },
        )
        self.manager_map["PaginationManager"] = page_manager

    def generate_manager(self, table):
        try:
            get_mapper(table)
        except ValueError:
            logging.getLogger(__name__).warning(f"No mapper for table {table.name!r}.")
            return
        return MagqlTableManager(
            table,
            create_resolver=self.create_resolver(table),
            update_resolver=self.update_resolver(table),
            delete_resolver=self.delete_resolver(table),
            single_resolver=self.single_resolver(table),
            many_resolver=self.many_resolver(table),
        )


class MagqlManager:
    def __init__(self, magql_name):
        self.query = MagqlObjectType("Query")
        self.mutation = MagqlObjectType("Mutation")
        self.magql_types = {}
        # The check delete union type resolver ( and likely more resolvers)
        # relies on the fact that the magql_name and the base object type
        # share the same name
        self.magql_name = magql_name


class MagqlTableManager(MagqlManager):
    """
    The manager used to manage a single sqlalchemy table
    """

    def __init__(
        self,
        table,
        magql_name=None,
        create_resolver=None,
        update_resolver=None,
        delete_resolver=None,
        single_resolver=None,
        many_resolver=None,
    ):
        """
        The manager for a single sqlalchemy table.
        :param table: The table that is being managed
        :param magql_name: Optional name override for how the table is
        referred to
        :param create_resolver: Optional override for create resolver
        :param update_resolver: Optional override for update resolver
        :param delete_resolver: Optional override for delete resolver
        :param single_resolver: Optional override for single resolver
        :param many_resolver: Optional override for many resolver
        """
        super().__init__(
            magql_name if magql_name is not None else camelize(table.name)
        )  # magql_object_name
        # Throws ValueError if it cannot find a table
        self.table_class = get_mapper(table).class_
        self.table = table
        self.table_name = table.name

        self.create_resolver = (
            create_resolver if create_resolver else CreateResolver(self.table)
        )
        self.update_resolver = (
            update_resolver if update_resolver else UpdateResolver(self.table)
        )
        self.delete_resolver = (
            delete_resolver if delete_resolver else DeleteResolver(self.table)
        )
        self.single_resolver = (
            single_resolver if single_resolver else SingleResolver(self.table)
        )
        self.many_resolver = (
            many_resolver if many_resolver else ManyResolver(self.table)
        )

        self.generate_magql_types()

    @property
    def single_query_name(self):
        if hasattr(self, "_single_query_name_override"):
            if callable(self._single_query_name_override):
                return self._single_query_name_override()
            else:
                return self._single_query_name_override
        return js_camelize(self.table.name)

    @single_query_name.setter
    def single_query_name(self, value):
        """
        Overrides the name of the single query to a custom value
        :param value: The name to change the single query to
        """
        self._single_query_name_override = value

    @property
    def many_query_name(self):
        if hasattr(self, "_many_query_name_override"):
            if callable(self._many_query_name_override):
                return self._many_query_name_override()
            else:
                return self._many_query_name_override
        return js_camelize(pluralize(self.table.name))

    @many_query_name.setter
    def many_query_name(self, value):
        """
       Overrides the name of the many query to a custom value
       :param value: The name to change the many query to
       """
        self._many_query_name_override = value

    @property
    def create_mutation_name(self):
        return "create" + self.magql_name

    @property
    def update_mutation_name(self):
        return "update" + self.magql_name

    @property
    def delete_mutation_name(self):
        return "delete" + self.magql_name

    def generate_create_mutation(self):
        # TODO: Move backend auth functions into manager collection
        self.create = MagqlField(
            self.magql_name + "Payload",
            {"input": MagqlArgument(MagqlNonNull(self.magql_name + "InputRequired"))},
            self.create_resolver,
        )

    def generate_update_mutation(self):
        self.update = MagqlField(
            self.magql_name + "Payload",
            {
                "id": MagqlArgument(MagqlNonNull("Int")),
                "input": MagqlArgument(MagqlNonNull(self.magql_name + "Input")),
            },
            self.update_resolver,
        )

    def generate_delete_mutation(self):
        self.delete = MagqlField(
            self.magql_name + "Payload",
            {"id": MagqlArgument(MagqlNonNull("Int"))},
            self.delete_resolver,
        )

    def generate_single_query(self):
        self.single = MagqlField(
            self.magql_name + "Payload",
            {"id": MagqlArgument(MagqlNonNull("Int"))},
            self.single_resolver,
        )

    def generate_many_query(self):
        self.many = MagqlField(
            self.magql_name + "ListPayload",
            {
                "filter": MagqlArgument(self.magql_name + "Filter"),
                "sort": MagqlArgument(
                    MagqlList(MagqlNonNull(self.magql_name + "Sort"))
                ),
                "page": MagqlArgument("Page"),
            },
            self.many_resolver,
        )

    def generate_types(self):
        base = MagqlObjectType(self.magql_name)
        input = MagqlInputObjectType(self.magql_name + "Input")
        input_required = MagqlInputObjectType(self.magql_name + "InputRequired")
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
            if not col.primary_key:
                input.fields[field_name] = MagqlInputField(magql_type)
                input_required.fields[field_name] = MagqlInputField(required_magql_type)
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

    def generate_magql_types(self):
        self.generate_create_mutation()
        self.generate_update_mutation()
        self.generate_delete_mutation()
        self.generate_single_query()
        self.generate_many_query()

        self.generate_types()

    # Allows fields to be added directly to mutation and query
    def to_magql(self):
        if self.create:
            self.mutation.fields[self.create_mutation_name] = self.create
        if self.update:
            self.mutation.fields[self.update_mutation_name] = self.update
        if self.delete:
            self.mutation.fields[self.delete_mutation_name] = self.delete
        if self.single:
            self.query.fields[self.single_query_name] = self.single
        if self.many:
            self.query.fields[self.many_query_name] = self.many

    # a manager map can be passed in to give information about
    # other managers, such as an overriden name, otherwise a default is used
    def add_rels(self, managers=None):
        try:
            table_mapper = get_mapper(self.table)
        except ValueError:
            logging.getLogger(__name__).warning(
                f"No mapper for table {self.table.name!r}."
            )
            return

        for rel_name, rel in table_mapper.relationships.items():
            rel_table = rel.target

            if rel_table.name in managers:
                rel_manager = managers[rel_table.name]
                if rel_manager is None:
                    continue
            else:
                rel_manager = None
            direction = rel.direction.name
            required = is_rel_required(rel)

            field_name = js_camelize(rel_name)

            # use magql name of rel manager if it exists else use default name
            target_name = (
                rel_manager.magql_name if rel_manager else camelize(rel.target.name)
            )

            base_field = target_name
            input_field_types = {
                str: "String",
                int: "Int",
                bool: "Boolean",
                float: "Float",
            }

            try:
                field_type = input_field_types[
                    rel_table.primary_key.columns.id.type.python_type
                ]
            except KeyError:
                raise KeyError(
                    "The value set as the primary key for the relationship is not valid"
                )

            input_required_field = input_field = field_type

            if "TOMANY" in direction:
                base_field = MagqlList(base_field)
                input_required_field = MagqlList(input_required_field)
                input_field = MagqlList(input_field)
            elif required:
                input_required_field = MagqlNonNull(input_required_field)

            if (
                field_name
                not in self.magql_types[self.magql_name + "InputRequired"].fields
            ):
                self.magql_types[self.magql_name + "InputRequired"].fields[
                    field_name
                ] = MagqlInputField(input_required_field)
            if field_name not in self.magql_types[self.magql_name + "Input"].fields:
                self.magql_types[self.magql_name + "Input"].fields[
                    field_name
                ] = MagqlInputField(input_field)
            if field_name not in self.magql_types[self.magql_name].fields:
                self.magql_types[self.magql_name].fields[field_name] = MagqlField(
                    base_field, None, Resolver()
                )
            if field_name not in self.magql_types[self.magql_name + "Filter"].fields:
                self.magql_types[self.magql_name + "Filter"].fields[
                    field_name
                ] = MagqlInputField(RelFilter)
        self.magql_types[self.magql_name + "Payload"] = MagqlNonNull(
            MagqlObjectType(
                self.magql_name + "Payload",
                {
                    "errors": MagqlField(MagqlList("String")),
                    "result": MagqlField(self.magql_name, None, ResultResolver()),
                },
            )
        )

        self.magql_types[self.magql_name + "ListPayload"] = MagqlNonNull(
            MagqlObjectType(
                self.magql_name + "ListPayload",
                {
                    "errors": MagqlField(MagqlList("String")),
                    "result": MagqlField(
                        MagqlList(self.magql_name), None, ResultResolver()
                    ),
                    "count": MagqlField("Int", None, CountResolver()),
                },
            )
        )
