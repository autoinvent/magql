from __future__ import annotations

import typing as t

import sqlalchemy as sa
import sqlalchemy.orm as sa_orm

from ..core.search import SearchResult


class ColumnSearchProvider:
    def __init__(self, model: type[t.Any]) -> None:
        self.model = model
        self.columns = find_string_columns(model)

    def __call__(self, context: t.Any, value: str) -> list[SearchResult]:
        session: sa_orm.Session = context
        value = prepare_contains(value)
        query = sa.select(self.model).filter(
            sa.or_(*(c.ilike(value, escape="/") for c in self.columns))
        )
        model_name = self.model.__name__
        return [
            SearchResult(
                type=model_name, id=sa.inspect(item).identity[0], value=str(item)
            )
            for item in session.execute(query).scalars()
        ]


def find_string_columns(model: type[t.Any]) -> list[sa.Column]:
    columns = sa.inspect(model).columns
    return [c for c in columns if isinstance(c.type, sa.String)]


def prepare_contains(value: str) -> str:
    """Prepare a search string for SQL ``LIKE`` from user input.

    :param value: Search value.
    :param escape: Use this character to escape ``%`` and ``_`` wildcard characters. If
        ``None``, the user can use wildcard characters.
    """
    value = value.replace("/", "//").replace("%", "/%").replace("_", "/_")
    return f"%{value}%"
