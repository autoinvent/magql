from __future__ import annotations

import logging
import typing as t

import sqlalchemy as sa
from graphql import GraphQLResolveInfo
from sqlalchemy import orm as sa_orm
from sqlalchemy.sql import roles as sa_sql_roles

from ..validators import ValidationError


class ItemExistsValidator:
    """Validate that an id exists for a model in the database. Used by update and delete
    mutations.

    :param model: The model to query.
    :param key: The primary key name, shown in the error message.
    :param col: The primary key column.
    """

    def __init__(self, model: type[t.Any], key: str, col: sa.Column[t.Any]) -> None:
        self.model = model
        self.key = key
        self.col = col

    def __call__(
        self, info: GraphQLResolveInfo, value: t.Any | None, data: t.Any
    ) -> None:
        if value is None:
            return

        session: sa_orm.Session = info.context
        query = sa.select(sa.exists(sa.select(self.col).filter(self.col == value)))

        if not session.execute(query).scalar():
            raise ValidationError(
                f"{self.model.__name__} with {self.key} {value} does not exist."
            )


class ListExistsValidator:
    """Validate that a list of ids all exist for a model in the database. Used by update
    mutations for to-many relationships. Each id that does not exist will generate its
    own error message.

    :param model: The model to query.
    :param key: The primary key name, shown in the error message.
    :param col: The primary key column.
    """

    def __init__(self, model: type[t.Any], key: str, col: sa.Column[t.Any]) -> None:
        self.model = model
        self.key = key
        self.col = col

    def __call__(
        self, info: GraphQLResolveInfo, value: list[t.Any] | None, data: t.Any
    ) -> None:
        if value is None:
            return

        session: sa_orm.Session = info.context
        # Select ids that match the input list of ids.
        query = sa.select(self.col).filter(self.col.in_(value))
        found = set(session.execute(query).scalars())
        # Find any input values that did not appear in the query result.
        not_found = [v for v in value if v not in found]

        if not_found:
            name = self.model.__name__
            key = self.key
            raise ValidationError(
                [f"{name} with {key} {v} does not exist." for v in not_found]
            )


class UniqueValidator:
    """Validate that a value for a column is unique, or values for a group of columns
    are unique together. Used by create and update mutations.

    For create mutations, optional arguments that aren't provided will use the column's
    default. However, this can't work for columns with callable defaults.

    For update mutations, the row won't conflict with itself. Optional arguments
    that aren't provided will use the row's data.

    :param model: The model to query.
    :param columns: One or more columns that must be unique together.
    :param pk_name: The primary key name. Used during update mutations.
    :param pk_col: The primary key column. Used during update mutations.
    """

    def __init__(
        self,
        model: type[t.Any],
        columns: dict[str, sa.Column[t.Any]],
        pk_name: str,
        pk_col: sa.Column[t.Any],
    ) -> None:
        self.model = model
        self.columns = columns
        self.pk_name = pk_name
        self.pk_col = pk_col
        keys = list(columns.keys())

        # Pre-generate the error messages since they don't change based on the input.
        if len(keys) == 1:
            key = keys[0]
            message = f"{model.__name__} with this {key} already exists."
        else:
            key_str = f"{', '.join(keys[:-1])} and {keys[-1]}"
            message = f"{model.__name__} with this {key_str} already exists."

        # Show the error message for each argument that must be unique together.
        self.errors: dict[str, str] = {k: message for k in keys}

    def __call__(self, info: GraphQLResolveInfo, data: t.Any) -> None:
        session: sa_orm.Session = info.context
        filters = []

        if self.pk_name in data:
            # An update mutation will have the primary key in the input. Prevent the row
            # from matching itself, only check other rows.
            item = session.get(self.model, data[self.pk_name])
            filters.append(self.pk_col != data[self.pk_name])

            for key, col in self.columns.items():
                if key in data:
                    filters.append(col == data[key])
                else:
                    # Use the row's value if the argument wasn't provided.
                    filters.append(col == getattr(item, key))
        else:
            # A create mutation must have input for every column, or a missing column
            # must have a static default.
            for key, col in self.columns.items():
                if key in data:
                    value = data[key]
                else:
                    # Use the default if the argument wasn't provided.
                    value = col.default

                    if callable(value) or isinstance(value, sa_sql_roles.SQLRole):
                        logging.getLogger(__name__).info(
                            f"Can't check uniqueness on {col}. An input was not"
                            " provided and it has a dynamic default."
                        )
                        return

                filters.append(col == value)

        query = sa.select(self.model).filter(*filters)
        query = sa.select(sa.exists(query))

        if session.execute(query).scalar():
            raise ValidationError(self.errors)
