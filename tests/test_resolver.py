import dataclasses
from types import SimpleNamespace

import magql


@dataclasses.dataclass()
class User:
    id: int
    name: str


def test_default_resolve():
    """The default resolver looks at attributes."""
    root = SimpleNamespace()
    root.user = User(1, "abc")
    s = magql.Schema()
    s.query.fields["user"] = magql.Field(
        magql.Object("User", fields={"name": magql.Field("String")})
    )
    result = s.execute("{ user { name } }", root)
    assert result.data == {"user": {"name": "abc"}}


def test_arg():
    """Field arguments are passed as keyword arguments to the field
    resolver.
    """
    users = {1: User(1, "abc")}
    s = magql.Schema()

    @s.query.field(
        "user",
        magql.Object("User", fields={"name": magql.Field("String")}),
        args={"id": magql.Argument(magql.Int)},
    )
    def resolve_user(parent, info, id):
        return users.get(id)

    result = s.execute("{ user(id: 1) { name } }")
    assert not result.errors
    assert result.data == {"user": {"name": "abc"}}


def test_resolver_decorator():
    """The decorator will add a resolver to a field after definition."""
    users = {1: User(1, "abc")}
    s = magql.Schema()
    user_field = magql.Field(
        magql.Object("User", fields={"name": magql.Field("String")}),
        args={"id": magql.Argument(magql.Int)},
    )
    s.query.fields["user"] = user_field

    @user_field.resolver
    def resolve_user(parent, info, id):
        return users.get(id)

    result = s.execute("{ user(id: 1) { name } }")
    assert not result.errors
    assert result.data == {"user": {"name": "abc"}}
