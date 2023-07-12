from __future__ import annotations

import re
import typing as t

import sqlalchemy as sa
import sqlalchemy.orm as sa_orm
from sqlalchemy.sql.type_api import TypeEngine

from ..core import nodes
from ..core import scalars
from ..core.filters import filter_item
from ..core.schema import Schema
from ..core.search import Search
from ..core.search import SearchProvider
from .check_delete import CheckDelete
from .pagination import PerPageValidator
from .pagination import validate_page
from .resolvers import CreateResolver
from .resolvers import DeleteResolver
from .resolvers import ItemResolver
from .resolvers import ListResolver
from .resolvers import UpdateResolver
from .search import ColumnSearchProvider
from .validators import ItemExistsValidator
from .validators import ListExistsValidator
from .validators import UniqueValidator

if t.TYPE_CHECKING:
    import typing_extensions as te


class ModelGroup:
    """Collects multiple model managers and manages higher-level APIs such as search and
    check delete.

    Typically there will be one group for all the models. If more than one group is used
    for some reason, the field names for its :attr:`search` and :attr:`check_delete`
    instances should be changed.

    :param managers: The model managers that are part of this group.
    """

    def __init__(self, managers: list[ModelManager] | None = None) -> None:
        self.managers: dict[str, ModelManager] = {}
        """Maps SQLAlchemy model names to their :class:`ModelManager` instance. Use
        :meth:`add_manager` to add to this.
        """

        self.search: Search = Search()
        """The :class:`.Search` instance model providers will be registered on."""

        self.check_delete: CheckDelete = CheckDelete(self.managers)
        """The :class:`.CheckDelete` instance models will be registered on."""

        if managers is not None:
            for manager in managers:
                self.add_manager(manager)

    @classmethod
    def from_declarative_base(
        cls, base: sa_orm.DeclarativeMeta, search: set[type[t.Any] | str] | None = None
    ) -> te.Self:
        """Create a group of model managers for all models in the given SQLAlchemy
        declarative base class.

        :param base: The SQLAlchemy declarative base class.
        :param search: The set of models, as classes or names, to show in global search.
        """
        if search is None:
            search = set()

        managers = []

        for mapper in base.registry.mappers:
            model = mapper.class_
            model_search = model in search or model.__name__ in search
            managers.append(ModelManager(model, search=model_search))

        return cls(managers)

    def add_manager(self, manager: ModelManager) -> None:
        """Add another model manager after the group was created.

        :param manager: The model manager to add.
        """
        self.managers[manager.model.__name__] = manager

    def register(self, schema: Schema) -> None:
        """Register this group's managers and APIs on the given :class:`.Schema`
        instance.

        :param schema: The schema instance to register on.
        """
        for manager in self.managers.values():
            manager.register(schema)
            manager.register_search(self.search)

        self.search.register(schema)
        self.check_delete.register(schema)


class ModelManager:
    """The API for a single SQLAlchemy model class. Generates Magql types, fields,
    resolvers, etc. These are exposed as attributes on this manager, and can be further
    customized after generation.

    :param model: The SQLAlchemy model class.
    :param search: Whether this model will provide results in global search.
    """

    model: type[t.Any]
    """The SQLAlchemy model class."""

    object: nodes.Object
    """The object type and fields representing the model and its columns. The type name
    is the model name.

    .. code-block:: graphql

        type Model {
            id: Int!
            name: String!
        }
    """

    item_field: nodes.Field
    """Query that selects a row by id from the database. The field name is the snake
    case model name with ``_item`` appended. Uses :class:`.ItemResolver`.

    .. code-block:: graphql

        type Query {
            model_item(id: Int!): Model
        }
    """

    list_result: nodes.Object
    """The object type representing the result of the list query. The type name is the
    model name with ``ListResult`` appended. :class:`.ListResult` is the Python type
    corresponding to this Magql type.

    .. code-block: graphql

        type ModelListResult {
            items: [Model!]!
            total: Int!
        }
    """

    sort: nodes.Enum
    """The enum type representing all the sorts that can be applied to the list query.
    The type name is the model name with ``Sort`` appended. For each column that
    is not a foreign key, an ascending and descending value are generated. For example,
    ``name_asc`` and ``name_desc``. In Python, the values are converted to
    ``(name: str, desc: bool)`` tuples.

    .. code-block:: graphql

        enum ModelSort {
            id_asc
            id_desc
            name_asc
            name_desc
        }
    """

    list_field: nodes.Field
    """Query that selects multiple rows from the database. The field name is the snake
    case model name with ``_list`` appended. Uses :class:`.ListResolver`.

    .. code-block:: graphql

        type Query {
            model_list(
                filter: [[FilterItem!]!],
                sort: [ModelSort!],
                page: Int,
                per_page: Int
            ): ModelListResult!
        }
    """

    create_field: nodes.Field
    """Mutation that inserts a row into the database. The field name is the snake case
    model name with ``_create`` appended. An argument is generated for each column in
    the model except the primary key. An argument is required if its column is not
    nullable and doesn't have a default. Uses :class:`.CreateResolver`.

    .. code-block:: graphql

        type Mutation {
            model_create(name: String!): Model!
        }
    """

    update_field: nodes.Field
    """Mutation that updates a row in the database. The field name is the snake case
    model name with ``_update`` appended. An argument is generated for each column in
    the model. The primary key argument is required, all others are not. Columns are not
    updated if their argument is not given. Uses :class:`.UpdateResolver`.

    .. code-block:: graphql

        type Mutation {
            model_update(id: Int!, name: String): Model!
        }
    """

    delete_field: nodes.Field
    """Mutation that deletes a row from the database. The field name is the snake case
    model name with ``_delete`` appended. Uses :class:`.DeleteResolver`.

    .. code-block:: graphql

        type Mutation {
            model_delete(id: Int!): Boolean!
        }
    """

    search_provider: SearchProvider | None = None
    """A global search provider function. Enabling search will create a
    :class:`.ColumnSearchProvider` that checks if any of the model's string columns
    contains the search term. This can be set to a custom function to change search
    behavior.
    """

    def __init__(self, model: type[t.Any], search: bool = False) -> None:
        self.model = model
        model_name = model.__name__
        mapper = t.cast(sa_orm.Mapper[t.Any], sa.inspect(model))
        # Find the primary key column and its Magql type.
        pk_name, pk_col = next(x for x in mapper.columns.items() if x[1].primary_key)
        pk_type = _convert_column_type(model_name, pk_name, pk_col)
        self.object = object = nodes.Object(model_name)
        item_exists = ItemExistsValidator(model, pk_name, pk_col)
        update_args: dict[str, nodes.Argument] = {
            pk_name: nodes.Argument(pk_type.non_null, validators=[item_exists])
        }
        create_args: dict[str, nodes.Argument] = {}
        sort_items: dict[str, tuple[str, bool]] = {}

        for key, col in mapper.columns.items():
            # Foreign key columns are assumed to have relationships, handled later.
            if col.foreign_keys:
                continue

            col_type = _convert_column_type(model_name, key, col)

            if col.nullable:
                object.fields[key] = nodes.Field(col_type)
            else:
                object.fields[key] = nodes.Field(col_type.non_null)

            sort_items[f"{key}_asc"] = (key, False)
            sort_items[f"{key}_desc"] = (key, True)

            # The primary key column is assumed to be generated, only used as an input
            # when querying an item by id.
            if col.primary_key:
                continue

            update_args[key] = nodes.Argument(col_type)

            # When creating an object, a field is required if it's not nullable and
            # doesn't have a default value.
            if col.nullable or col.default:
                create_args[key] = nodes.Argument(col_type)
            else:
                create_args[key] = nodes.Argument(col_type.non_null)

        for key, rel in mapper.relationships.items():
            target_model = rel.entity.class_
            target_name = target_model.__name__
            # Assume a single primary key column for the input type. Can't use a local
            # foreign key because that won't exist for to-many.
            target_pk_name, target_pk_col = next(
                x for x in rel.mapper.columns.items() if x[1].primary_key
            )
            target_pk_type = _convert_column_type(
                target_name, target_pk_name, target_pk_col
            )

            if rel.direction is sa_orm.MANYTOONE:
                # To-one is like a column but with an object type instead of a scalar.
                # Assume a single foreign key column.
                col = next(iter(rel.local_columns))  # type: ignore[arg-type]

                if col.nullable:
                    object.fields[key] = nodes.Field(target_name)
                else:
                    object.fields[key] = nodes.Field(nodes.NonNull(target_name))

                rel_item_exists = ItemExistsValidator(
                    target_model, target_pk_name, target_pk_col
                )
                update_args[key] = nodes.Argument(
                    target_pk_type, validators=[rel_item_exists]
                )

                if col.nullable or col.default:
                    create_args[key] = nodes.Argument(
                        target_pk_type, validators=[rel_item_exists]
                    )
                else:
                    create_args[key] = nodes.Argument(
                        target_pk_type.non_null, validators=[rel_item_exists]
                    )
            else:
                # To-many is a non-null list of non-null objects.
                field_type = nodes.NonNull(target_name).list.non_null
                object.fields[key] = nodes.Field(field_type)
                # The input list can be empty or null, but the ids are non-null.
                rel_list_exists = ListExistsValidator(
                    target_model, target_pk_name, target_pk_col
                )
                update_args[key] = nodes.Argument(
                    target_pk_type.non_null.list, validators=[rel_list_exists]
                )
                create_args[key] = nodes.Argument(
                    target_pk_type.non_null.list, validators=[rel_list_exists]
                )

        self.item_field = nodes.Field(
            object,
            args={"id": nodes.Argument(pk_type, validators=[item_exists])},
            resolve=ItemResolver(model),
        )
        self.list_result = nodes.Object(
            f"{model_name}ListResult",
            fields={
                "items": nodes.Field(object.non_null.list.non_null),
                "total": nodes.Field(scalars.Int.non_null),
            },
        )
        self.sort = nodes.Enum(f"{model_name}Sort", sort_items)
        self.list_field = nodes.Field(
            self.list_result.non_null,
            args={
                "filter": nodes.Argument(filter_item.non_null.list.non_null.list),
                "sort": nodes.Argument(self.sort.non_null.list),
                "page": nodes.Argument(scalars.Int, validators=[validate_page]),
                "per_page": nodes.Argument(
                    scalars.Int, validators=[PerPageValidator()]
                ),
            },
            resolve=ListResolver(model),
        )
        unique_validators = []
        local_table = t.cast(sa.Table, mapper.local_table)

        for constraint in local_table.constraints:
            if not isinstance(constraint, sa.UniqueConstraint):
                continue

            unique_validators.append(
                UniqueValidator(
                    model, constraint.columns, pk_name, pk_col  # type: ignore[arg-type]
                )
            )

        self.create_field = nodes.Field(
            self.object.non_null,
            args=create_args,  # type: ignore[arg-type]
            resolve=CreateResolver(model),
            validators=[*unique_validators],
        )
        self.update_field = nodes.Field(
            self.object.non_null,
            args=update_args,  # type: ignore[arg-type]
            resolve=UpdateResolver(model),
            validators=[*unique_validators],
        )
        self.delete_field = nodes.Field(
            scalars.Boolean.non_null,
            args={pk_name: nodes.Argument(pk_type.non_null, validators=[item_exists])},
            resolve=DeleteResolver(model),
        )

        if search:
            self.search_provider = ColumnSearchProvider(model)

    def register(self, schema: Schema) -> None:
        """Register this manager's query and mutation fields on the given
        :class:`.Schema` instance.

        :param schema: The schema instance to register on.
        """
        name = camel_to_snake_case(self.model.__name__)
        schema.query.fields[f"{name}_item"] = self.item_field
        schema.query.fields[f"{name}_list"] = self.list_field
        schema.mutation.fields[f"{name}_create"] = self.create_field
        schema.mutation.fields[f"{name}_update"] = self.update_field
        schema.mutation.fields[f"{name}_delete"] = self.delete_field

    def register_search(self, search: Search) -> None:
        """If a search provider is enabled for this manager, register it on the given
        :class:`.Search` instance.

        Typically the search instance is managed by the :class:`ModelGroup`, which will
        register it on a schema.

        :param search: The search instance to register on.
        """
        if self.search_provider is not None:
            search.provider(self.search_provider)


def _convert_column_type(
    model_name: str,
    key: str,
    column: sa.Column[t.Any],
    nested_type: TypeEngine[t.Any] | None = None,
) -> nodes.Type:
    """Convert a SQLAlchemy column type to a Magql scalar type.

    :param model_name: The model's name, used when generating an :class:`.Enum`.
    :param key: The column's attribute name, used when generating an :class:`Enum`.
    :param column: The SQLAlchemy column instance.
    :param nested_type: The inner type of a SQLAlchemy ``ARRAY``, used when recursively
        generating a :class:`.List`.
    """

    if nested_type is None:
        ct = column.type
    else:
        ct = nested_type

    # sa.Enum inherits sa.String, must be checked first.
    if isinstance(ct, sa.Enum):
        name = f"{model_name}{key.title()}"

        if ct.enum_class is not None:
            return nodes.Enum(name, {k: ct.enum_class[k] for k in ct.enums})

        return nodes.Enum(name, ct.enums)

    if isinstance(ct, sa.String):
        return scalars.String

    if isinstance(ct, sa.Integer):
        return scalars.Int

    if isinstance(ct, sa.Float):
        return scalars.Float

    if isinstance(ct, sa.Boolean):
        return scalars.Boolean

    if isinstance(ct, sa.DateTime):
        return scalars.DateTime

    if isinstance(ct, sa.JSON):
        return scalars.JSON

    if isinstance(ct, sa.ARRAY):
        # Convert the item type. Array items are non-null.
        out = _convert_column_type(model_name, key, column, ct.item_type).non_null.list

        # Dimensions > 1 add extra non-null list wrapping.
        for _ in range((ct.dimensions or 1) - 1):
            out = out.non_null.list

        return out

    return scalars.String


def camel_to_snake_case(name: str) -> str:
    """Convert a ``CamelCase`` name to ``snake_case``."""
    name = re.sub(r"((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))", r"_\1", name)
    return name.lower().lstrip("_")
