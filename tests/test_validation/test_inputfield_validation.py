from __future__ import annotations

import typing as t
from dataclasses import dataclass

import graphql

import magql.validators
from magql.testing import expect_data
from magql.testing import expect_validation_error


@dataclass
class User:
    username: str
    hobbies: list[str] | None


def validate_lowercase(
    info: graphql.GraphQLResolveInfo, value: str, data: dict[str, t.Any]
) -> None:
    if not value.islower():
        raise magql.ValidationError("Must be lowercase.")


def validate_specific_user_input(
    info: graphql.GraphQLResolveInfo, value: dict[str, t.Any], data: dict[str, t.Any]
) -> None:
    if value == {"username": "A", "hobbies": ["a", "b", "C"]}:
        raise magql.ValidationError("Specific UserInput is not allowed.")


UserInput = magql.InputObject(
    "UserInput",
    fields={
        "username": magql.InputField(
            "String!",
            validators=[validate_lowercase, magql.validators.Length(min=2, max=10)],
        ),
        "hobbies": magql.InputField(
            "[String!]",
            validators=[
                magql.validators.Length(min=2),
                [validate_lowercase],  # type: ignore[list-item]
            ],
        ),
    },
)

NestedUserInput = magql.InputObject(
    "NestedUserInput",
    fields={
        "user": magql.InputField(
            "UserInput!", validators=[validate_specific_user_input]
        )
    },
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
    variables = {"i": {"username": "valid", "hobbies": ["read", "swim"]}}
    result = expect_data(schema, valid_op, variables=variables)
    assert result == {"user": {"username": "valid", "hobbies": ["read", "swim"]}}


def test_invalid() -> None:
    """Multiple fields can be invalid, and each field can have have multiple errors."""
    result = expect_validation_error(
        schema, valid_op, variables={"i": {"username": "A", "hobbies": []}}
    )
    assert result["input"][0]["username"][0] == "Must be lowercase."
    assert result["input"][0]["username"][1].startswith("Length must be between")
    assert result["input"][0]["hobbies"][0].startswith("Length must be at least")


def test_list_validate_item() -> None:
    """Validators can apply to list value or individual items."""
    variables = {"i": {"username": "aa", "hobbies": ["A"]}}
    result = expect_validation_error(schema, valid_op, variables=variables)
    assert result["input"][0]["hobbies"][0].startswith("Length must be at least")
    assert result["input"][0]["hobbies"][1] == ["Must be lowercase."]


def test_list_mixed_valid() -> None:
    """Valid list values have None placeholder in errors."""
    variables = {"i": {"username": "aa", "hobbies": ["a", "B"]}}
    result = expect_validation_error(schema, valid_op, variables=variables)
    assert result["input"][0]["hobbies"][0] == [None, "Must be lowercase."]


def test_nested_valid() -> None:
    """Nested valid input does not have errors."""
    variables = {"i": {"user": {"username": "valid", "hobbies": ["read", "swim"]}}}
    result = expect_data(schema, nested_valid_op, variables=variables)
    assert result == {"nestedUser": {"username": "valid", "hobbies": ["read", "swim"]}}


def test_nested_invalid() -> None:
    """Nested input objects are correctly validated."""
    variables = {"i": {"user": {"username": "A", "hobbies": ["a", "b", "C"]}}}
    result = expect_validation_error(schema, nested_valid_op, variables=variables)
    arg = result["input"][0]
    assert arg["user"][0]["username"][0] == "Must be lowercase."
    assert arg["user"][0]["username"][1].startswith("Length must be between")
    assert arg["user"][0]["hobbies"][0] == [None, None, "Must be lowercase."]
    assert arg["user"][1] == "Specific UserInput is not allowed."
