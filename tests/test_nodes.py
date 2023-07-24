from __future__ import annotations

import enum
import typing as t

import graphql
import pytest

import magql


def test_object() -> None:
    obj = magql.Object("User", fields={"id": magql.Field(magql.ID)})
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLObjectType)
    assert g.fields["id"].type is graphql.GraphQLID


def test_argument() -> None:
    obj = magql.Field(magql.String, args={"id": magql.Argument(magql.Int)})
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLField)
    assert g.args["id"].type is graphql.GraphQLInt


def test_interface() -> None:
    obj = magql.Object(
        "User",
        interfaces=[
            magql.Interface("Person", fields={"name": magql.Field(magql.String)})
        ],
        fields={"admin": magql.Field(magql.Boolean)},
    )
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLObjectType)
    assert "name" not in g.fields
    assert isinstance(g.fields["admin"], graphql.GraphQLField)
    assert isinstance(g.interfaces[0], graphql.GraphQLInterfaceType)
    assert isinstance(g.interfaces[0].fields["name"], graphql.GraphQLField)


def test_nested_interface() -> None:
    obj = magql.Object(
        "User",
        interfaces=[magql.Interface("Person", interfaces=[magql.Interface("Entity")])],
    )
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLObjectType)
    assert isinstance(g.interfaces[0], graphql.GraphQLInterfaceType)
    assert len(g.interfaces) == 1
    assert isinstance(g.interfaces[0].interfaces[0], graphql.GraphQLInterfaceType)


def test_union() -> None:
    class User:
        pass

    class Admin(User):
        pass

    obj = magql.Union(
        "Person", types={User: magql.Object("User"), Admin: magql.Object("Admin")}
    )
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLUnionType)
    assert len(g.types) == 2
    assert {t.name for t in g.types} == {"User", "Admin"}


def test_input() -> None:
    obj = magql.Argument(
        magql.InputObject(
            "UserCreateData", fields={"name": magql.InputField(magql.String)}
        )
    )
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLArgument)
    assert isinstance(g.type, graphql.GraphQLInputObjectType)
    assert isinstance(g.type.fields["name"], graphql.GraphQLInputField)
    assert g.type.fields["name"].type is graphql.GraphQLString


Color = enum.Enum("Color", ["red", "green", "blue"])


@pytest.mark.parametrize(
    ("values", "expect"),
    [
        pytest.param(["red", "green", "blue"], "red", id="list"),
        pytest.param({"red": 1, "green": 2, "blue": 3}, 1, id="dict"),
        pytest.param(Color, Color.red, id="enum"),
    ],
)
def test_enum(
    values: list[str] | dict[str, t.Any] | type[enum.Enum],
    expect: str | int | enum.Enum,
) -> None:
    obj = magql.Enum("colors", values)
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLEnumType)
    assert isinstance(g.values["red"], graphql.GraphQLEnumValue)
    assert g.values["red"].value == expect


def test_wrapping() -> None:
    obj = magql.List(magql.NonNull(magql.String))
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLList)
    assert isinstance(g.of_type, graphql.GraphQLNonNull)
    assert graphql.get_named_type(g) is graphql.GraphQLString


@pytest.mark.parametrize(
    ("obj", "expect"),
    [
        pytest.param(magql.String, graphql.GraphQLString, id="String"),
        pytest.param(magql.Int, graphql.GraphQLInt, id="Int"),
        pytest.param(magql.Float, graphql.GraphQLFloat, id="Float"),
        pytest.param(magql.Boolean, graphql.GraphQLBoolean, id="Boolean"),
        pytest.param(magql.ID, graphql.GraphQLID, id="ID"),
    ],
)
def test_standard_scalar(obj: magql.Scalar, expect: graphql.GraphQLScalarType) -> None:
    g = obj._to_graphql()
    assert g is expect


@pytest.mark.parametrize(
    "obj",
    [
        pytest.param(magql.JSON, id="JSON"),
        pytest.param(magql.Upload, id="Upload"),
    ],
)
def test_custom_scalar(obj: magql.Scalar) -> None:
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLScalarType)
    assert g.name == obj.name
    assert obj._to_graphql() is g


def test_wrapping_properties() -> None:
    """Types have list and non_null properties that return wrapped
    types.
    """
    obj = magql.String
    assert isinstance(obj.list, magql.List)
    assert isinstance(obj.non_null, magql.NonNull)
    assert obj.non_null.type is obj
    go = obj.non_null.list.non_null._to_graphql()
    assert graphql.get_named_type(go).name == "String"


def test_to_graphql_cached() -> None:
    """The same GraphQL node is produced if a magql node is converted
    multiple times.
    """
    obj = magql.Object("User", fields={"id": magql.Field(magql.ID)})
    g1 = obj._to_graphql()
    g2 = obj._to_graphql()
    assert g1 is g2
    assert g1.fields["id"] is g2.fields["id"]
