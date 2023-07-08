import pytest

from magql import core


def test_defined_in_graph():
    """Type definitions are collected from the graph, and are
    substituted for name references.
    """
    ms = core.Schema()
    ms.query.fields["user"] = core.Field(core.Object("User"))
    ms.mutation.fields["userCreate"] = core.Field("User")
    ms._find_nodes()
    assert "User" in ms.type_map
    assert ms.query.fields["user"].type is ms.mutation.fields["userCreate"].type


def test_defined_in_schema():
    """All references to a type in the graph may be strings, in which
    case the type must be added to the schema.
    """
    ms = core.Schema()
    ms.query.fields["user"] = core.Field("User")
    ms.mutation.fields["userCreate"] = core.Field("User")
    ms.add_type(core.Object("User"))
    gs = ms.to_graphql()
    assert "User" in gs.type_map


def test_defined_in_schema_init():
    """Types can be passed in when creating the schema."""
    ms = core.Schema(types=[core.Object("User"), core.InputObject("UserInput")])
    ms.query.fields["user"] = core.Field("User")
    ms.mutation.fields["userCreate"] = core.Field(
        "User", args={"input": core.Argument("UserInput")}
    )
    gs = ms.to_graphql()
    assert "User" in gs.type_map
    assert "UserInput" in gs.type_map


def test_undefined():
    """Converting to a GraphQL schema will raise an error if there are
    undefined types. Finding and applying types is incremental and will
    not raise an error.
    """
    ms = core.Schema()
    ms.query.fields["user"] = core.Field("User")
    ms.mutation.fields["userCreate"] = core.Field(
        "User", args={"input": core.Argument("UserInput")}
    )
    ms._find_nodes()  # doesn't raise
    assert ms.type_map["User"] is None

    with pytest.raises(KeyError, match="type names: 'User', 'UserInput'."):
        ms.to_graphql()

    ms.add_type(core.Object("User"))

    with pytest.raises(KeyError, match="type names: 'UserInput'."):
        ms.to_graphql()


def test_circular_reference():
    """User has a field of type User. Applying the type should not cause
    a RecursionError.
    """
    ms = core.Schema()
    ms.query.fields["user"] = core.Field(
        core.Object("User", fields={"friend": core.Field("User")})
    )
    ms._find_nodes()
    assert (
        ms.query.fields["user"].type
        is ms.query.fields["user"].type.fields["friend"].type
    )


def test_unused():
    """An unused type is not present in the GraphQL schema."""
    ms = core.Schema()
    ms.query.fields["user"] = core.Field("User")
    ms.add_type(core.Object("User"))
    ms.add_type(core.InputObject("UserInput"))
    gs = ms.to_graphql()
    assert "UserInput" not in gs.type_map
    assert "Mutation" not in gs.type_map
