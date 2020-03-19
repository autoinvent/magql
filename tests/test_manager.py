import pytest
from inflection import camelize
from inflection import pluralize
from tests.conftest import base
from tests.conftest import Car
from tests.conftest import Hometown
from tests.conftest import House
from tests.conftest import Person
from tests.conftest import Status
from tests.conftest import Wealth

from magql.definitions import MagqlArgument
from magql.definitions import MagqlBoolean
from magql.definitions import MagqlEnumType
from magql.definitions import MagqlField
from magql.definitions import MagqlFloat
from magql.definitions import MagqlInputObjectType
from magql.definitions import MagqlInt
from magql.definitions import MagqlList
from magql.definitions import MagqlNonNull
from magql.definitions import MagqlObjectType
from magql.definitions import MagqlString
from magql.manager import MagqlTableManager
from magql.manager import MagqlTableManagerCollection
from magql.resolver_factory import CreateResolver
from magql.resolver_factory import DeleteResolver
from magql.resolver_factory import ManyResolver
from magql.resolver_factory import SingleResolver
from magql.resolver_factory import UpdateResolver


def check_magql_types(manager):
    magql_name = manager.magql_name
    assert isinstance(manager.magql_types[magql_name], MagqlObjectType)
    assert isinstance(manager.magql_types[magql_name + "Input"], MagqlInputObjectType)
    assert isinstance(
        manager.magql_types[magql_name + "InputRequired"], MagqlInputObjectType
    )
    assert isinstance(manager.magql_types[magql_name + "Filter"], MagqlInputObjectType)
    assert isinstance(manager.magql_types[magql_name + "Sort"], MagqlEnumType)


def bad_manager_collection():
    table = {}
    for table_name, _table in base.metadata.tables.items():
        if table_name == "BadClass" or table_name == "BadRelClass":
            table[table_name] = _table
    return MagqlTableManagerCollection(table)


@pytest.mark.parametrize("model", [House, Car, Person])
def test_default_table_manager(model):
    table = model.__table__
    table_name = model.__tablename__
    manager = MagqlTableManager(table)
    assert model is manager.table_class
    assert table is manager.table
    assert camelize(table_name) == manager.table_name
    assert table_name == manager.table_name
    check_magql_types(manager)


@pytest.mark.parametrize("model", [House, Car, Person])
def test_magql_name_override(model):
    table = model.__table__
    magql_name = model.__tablename__ + "Override"
    manager = MagqlTableManager(table, magql_name)
    assert magql_name == manager.magql_name
    check_magql_types(manager)


class CreateResolverOverride(CreateResolver):
    def resolve(self, parent, info, *args, **kwargs):
        pass


class DeleteResolverOverride(CreateResolver):
    def resolve(self, parent, info, *args, **kwargs):
        pass


class UpdateResolverOverride(CreateResolver):
    def resolve(self, parent, info, *args, **kwargs):
        pass


class ManyResolverOverride(CreateResolver):
    def resolve(self, parent, info, *args, **kwargs):
        pass


class SingleResolverOverride(CreateResolver):
    def resolve(self, parent, info, *args, **kwargs):
        pass


@pytest.mark.parametrize("model", [House, Car, Person])
def test_generated_names(model):
    table = model.__table__
    manager = MagqlTableManager(table)

    assert manager.single_query_name == camelize(table.name, False)
    assert manager.many_query_name == camelize(pluralize(table.name), False)
    assert manager.create_mutation_name == "create" + manager.magql_name
    assert manager.update_mutation_name == "update" + manager.magql_name
    assert manager.delete_mutation_name == "delete" + manager.magql_name


@pytest.mark.parametrize("model", [House, Car, Person])
def test_generated_field(model):
    table = model.__table__
    manager = MagqlTableManager(table)
    assert isinstance(manager.create, MagqlField)
    assert isinstance(manager.update, MagqlField)
    assert isinstance(manager.delete, MagqlField)
    assert isinstance(manager.single, MagqlField)
    assert isinstance(manager.many, MagqlField)


@pytest.mark.parametrize("model", [House, Car, Person])
def test_generated_field_name(model):
    table = model.__table__
    manager = MagqlTableManager(table)

    assert manager.single.type_name == manager.magql_name + "Payload"
    assert manager.many.type_name == manager.magql_name + "ListPayload"
    assert manager.create.type_name == manager.magql_name + "Payload"
    assert manager.update.type_name == manager.magql_name + "Payload"
    assert manager.delete.type_name == manager.magql_name + "Payload"


@pytest.mark.parametrize("model", [House, Car, Person])
def test_generated_field_single_resolver_arguments(model):
    table = model.__table__
    manager = MagqlTableManager(table)

    single = manager.single

    assert "id" in single.args
    assert isinstance(single.args["id"], MagqlArgument)
    assert isinstance(single.args["id"].type_, MagqlNonNull)
    assert single.args["id"].type_.type_ == "Int"


@pytest.mark.parametrize("model", [House, Car, Person])
def test_generated_field_many_resolver_arguments(model):
    table = model.__table__
    manager = MagqlTableManager(table)

    many = manager.many

    assert "filter" in many.args
    assert "sort" in many.args

    assert isinstance(many.args["filter"], MagqlArgument)
    assert many.args["filter"].type_ == manager.magql_name + "Filter"

    assert isinstance(many.args["sort"], MagqlArgument)
    assert isinstance(many.args["sort"].type_, MagqlList)
    assert isinstance(many.args["sort"].type_.type_, MagqlNonNull)
    assert many.args["sort"].type_.type_.type_ == manager.magql_name + "Sort"


@pytest.mark.parametrize("model", [House, Car, Person])
def test_generated_field_create_resolver_arguments(model):
    table = model.__table__
    manager = MagqlTableManager(table)

    create = manager.create

    assert "input" in create.args
    assert isinstance(create.args["input"], MagqlArgument)
    assert isinstance(create.args["input"].type_, MagqlNonNull)
    assert create.args["input"].type_.type_ == manager.magql_name + "InputRequired"


@pytest.mark.parametrize("model", [House, Car, Person])
def test_generated_field_update_resolver_arguments(model):
    table = model.__table__
    manager = MagqlTableManager(table)

    update = manager.update

    assert "input" in update.args
    assert isinstance(update.args["input"], MagqlArgument)
    assert isinstance(update.args["input"].type_, MagqlNonNull)
    assert update.args["input"].type_.type_ == manager.magql_name + "Input"

    assert "id" in update.args
    assert isinstance(update.args["id"], MagqlArgument)
    assert isinstance(update.args["id"].type_, MagqlNonNull)
    assert update.args["id"].type_.type_ == "Int"


@pytest.mark.parametrize("model", [House, Car, Person])
def test_generated_field_delete_resolver_arguments(model):
    table = model.__table__
    manager = MagqlTableManager(table)

    delete = manager.delete

    assert "id" in delete.args
    assert isinstance(delete.args["id"], MagqlArgument)
    assert isinstance(delete.args["id"].type_, MagqlNonNull)
    assert delete.args["id"].type_.type_ == "Int"


@pytest.mark.parametrize("model", [House, Car, Person])
def test_generated_field_resolvers(model):
    table = model.__table__
    manager = MagqlTableManager(table)

    assert isinstance(manager.single.resolve, SingleResolver)
    assert isinstance(manager.many.resolve, ManyResolver)
    assert isinstance(manager.create.resolve, CreateResolver)
    assert isinstance(manager.update.resolve, UpdateResolver)
    assert isinstance(manager.delete.resolve, DeleteResolver)


@pytest.mark.parametrize("model", [House, Car, Person])
def test_return_types(model):
    table = model.__table__
    manager = MagqlTableManager(table)

    assert manager.single_query_name == camelize(table.name, False)
    assert manager.many_query_name == camelize(pluralize(table.name), False)
    assert manager.create_mutation_name == "create" + manager.magql_name
    assert manager.update_mutation_name == "update" + manager.magql_name
    assert manager.delete_mutation_name == "delete" + manager.magql_name


@pytest.mark.parametrize("model", [House, Car, Person])
def test_resolver_overrides(model):
    table = model.__table__
    manager = MagqlTableManager(
        table,
        None,
        CreateResolverOverride(table),
        UpdateResolverOverride(table),
        DeleteResolverOverride(table),
        SingleResolverOverride(table),
        ManyResolverOverride(table),
    )
    assert isinstance(manager.create.resolve, CreateResolverOverride)
    assert isinstance(manager.update.resolve, UpdateResolverOverride)
    assert isinstance(manager.delete.resolve, DeleteResolverOverride)
    assert isinstance(manager.single.resolve, SingleResolverOverride)
    assert isinstance(manager.many.resolve, ManyResolverOverride)


@pytest.mark.parametrize("model", [House, Car, Hometown, Status, Wealth, Person])
def test_add_rels(model, manager_collection):
    input_required_types = [MagqlInt, MagqlString, MagqlBoolean, MagqlFloat]
    input_required_strings = ["String", "Int", "Boolean", "Float"]
    for v in (
        manager_collection.manager_map[model.__tablename__]
        .magql_types[f"{model.__tablename__}InputRequired"]
        .fields.values()
    ):
        if isinstance(v.type_name, MagqlNonNull) or isinstance(v.type_name, MagqlList):
            field_type = v.type_name.type_
        else:
            field_type = v.type_name
        if type(field_type) in input_required_types:
            check_type = input_required_types[
                input_required_types.index(type(field_type))
            ]
        else:
            check_type = input_required_strings[
                input_required_strings.index(field_type)
            ]
        if isinstance(field_type, str):
            assert field_type == check_type
        else:
            assert isinstance(field_type, check_type)


def test_magql_name_rel_override(manager_collection):
    assert (
        manager_collection.manager_map["Person"]
        .magql_types["Person"]
        .fields["poBox"]
        .type_name
        == "POBox"
    )


def test_custom_fields(manager_collection):
    assert (
        manager_collection.manager_map["pobox"]
        .magql_types["POBox"]
        .fields["customField"]
    )


def test_bad_rels():
    with pytest.raises(KeyError):
        bad_manager_collection()
