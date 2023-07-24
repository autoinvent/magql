import pytest

import magql


def test_defined_in_graph() -> None:
    """Type definitions are collected from the graph, and are substituted for
    name references.
    """
    ms = magql.Schema()
    ms.query.fields["user"] = magql.Field(magql.Object("User"))
    ms.mutation.fields["userCreate"] = magql.Field("User")
    ms._find_nodes()
    assert "User" in ms.type_map
    assert ms.query.fields["user"].type is ms.mutation.fields["userCreate"].type


def test_defined_in_schema() -> None:
    """All references to a type in the graph may be strings, in which case the
    type must be added to the schema.
    """
    ms = magql.Schema()
    ms.query.fields["user"] = magql.Field("User")
    ms.mutation.fields["userCreate"] = magql.Field("User")
    ms.add_type(magql.Object("User"))
    gs = ms.to_graphql()
    assert "User" in gs.type_map


def test_defined_in_schema_init() -> None:
    """Types can be passed in when creating the schema."""
    ms = magql.Schema(types=[magql.Object("User"), magql.InputObject("UserInput")])
    ms.query.fields["user"] = magql.Field("User")
    ms.mutation.fields["userCreate"] = magql.Field(
        "User", args={"input": magql.Argument("UserInput")}
    )
    gs = ms.to_graphql()
    assert "User" in gs.type_map
    assert "UserInput" in gs.type_map


def test_undefined() -> None:
    """Converting to a GraphQL schema will raise an error if there are undefined
    types. Finding and applying types is incremental and will not raise an error.
    """
    ms = magql.Schema()
    ms.query.fields["user"] = magql.Field("User")
    ms.mutation.fields["userCreate"] = magql.Field(
        "User", args={"input": magql.Argument("UserInput")}
    )
    ms._find_nodes()  # doesn't raise
    assert ms.type_map["User"] is None

    with pytest.raises(KeyError, match="type names: 'User', 'UserInput'."):
        ms.to_graphql()

    ms.add_type(magql.Object("User"))

    with pytest.raises(KeyError, match="type names: 'UserInput'."):
        ms.to_graphql()


def test_circular_reference() -> None:
    """User has a field of type User. Applying the type should not cause a
    RecursionError.
    """
    ms = magql.Schema()
    ms.query.fields["user"] = magql.Field(
        magql.Object("User", fields={"friend": magql.Field("User")})
    )
    ms._find_nodes()
    user_type = ms.query.fields["user"].type
    assert isinstance(user_type, magql.Object)
    assert user_type is user_type.fields["friend"].type


def test_unused() -> None:
    """An unused type is not present in the GraphQL schema."""
    ms = magql.Schema()
    ms.query.fields["user"] = magql.Field("User")
    ms.add_type(magql.Object("User"))
    ms.add_type(magql.InputObject("UserInput"))
    gs = ms.to_graphql()
    assert "UserInput" not in gs.type_map
    assert "Mutation" not in gs.type_map
