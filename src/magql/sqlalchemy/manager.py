from __future__ import annotations

import re
import typing as t

import sqlalchemy as sa
import sqlalchemy.orm as sa_orm

from ..core import nodes
from ..core import scalars
from ..core.schema import Schema
from ..core.search import Search
from ..core.search import SearchProvider
from .check_delete import CheckDelete
from .filters import filter_item
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


class ModelGroup:
    def __init__(self, managers: list[ModelManager] | None = None) -> None:
        self.managers: dict[str, ModelManager] = {}
        self.search = Search()
        self.check_delete = CheckDelete(self.managers)

        if managers is not None:
            for manager in managers:
                self.add_manager(manager)

    def add_manager(self, manager: ModelManager) -> None:
        self.managers[manager.model.__name__] = manager

    def register(self, schema: Schema) -> None:
        for manager in self.managers.values():
            manager.register(schema)
            manager.register_search(self.search)

        self.search.register(schema)
        self.check_delete.register(schema)


class ModelManager:
    def __init__(self, model: type[t.Any], search: bool = False) -> None:
        self.model = model
        model_name = model.__name__
        mapper = sa.inspect(model)
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
                col = next(iter(rel.local_columns))

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

        for constraint in mapper.local_table.constraints:
            if not isinstance(constraint, sa.UniqueConstraint):
                continue

            unique_validators.append(
                UniqueValidator(model, constraint.columns, pk_name, pk_col)
            )

        self.create_field = nodes.Field(
            self.object.non_null,
            args=create_args,
            resolve=CreateResolver(model),
            validators=[*unique_validators],
        )
        self.update_field = nodes.Field(
            self.object.non_null,
            args=update_args,
            resolve=UpdateResolver(model),
            validators=[*unique_validators],
        )
        self.delete_field = nodes.Field(
            scalars.Boolean.non_null,
            args={pk_name: nodes.Argument(pk_type.non_null, validators=[item_exists])},
            resolve=DeleteResolver(model),
        )

        if search:
            self.search_provider: SearchProvider | None = ColumnSearchProvider(model)
        else:
            self.search_provider = None

    def register(self, schema: Schema) -> None:
        name = camel_to_snake_case(self.model.__name__)
        schema.query.fields[f"{name}_item"] = self.item_field
        schema.query.fields[f"{name}_list"] = self.list_field
        schema.mutation.fields[f"{name}_create"] = self.create_field
        schema.mutation.fields[f"{name}_update"] = self.update_field
        schema.mutation.fields[f"{name}_delete"] = self.delete_field

    def register_search(self, search: Search) -> None:
        if self.search_provider is not None:
            search.provider(self.search_provider)


def _convert_column_type(
    model_name: str, key: str, column: sa.Column, nested_type: sa.Column | None = None
) -> nodes.Type:
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
        for _ in range(ct.dimensions - 1):
            out = out.non_null.list

        return out

    return scalars.String


def camel_to_snake_case(name: str) -> str:
    """Convert a ``CamelCase`` name to ``snake_case``."""
    name = re.sub(r"((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))", r"_\1", name)
    return name.lower().lstrip("_")