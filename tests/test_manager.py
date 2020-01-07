import pytest
from inflection import camelize
from inflection import pluralize
from tests.conftest import base
from tests.conftest import Car
from tests.conftest import House
from tests.conftest import Person

from magql.definitions import MagqlEnumType
from magql.definitions import MagqlField
from magql.definitions import MagqlInputObjectType
from magql.definitions import MagqlObjectType
from magql.magql_manager import MagqlTableManager
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


@pytest.mark.parametrize("model", [House, Car, Person])
def test_default_table_manager(model):
    table = model.__table__
    table_name = model.__tablename__
    manager = MagqlTableManager(table)
    assert model is manager.table_class
    assert table is manager.table
    assert camelize(table_name) == manager.table_name
    assert table_name == manager.table_name
    assert manager.many_query_name == camelize(pluralize(table_name), False)
    assert manager.single_query_name == camelize(table_name, False)

    assert isinstance(manager.create.resolve, CreateResolver)
    assert isinstance(manager.create, MagqlField)
    assert isinstance(manager.update.resolve, UpdateResolver)
    assert isinstance(manager.update, MagqlField)
    assert isinstance(manager.delete.resolve, DeleteResolver)
    assert isinstance(manager.delete, MagqlField)
    assert isinstance(manager.single.resolve, SingleResolver)
    assert isinstance(manager.single, MagqlField)
    assert isinstance(manager.many.resolve, ManyResolver)
    assert isinstance(manager.many, MagqlField)

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
