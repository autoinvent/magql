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


UserInput = magql.InputObject(
    "UserInput",
    fields={
        "username": magql.InputField(
            "String!",
            validators=[validate_lowercase, magql.validators.Length(min=2, max=10)],
        ),
        "hobbies": magql.InputField(
            "[String!]",
            validators=[magql.validators.Length(min=2), [validate_lowercase]],
        ),
    },
)

NestedUserInput = magql.InputObject(
    "NestedUserInput",
    fields={"user": magql.InputField("UserInput!")},
)

schema = magql.Schema(
    types=[
        magql.Object("User", fields={"username": "String!", "hobbies": "[String!]"}),
        UserInput,
        NestedUserInput,
    ]
)


@schema.query.field("user", "User!", args={"input": magql.Argument("UserInput!")})
def resolve_user_create(
    parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
) -> User:
    input = kwargs["input"]
    return User(username=input["username"], hobbies=input.get("hobbies"))


@schema.query.field(
    "nestedUser", "User!", args={"input": magql.Argument("NestedUserInput!")}
)
def resolve_nested_user_create(
    parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
) -> User:
    input = kwargs["input"]["user"]
    return User(username=input["username"], hobbies=input.get("hobbies"))


valid_op = """\
query($i: UserInput!) {
  user(input: $i) {
    username
    hobbies
  }
}
"""

nested_valid_op = """\
query($i: NestedUserInput!) {
  nestedUser(input: $i) {
    username
    hobbies
  }
}
"""


def test_valid() -> None:
    """Valid input does not have errors."""
    result = schema.execute(
        valid_op, variables={"i": {"username": "valid", "hobbies": ["read", "swim"]}}
    )
    assert result.errors is None
    assert result.data == {"user": {"username": "valid", "hobbies": ["read", "swim"]}}


def test_invalid() -> None:
    """Multiple fields can be invalid, and each field can have have multiple errors."""
    result = schema.execute(valid_op, variables={"i": {"username": "A", "hobbies": []}})
    assert len(result.errors) == 1
    assert result.errors[0].message == "magql argument validation"
    assert (
        result.errors[0].extensions["input"][0]["username"][0] == "Must be lowercase."
    )
    assert (
        result.errors[0]
        .extensions["input"][0]["username"][1]
        .startswith("Must be between")
    )
    assert (
        result.errors[0]
        .extensions["input"][0]["hobbies"][0]
        .startswith("Must be at least")
    )


def test_list_validate_item() -> None:
    """Validators can apply to list value or individual items."""
    result = schema.execute(
        valid_op, variables={"i": {"username": "aa", "hobbies": ["A"]}}
    )
    assert len(result.errors) == 1
    assert result.errors[0].message == "magql argument validation"
    assert (
        result.errors[0]
        .extensions["input"][0]["hobbies"][0]
        .startswith("Must be at least 2")
    )
    assert result.errors[0].extensions["input"][0]["hobbies"][1] == [
        "Must be lowercase."
    ]


def test_list_mixed_valid() -> None:
    """Valid list values have None placeholder in errors."""
    result = schema.execute(
        valid_op, variables={"i": {"username": "aa", "hobbies": ["a", "B"]}}
    )
    assert len(result.errors) == 1
    assert result.errors[0].message == "magql argument validation"
    assert result.errors[0].extensions["input"][0]["hobbies"][0] == [
        None,
        "Must be lowercase.",
    ]


def test_nested_invalid() -> None:
    """Nested input objects are correctly validated."""
    result = schema.execute(
        nested_valid_op,
        variables={"i": {"user": {"username": "A", "hobbies": ["a", "b", "C"]}}},
    )
    assert len(result.errors) == 1
    assert result.errors[0].message == "magql argument validation"
    assert (
        result.errors[0].extensions["input"][0]["user"][0]["username"][0]
        == "Must be lowercase."
    )
    assert (
        result.errors[0]
        .extensions["input"][0]["user"][0]["username"][1]
        .startswith("Must be between")
    )
    assert result.errors[0].extensions["input"][0]["user"][0]["hobbies"][0] == [
        None,
        None,
        "Must be lowercase.",
    ]
