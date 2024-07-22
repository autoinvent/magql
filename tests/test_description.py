from __future__ import annotations

import typing as t

from graphql import GraphQLResolveInfo

import magql


def test_clean_description() -> None:
    """Indentation and trailing space is removed from multiline string."""
    field = magql.Field(
        "String",
        description="""A description

        with multiple
        lines.
        """,
    )
    assert field.description == "A description\n\nwith multiple\nlines."


def test_clean_description_to_graphql() -> None:
    """Description is cleaned when converted to GraphQL."""
    field = magql.Field(magql.String)
    field.description = """A description

    with multiple
    lines.
    """
    desc = field._to_graphql().description
    assert desc == "A description\n\nwith multiple\nlines."


def test_field_docstring() -> None:
    """Field decorator uses docstring as description."""
    obj = magql.Object("User")

    @obj.field("name", "String")
    def resolve_user_name(
        parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        """first"""
        pass

    assert obj.fields["name"].description == "first"


def test_field_no_docstring() -> None:
    """Function without docstring is allowed."""
    obj = magql.Object("User")

    @obj.field("name", "String")
    def resolve_user_name(
        parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        pass

    assert obj.fields["name"].description is None


def test_field_no_override() -> None:
    obj = magql.Object("User")

    @obj.field("name", "String", description="first")
    def resolve_user_name(
        parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        """second"""
        pass

    assert obj.fields["name"].description == "first"


def test_resolver_docstring() -> None:
    """Resolver decorator uses docstring as description."""
    field = magql.Field("String")

    @field.resolver
    def resolve(parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any) -> t.Any:
        """first"""
        pass

    assert field.description == "first"


def test_resolver_no_docstring() -> None:
    """Function without docstring is allowed."""
    field = magql.Field("String")

    @field.resolver
    def resolve(parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any) -> t.Any:
        pass

    assert field.description is None


def test_resolver_no_override() -> None:
    """Docstring is not used if description is set."""
    field = magql.Field("String", description="first")

    @field.resolver
    def resolve(parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any) -> t.Any:
        """second"""
        pass

    assert field.description == "first"
