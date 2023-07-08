import enum

import graphql
import pytest

from magql import core


def test_object():
    obj = core.Object("User", fields={"id": core.Field(core.ID)})
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLObjectType)
    assert g.fields["id"].type is graphql.GraphQLID


def test_argument():
    obj = core.Field(core.String, args={"id": core.Argument(core.Int)})
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLField)
    assert g.args["id"].type is graphql.GraphQLInt


def test_interface():
    obj = core.Object(
        "User",
        interfaces=[core.Interface("Person", fields={"name": core.Field(core.String)})],
        fields={"admin": core.Field(core.Boolean)},
    )
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLObjectType)
    assert "name" not in g.fields
    assert isinstance(g.fields["admin"], graphql.GraphQLField)
    assert isinstance(g.interfaces[0], graphql.GraphQLInterfaceType)
    assert isinstance(g.interfaces[0].fields["name"], graphql.GraphQLField)


def test_nested_interface():
    obj = core.Object(
        "User",
        interfaces=[core.Interface("Person", interfaces=[core.Interface("Entity")])],
    )
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLObjectType)
    assert isinstance(g.interfaces[0], graphql.GraphQLInterfaceType)
    assert len(g.interfaces) == 1
    assert isinstance(g.interfaces[0].interfaces[0], graphql.GraphQLInterfaceType)


def test_union():
    obj = core.Union("Person", types=[core.Object("User"), core.Object("Admin")])
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLUnionType)
    assert len(g.types) == 2
    assert {t.name for t in g.types} == {"User", "Admin"}


def test_input():
    obj = core.Argument(
        core.InputObject(
            "UserCreateData", fields={"name": core.InputField(core.String)}
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
def test_enum(values, expect):
    obj = core.Enum("colors", values)
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLEnumType)
    assert isinstance(g.values["red"], graphql.GraphQLEnumValue)
    assert g.values["red"].value == expect


def test_wrapping():
    obj = core.List(core.NonNull(core.String))
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLList)
    assert isinstance(g.of_type, graphql.GraphQLNonNull)
    assert graphql.get_named_type(g) is graphql.GraphQLString


@pytest.mark.parametrize(
    ("obj", "expect"),
    [
        pytest.param(core.String, graphql.GraphQLString, id="String"),
        pytest.param(core.Int, graphql.GraphQLInt, id="Int"),
        pytest.param(core.Float, graphql.GraphQLFloat, id="Float"),
        pytest.param(core.Boolean, graphql.GraphQLBoolean, id="Boolean"),
        pytest.param(core.ID, graphql.GraphQLID, id="ID"),
    ],
)
def test_standard_scalar(obj, expect):
    g = obj._to_graphql()
    assert g is expect


@pytest.mark.parametrize(
    "obj",
    [
        pytest.param(core.JSON, id="JSON"),
        pytest.param(core.Upload, id="Upload"),
    ],
)
def test_custom_scalar(obj):
    g = obj._to_graphql()
    assert isinstance(g, graphql.GraphQLScalarType)
    assert g.name == obj.name
    assert obj._to_graphql() is g


def test_wrapping_properties():
    """Types have list and non_null properties that return wrapped
    types.
    """
    obj = core.String
    assert isinstance(obj.list, core.List)
    assert isinstance(obj.non_null, core.NonNull)
    assert obj.non_null.type is obj
    go = obj.non_null.list.non_null._to_graphql()
    assert graphql.get_named_type(go).name == "String"


def test_to_graphql_cached():
    """The same GraphQL node is produced if a magql node is converted
    multiple times.
    """
    obj = core.Object("User", fields={"id": core.Field(core.ID)})
    g1 = obj._to_graphql()
    g2 = obj._to_graphql()
    assert g1 is g2
    assert g1.fields["id"] is g2.fields["id"]
