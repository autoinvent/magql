from __future__ import annotations

import dataclasses
import typing as t
from types import SimpleNamespace

import graphql

import magql


@dataclasses.dataclass()
class User:
    id: int
    name: str


def test_default_resolve() -> None:
    """The default resolver looks at attributes."""
    root = SimpleNamespace()
    root.user = User(1, "abc")
    s = magql.Schema(types=[magql.Object("User", fields={"name": "String"})])
    s.query.fields["user"] = magql.Field("User")
    result = s.execute("{ user { name } }", root)
    assert result.data == {"user": {"name": "abc"}}


def test_arg() -> None:
    """Field arguments are passed as keyword arguments to the field resolver."""
    users = {1: User(1, "abc")}
    s = magql.Schema(types=[magql.Object("User", fields={"name": "String"})])

    @s.query.field("user", "User", args={"id": "Int"})
    def resolve_user(
        parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> User | None:
        return users.get(kwargs["id"])

    result = s.execute("{ user(id: 1) { name } }")
    assert result.errors is None
    assert result.data == {"user": {"name": "abc"}}


def test_resolver_decorator() -> None:
    """The decorator will add a resolver to a field after definition."""
    users = {1: User(1, "abc")}
    s = magql.Schema(types=[magql.Object("User", fields={"name": "String"})])
    s.query.fields["user"] = magql.Field("User", args={"id": "Int"})

    @s.query.fields["user"].resolver
    def resolve_user(
        parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> User | None:
        return users.get(kwargs["id"])

    result = s.execute("{ user(id: 1) { name } }")
    assert result.errors is None
    assert result.data == {"user": {"name": "abc"}}
