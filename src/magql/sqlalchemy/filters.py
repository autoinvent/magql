from __future__ import annotations

import typing as t
from datetime import timezone

import sqlalchemy as sa
from dateutil.parser import isoparse
from sqlalchemy.sql.type_api import TypeEngine

from .search import prepare_contains


def op_eq(c: sa.Column[t.Any], vs: list[t.Any]) -> t.Any:
    if len(vs) == 1:
        return c == vs[0]

    return c.in_(vs)


def op_like(c: sa.Column[t.Any], vs: list[t.Any]) -> t.Any:
    return sa.or_(*(c.ilike(prepare_contains(v), escape="/") for v in vs))


_comp_ops = {
    "eq": op_eq,
    "lt": lambda c, vs: sa.or_(*(c < v for v in vs)),
    "le": lambda c, vs: sa.or_(*(c <= v for v in vs)),
    "ge": lambda c, vs: sa.or_(*(c >= v for v in vs)),
    "gt": lambda c, vs: sa.or_(*(c > v for v in vs)),
}


type_ops: dict[
    type[TypeEngine[t.Any]],
    dict[str, t.Callable[[sa.Column[t.Any], list[t.Any]], t.Any]],
] = {
    sa.String: {
        "eq": op_eq,
        "like": op_like,
    },
    sa.Integer: {
        **_comp_ops,
    },
    sa.Float: {
        **_comp_ops,
    },
    sa.Boolean: {
        "eq": lambda c, vs: c if vs[0] else ~c,
    },
    sa.DateTime: {
        **_comp_ops,
    },
    sa.Enum: {
        "eq": op_eq,
    },
}
"""Maps SQLAlchemy column types to available filter operations. The operations
map names to callables that generate a SQL expression.
"""


def get_op(
    c: sa.Column[t.Any], name: str
) -> t.Callable[[sa.Column[t.Any], list[t.Any]], t.Any]:
    """Get the operation callable for a given column and operation name. A
    :exc:`KeyError` is raised if the operation is not defined for the type.

    :param c: The SQLAlchemy column.
    :param name: The name of the operation.
    """
    for base in type(c.type).__mro__:
        if base in type_ops:
            try:
                return type_ops[base][name]
            except KeyError as e:
                raise KeyError(f"Unknown op '{name}' for type '{type(c.type)}'.") from e

    raise KeyError(f"No ops for type '{type(c.type)}'.")


def prepare_value(c: sa.Column[t.Any], vs: list[t.Any]) -> list[t.Any]:
    """Convert data in the filter value from JSON to Python based on the type of the
    column.

    -   For ``DateTime`` columns, converts values using ISO 8601.
    -   Other data is passed through without change.

    :param c: The SQLAlchemy column.
    :param vs: The list of JSON values from the filter item.
    """
    if isinstance(c.type, sa.DateTime):
        out = []

        for v in vs:
            dt = isoparse(v)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            out.append(dt)

        return out

    return vs


def apply_filter_item(c: sa.Column[t.Any], filter_item: dict[str, t.Any]) -> t.Any:
    """Apply a single filter item to the given column, returning a SQL expression.
    Called by :meth:`.ListResolver.apply_filter`.

    :param c: The SQLAlchemy column.
    :param filter_item: One filter item to apply.
    """
    op = get_op(c, filter_item["op"])
    vs = prepare_value(c, filter_item["value"])
    out = op(c, vs)

    if filter_item["not"]:
        return ~out

    return out
