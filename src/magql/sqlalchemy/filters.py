from __future__ import annotations

import typing as t
from datetime import timezone

import sqlalchemy as sa
from dateutil.parser import isoparse

from ..core import nodes
from ..core import scalars
from .search import prepare_contains

filter_item = nodes.InputObject(
    "FilterItem",
    fields={
        "path": scalars.String.non_null,
        "op": scalars.String.non_null,
        "not": nodes.InputField(scalars.Boolean.non_null, default=False),
        "value": scalars.JSON.list.non_null,
    },
)


def op_eq(c: sa.Column, vs: list[t.Any]) -> t.Any:
    if len(vs) == 1:
        return c == vs[0]

    return c.in_(vs)


def op_like(c: sa.Column, vs: list[t.Any]) -> t.Any:
    return sa.or_(*(c.ilike(prepare_contains(v), escape="/") for v in vs))


_comp_ops = {
    "eq": op_eq,
    "lt": lambda c, vs: sa.or_(*(c < v for v in vs)),
    "le": lambda c, vs: sa.or_(*(c <= v for v in vs)),
    "ge": lambda c, vs: sa.or_(*(c >= v for v in vs)),
    "gt": lambda c, vs: sa.or_(*(c > v for v in vs)),
}


type_ops = {
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


def get_op(c: sa.Column, name: str) -> t.Callable[[sa.Column, list[t.Any]], t.Any]:
    for base in type(c.type).__mro__:
        if base in type_ops:
            try:
                return type_ops[base][name]
            except KeyError as e:
                raise KeyError(f"Unknown op '{name}' for type '{type(c.type)}'.") from e

    raise KeyError(f"No ops for type '{type(c.type)}'.")


def prepare_value(c: sa.Column, vs: list[t.Any]) -> list[t.Any]:
    if isinstance(c.type, sa.DateTime):
        out = []

        for v in vs:
            dt = isoparse(v)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            out.append(dt)

        return out

    return vs


def apply_filter_item(c: sa.Column, filter_item: dict[str, t.Any]) -> t.Any:
    op = get_op(c, filter_item["op"])
    vs = prepare_value(c, filter_item["value"])
    out = op(c, vs)

    if filter_item["not"]:
        return ~out

    return out
