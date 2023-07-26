from __future__ import annotations

import typing as t
from dataclasses import dataclass

import graphql

import magql.validators


@dataclass
class User:
    username: str
    profession: str | None
    hobbies: list[str] | None


def validate_profession_given_if_hobbies(
    info: graphql.GraphQLResolveInfo, data: dict[str, t.Any]
) -> None:
    hobbies = data.get("hobbies")
    profession = data.get("profession")
    if hobbies is not None and len(hobbies) < 3 and profession is not None:
        error_message = (
            "Profession cannot be provided if the user does not have "
            "more than 2 hobbies."
        )
        raise magql.ValidationError({"profession": [error_message]})


def validate_profession_starts_with_username(
    info: graphql.GraphQLResolveInfo, data: dict[str, t.Any]
) -> None:
    username = data.get("username")
    profession = data.get("profession")
    if profession is not None and not profession.startswith(f"{username}_"):
        raise magql.ValidationError(
            {"profession": ["Profession must start with username followed by '_'."]}
        )


schema = magql.Schema(
    types=[
        magql.Object(
            "User",
            fields={
                "username": "String!",
                "hobbies": "[String!]",
                "profession": "String",
            },
        )
    ]
)


@schema.query.field(
    "user",
    "User!",
    args={
        "username": magql.Argument("String!"),
        "profession": magql.Argument("String"),
        "hobbies": magql.Argument("[String!]"),
    },
    validators=[
        validate_profession_given_if_hobbies,
        validate_profession_starts_with_username,
    ],
)
def resolve_user_create(
    parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
) -> User:
    return User(
        username=kwargs["username"],
        profession=kwargs.get("profession"),
        hobbies=kwargs.get("hobbies"),
    )


valid_op = """\
query($u: String!, $h: [String!], $p: String) {
  user(username: $u, hobbies: $h, profession: $p) {
    username
    hobbies
    profession
  }
}
"""


def test_valid_user() -> None:
    """Valid input does not have errors."""
    variables = {"u": "K", "h": ["reading", "swimming", "coding"], "p": "K_engineer"}
    result = schema.execute(valid_op, variables=variables)
    assert result.errors is None
    assert result.data == {
        "user": {
            "username": "K",
            "hobbies": ["reading", "swimming", "coding"],
            "profession": "K_engineer",
        }
    }


def test_valid_no_profession() -> None:
    """Valid input when no profession and hobbies are provided."""
    variables = {"u": "K", "h": None, "p": None}
    result = schema.execute(valid_op, variables=variables)
    assert result.errors is None
    assert result.data == {
        "user": {"username": "K", "hobbies": None, "profession": None}
    }


def test_invalid_profession_given_hobbies() -> None:
    """Invalid input when profession is provided but hobbies length is less than 3."""
    variables = {"u": "K", "h": ["reading", "swimming"], "p": "K_engineer"}
    result = schema.execute(valid_op, variables=variables)
    assert result.errors and len(result.errors) == 1
    error = result.errors[0]
    assert error.message == "magql argument validation"
    assert error.extensions
    assert error.extensions["profession"][0].startswith("Profession cannot be")


def test_invalid_profession_starts_with_username() -> None:
    """Invalid input when profession does not start with username."""
    variables = {"u": "K", "h": ["reading", "swimming", "coding"], "p": "engineer_K"}
    result = schema.execute(valid_op, variables=variables)
    assert result.errors and len(result.errors) == 1
    error = result.errors[0]
    assert error.message == "magql argument validation"
    assert error.extensions
    assert error.extensions["profession"][0].startswith("Profession must start with")


def test_invalid_multiple_errors() -> None:
    """Invalid input when profession violates two validations"""
    variables = {"u": "K", "h": ["Reading"], "p": "Doctor"}
    result = schema.execute(valid_op, variables=variables)
    assert result.errors and len(result.errors) == 1
    error = result.errors[0]
    assert error.message == "magql argument validation"
    assert error.extensions
    assert error.extensions["profession"][0].startswith("Profession cannot be")
    assert error.extensions["profession"][1].startswith("Profession must start with")
