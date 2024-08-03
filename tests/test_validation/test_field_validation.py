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
    profession: str | None
    hobbies: list[str] | None


def validate_profession_given_if_hobbies(
    info: graphql.GraphQLResolveInfo, data: dict[str, t.Any]
) -> None:
    hobbies = data.get("hobbies")
    profession = data.get("profession")
    if hobbies is not None and len(hobbies) < 3 and profession is not None:
        raise magql.ValidationError(
            "Profession cannot be provided "
            "if the user does not have more than 2 hobbies."
        )


def validate_profession_starts_with_username(
    info: graphql.GraphQLResolveInfo, data: dict[str, t.Any]
) -> None:
    username = data.get("username")
    profession = data.get("profession")
    if profession is not None and not profession.startswith(f"{username}_"):
        raise magql.ValidationError(
            "Profession must start with username followed by '_'."
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
    variables = {"u": "K", "h": ["reading", "swimming", "coding"], "p": "K_programmer"}
    result = expect_data(schema, valid_op, variables=variables)
    assert result == {
        "user": {
            "username": "K",
            "hobbies": ["reading", "swimming", "coding"],
            "profession": "K_programmer",
        }
    }


def test_invalid_profession_given_hobbies() -> None:
    """Invalid input when profession is provided but hobbies length is less than 3."""
    variables = {"u": "K", "h": ["reading", "swimming"], "p": "K_programmer"}
    result = expect_validation_error(schema, valid_op, variables=variables)
    assert result[""][0].startswith("Profession cannot be")


def test_invalid_profession_starts_with_username() -> None:
    """Invalid input when profession does not start with username."""
    variables = {"u": "K", "h": ["reading", "swimming", "coding"], "p": "programmer_K"}
    result = expect_validation_error(schema, valid_op, variables=variables)
    assert result[""][0].startswith("Profession must start with")


def test_invalid_multiple_errors() -> None:
    """Invalid input when profession violates two validations"""
    variables = {"u": "K", "h": ["Reading"], "p": "Doctor"}
    result = expect_validation_error(schema, valid_op, variables=variables)
    assert result[""][0].startswith("Profession cannot be")
    assert result[""][1].startswith("Profession must start with")
