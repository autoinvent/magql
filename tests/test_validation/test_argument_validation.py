from __future__ import annotations

import typing as t
from dataclasses import dataclass

import graphql

import magql.validators


@dataclass
class User:
    username: str
    hobbies: list[str] | None


def validate_lowercase(
    info: graphql.GraphQLResolveInfo, value: str, data: dict[str, t.Any]
) -> None:
    if not value.islower():
        raise magql.ValidationError("Must be lowercase.")


schema = magql.Schema(
    types=[magql.Object("User", fields={"username": "String!", "hobbies": "[String!]"})]
)


@schema.query.field(
    "user",
    "User!",
    args={
        "username": magql.Argument(
            "String!",
            validators=[validate_lowercase, magql.validators.Length(min=2, max=10)],
        ),
        "hobbies": magql.Argument(
            "[String!]",
            validators=[
                magql.validators.Length(min=2),
                [validate_lowercase],  # type: ignore[list-item]
            ],
        ),
    },
)
def resolve_user_create(
    parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
) -> User:
    return User(username=kwargs["username"], hobbies=kwargs.get("hobbies"))


valid_op = """\
query($u: String!, $h: [String!]!) {
  user(username: $u, hobbies: $h) {
    username
    hobbies
  }
}
"""


def test_valid() -> None:
    """Valid input does not have errors."""
    result = schema.execute(valid_op, variables={"u": "valid", "h": ["read", "swim"]})
    assert result.errors is None
    assert result.data == {"user": {"username": "valid", "hobbies": ["read", "swim"]}}


def test_invalid() -> None:
    """Multiple arguments can be invalid, and each argument can have have
    multiple errors.
    """
    result = schema.execute(valid_op, variables={"u": "A", "h": []})
    assert result.errors is not None and len(result.errors) == 1
    error = result.errors[0]
    assert error.message == "magql argument validation"
    assert error.extensions is not None
    assert error.extensions["username"][0] == "Must be lowercase."
    assert error.extensions["username"][1].startswith("Length must be between")
    assert error.extensions["hobbies"][0].startswith("Length must be at least")


def test_list_validate_item() -> None:
    """Validators can apply to list value or individual items."""
    result = schema.execute(valid_op, variables={"u": "aa", "h": ["A"]})
    assert result.errors is not None and len(result.errors) == 1
    error = result.errors[0]
    assert error.message == "magql argument validation"
    assert error.extensions is not None
    assert error.extensions["hobbies"][0].startswith("Length must be at least")
    assert error.extensions["hobbies"][1] == ["Must be lowercase."]


def test_list_mixed_valid() -> None:
    """Valid list values have None placeholder in errors."""
    result = schema.execute(valid_op, variables={"u": "aa", "h": ["a", "B"]})
    assert result.errors is not None and len(result.errors) == 1
    assert result.errors[0].message == "magql argument validation"
    assert result.errors[0].extensions is not None
    assert result.errors[0].extensions["hobbies"][0] == [None, "Must be lowercase."]


def test_invalid_missing_arg() -> None:
    """Missing argument will be caught by GraphQL syntax validation and won't
    trigger input validation.
    """
    # username is required, hobbies isn't
    result = schema.execute("{ user { username } }", variables={"h": ["a", "b"]})
    assert result.errors is not None and len(result.errors) == 1
    assert "'username' of type 'String!' is required" in result.errors[0].message


def test_invalid_null_value() -> None:
    """Null value will be caught by GraphQL type validation and won't trigger
    input validation.
    """
    # username is non-null, hobbies is null
    result = schema.execute("{ user(username: null, hobbies: null) { username } }")
    assert result.errors is not None and len(result.errors) == 1
    assert "'String!', found null" in result.errors[0].message


def test_invalid_type_value() -> None:
    """Value with incorrect type will be caught by GraphQL type validation and
    won't trigger input validation.
    """
    result = schema.execute("{ user(username: 1) { username } }")
    assert result.errors is not None and len(result.errors) == 1
    assert "non string value: 1" in result.errors[0].message


def test_unhandled_error() -> None:
    """A Python error raised during validation is reported as a general error."""
    result = schema.execute("""{ user(username: "aa", hobbies: null) { username } }""")
    assert result.errors is not None and len(result.errors) == 1
    assert "'NoneType' has no len()" in result.errors[0].message
