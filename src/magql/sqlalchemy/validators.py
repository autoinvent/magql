from __future__ import annotations

import logging
import typing as t

import sqlalchemy as sa
from graphql import GraphQLResolveInfo
from sqlalchemy import orm as sa_orm
from sqlalchemy.sql import roles as sa_sql_roles

from ..validators import ValidationError


class ItemExistsValidator:
    def __init__(self, model: type[t.Any], key: str, col: sa.Column) -> None:
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
    def __init__(self, model: type[t.Any], key: str, col: sa.Column) -> None:
        self.model = model
        self.key = key
        self.col = col

    def __call__(
        self, info: GraphQLResolveInfo, value: list[t.Any] | None, data: t.Any
    ) -> None:
        if value is None:
            return

        session: sa.orm.Session = info.context
        query = sa.select(self.col).filter(self.col.in_(value))
        found = set(session.execute(query).scalars())
        not_found = [v for v in value if v not in found]

        if not_found:
            name = self.model.__name__
            key = self.key
            raise ValidationError(
                [f"{name} with {key} {v} does not exist." for v in not_found]
            )


class UniqueValidator:
    def __init__(
        self,
        model: type[t.Any],
        columns: dict[str, sa.Column],
        pk_name: str,
        pk_col: sa.Column,
    ) -> None:
        self.model = model
        self.columns = columns
        self.pk_name = pk_name
        self.pk_col = pk_col
        keys = list(columns.keys())

        if len(keys) == 1:
            key = keys[0]
            message = f"{model.__name__} with this {key} already exists."
        else:
            key_str = f"{', '.join(keys[:-1])} and {keys[-1]}"
            message = f"{model.__name__} with this {key_str} already exists."

        self.errors = {k: message for k in keys}

    def __call__(self, info: GraphQLResolveInfo, data: t.Any) -> None:
        session: sa_orm.Session = info.context
        filters = []

        if self.pk_name in data:
            # An update mutation will have the primary key in the input. Don't consider
            # the edited item's existing values, only check other items.
            session: sa_orm.Session = info.context
            item = session.get(self.model, data[self.pk_name])
            filters.append(self.pk_col != data[self.pk_name])

            for key, col in self.columns.items():
                if key in data:
                    filters.append(col == data[key])
                else:
                    filters.append(col == getattr(item, key))
        else:
            # A create mutation must have input for every column, or a missing column
            # must have a static default.
            for key, col in self.columns.items():
                if key in data:
                    value = data[key]
                else:
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
