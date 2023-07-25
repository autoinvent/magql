from __future__ import annotations

import typing as t
from dataclasses import dataclass

import graphql

import magql
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


UserInput = magql.InputObject(
    "UserInput",
    fields={
        "username": magql.InputField("String!"),
        "profession": magql.InputField("String"),
        "hobbies": magql.InputField("[String]"),
    },
    validators=[
        validate_profession_given_if_hobbies,
        validate_profession_starts_with_username,
    ],
)

schema = magql.Schema(
    types=[
        magql.Object(
            "User",
            fields={
                "username": "String!",
                "profession": "String",
                "hobbies": "[String]",
            },
        ),
        UserInput,
    ]
)


@schema.query.field("user", "User!", args={"input": magql.Argument("UserInput!")})
def resolve_user_create(
    parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
) -> User:
    input = kwargs["input"]
    return User(
        username=input["username"],
        profession=input.get("profession"),
        hobbies=input.get("hobbies"),
    )


valid_op = """\
query($i: UserInput!) {
  user(input: $i) {
    username
    profession
    hobbies
  }
}
"""


def test_valid() -> None:
    """Valid input does not have errors."""
    variables = {
        "i": {
            "username": "K",
            "profession": "K_Programmer",
            "hobbies": ["Reading", "Swimming", "Coding"],
        }
    }
    result = expect_data(schema, valid_op, variables=variables)
    assert result == {
        "user": {
            "username": "K",
            "profession": "K_Programmer",
            "hobbies": ["Reading", "Swimming", "Coding"],
        }
    }


def test_invalid_profession_given_hobbies() -> None:
    """Invalid input when profession is provided but hobbies length is less than 3."""
    variables = {
        "i": {"username": "K", "profession": "K_Programmer", "hobbies": ["Reading"]}
    }
    result = expect_validation_error(schema, valid_op, variables=variables)
    assert result["input"][0][""][0].startswith("Profession cannot be")


def test_invalid_profession_name() -> None:
    """Invalid input when profession does not start with username."""
    variables = {
        "i": {
            "username": "K",
            "profession": "Programmer",
            "hobbies": ["Reading", "Swimming", "Coding"],
        }
    }
    result = expect_validation_error(schema, valid_op, variables=variables)
    assert result["input"][0][""][0].startswith("Profession must start with")


def test_invalid_multiple_errors() -> None:
    """Invalid input when profession violates two validations"""
    variables = {"i": {"username": "K", "profession": "Doctor", "hobbies": ["Reading"]}}
    result = expect_validation_error(schema, valid_op, variables=variables)
    assert result["input"][0][""][0].startswith("Profession cannot be")
    assert result["input"][0][""][1].startswith("Profession must start with")
