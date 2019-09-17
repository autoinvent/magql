from inflection import camelize
from inflection import pluralize
from marshmallow_sqlalchemy import field_for
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
from magql.resolver_factory import CreateResolver
from magql.resolver_factory import DECIMALResolver
from magql.resolver_factory import DeleteResolver
from magql.resolver_factory import EnumResolver
from magql.resolver_factory import ManyResolver
from magql.resolver_factory import Resolver
from magql.resolver_factory import SingleResolver
from magql.resolver_factory import SQLAlchemyTableUnionResolver
from magql.resolver_factory import UpdateResolver


def is_rel_required(rel):
    calc_keys = rel._calculated_foreign_keys
    fk = rel._user_defined_foreign_keys.union(calc_keys).pop()
    return not fk.nullable


# TODO: refactor ManagerCollection so it seamlessly integrates regular
# and table managers
class MagqlTableManagerCollection:
    def __init__(
        self,
        tables,
        managers=None,
        default_create_resolver=CreateResolver,
        default_update_resolver=UpdateResolver,
        default_delete_resolver=DeleteResolver,
        default_single_resolver=SingleResolver,
        default_many_resolver=ManyResolver,
    ):

        self.default_create_resolver = default_create_resolver
        self.default_update_resolver = default_update_resolver
        self.default_delete_resolver = default_delete_resolver
        self.default_single_resolver = default_single_resolver
        self.default_many_resolver = default_many_resolver

        self.manager_map = {}
        for _table_name, table in tables.items():
            if managers and table in managers:
                manager = managers[table]
            else:
                manager = self.generate_manager(table)
                # skip tables that do not have a manager
            if manager:
                manager.generate_validation_schema()
                manager.to_magql()
            self.manager_map[table] = manager

        for _table, manager in self.manager_map.items():
            if manager:
                manager.add_rels(self.manager_map)

        self.magql_name_to_table = {}
        self.generate_check_delete()

    def generate_check_delete(self):
        check_delete_manager = MagqlManager("checkDelete")

        self.magql_names = []
        for _magql_name, manager in self.manager_map.items():
            if manager:
                self.magql_names.append(manager.magql_name)

        for _magql_name, manager in self.manager_map.items():
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
            CheckDeleteResolver(self.manager_map),
        )
        self.manager_map["checkDelete"] = check_delete_manager

    def generate_manager(self, table):
        try:
            get_mapper(table)
        except ValueError:
            # TODO: Replace with logs
            # print(f"No Mapper for table {table.name}")
            return
        return MagqlTableManager(
            table,
            create_resolver=self.default_create_resolver,
            update_resolver=self.default_update_resolver,
            delete_resolver=self.default_delete_resolver,
            single_resolver=self.default_single_resolver,
            many_resolver=self.default_many_resolver,
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
    def __init__(
        self,
        table,
        magql_name=None,
        create_resolver=CreateResolver,
        update_resolver=UpdateResolver,
        delete_resolver=DeleteResolver,
        single_resolver=SingleResolver,
        many_resolver=ManyResolver,
    ):
        super(MagqlTableManager, self).__init__(
            magql_name if magql_name is not None else camelize(table.name)
        )  # magql_object_name
        # Throws ValueError if it cannot find a table
        self.table_class = get_mapper(table).class_
        self.table = table
        self.table_name = table.name
        self.validators = {}

        self.create_resolver = create_resolver
        self.update_resolver = update_resolver
        self.delete_resolver = delete_resolver
        self.single_resolver = single_resolver
        self.many_resolver = many_resolver

        self.validation_schema = None

        self.generate_magql_types()

        # self.generate_magql_types()

    def validate_field(self, field_name):
        """
        Validation functions must raise a ValidationError when there is an error
        :param field_name: The name of the field that's validation field is changing
        :return:
        """

        def validator_decorator(validate_function):
            field_validators = self.validators.get(field_name, [])
            field_validators.append(validate_function)
            self.validators[field_name] = field_validators

        return validator_decorator

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

    def generate_validation_schema(self):

        # validation_schema_overrides =get_validator_overrides(table_class)

        validation_schema_overrides = {
            "Meta": type("Meta", (object,), {"model": self.table_class})  # noqa: E501
        }

        for field_name, validators in self.validators.items():
            validation_schema_overrides[field_name] = field_for(
                self.table_class, field_name, validate=validators
            )

        self.validation_schema = type(
            self.magql_name + "Schema", (ModelSchema,), validation_schema_overrides
        )()

        if self.create:
            self.create.resolve.schema = self.validation_schema
        if self.update:
            self.update.resolve.schema = self.validation_schema

    def generate_create_mutation(self):
        primary_key = tuple(
            map(lambda x: x.name, inspect(self.table_class).primary_key)
        )

        # TODO: Move backend auth functions into manager collection
        self.create = MagqlField(
            self.magql_name + "Payload",
            {"input": MagqlArgument(MagqlNonNull(self.magql_name + "InputRequired"))},
            self.create_resolver(self.table, self.validation_schema, primary_key),
        )

    def generate_update_mutation(self):
        self.update = MagqlField(
            self.magql_name + "Payload",
            {
                "id": MagqlArgument(MagqlNonNull("Int")),
                "input": MagqlArgument(MagqlNonNull(self.magql_name + "Input")),
            },
            self.update_resolver(self.table, self.validation_schema),
        )

    def generate_delete_mutation(self):
        self.delete = MagqlField(
            self.magql_name + "Payload",
            {"id": MagqlArgument(MagqlNonNull("Int"))},
            self.delete_resolver(self.table),
        )

    def generate_single_query(self):
        self.single = MagqlField(
            self.magql_name,
            {"id": MagqlArgument(MagqlNonNull("Int"))},
            self.single_resolver(self.table),
        )

    def generate_many_query(self):
        self.many = MagqlField(
            MagqlList(self.magql_name),
            {
                "filter": MagqlArgument(self.magql_name + "Filter"),
                "sort": MagqlArgument(
                    MagqlList(MagqlNonNull(self.magql_name + "Sort"))
                ),
            },
            self.many_resolver(self.table),
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
            # TODO: Replace with logs
            # print(f"No Mapper for table {self.table.name}")
            return

        for rel_name, rel in table_mapper.relationships.items():
            rel_table = rel.target

            if rel_table in managers:
                rel_manager = managers[rel_table]
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
            input_required_field = input_field = "Int"

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
                    js_camelize(self.table_name): MagqlField(
                        self.magql_name, None, CamelResolver()
                    ),
                },
            )
        )