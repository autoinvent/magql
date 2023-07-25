from __future__ import annotations

import typing as t
from dataclasses import dataclass

import graphql

import magql


@dataclass
class User:
    username: str
    profession: str | None
    hobbies: list[str] | None


def validate_profession_given_if_hobbies(info, data):
    hobbies = data.get("hobbies")
    profession = data.get("profession")
    if hobbies is not None and len(hobbies) < 3 and profession is not None:
        error_message = (
            "Profession cannot be provided if the user does not have "
            "more than 2 hobbies."
        )
        raise magql.ValidationError({"profession": [error_message]})


def validate_profession_starts_with_username(info, data):
    username = data.get("username")
    profession = data.get("profession")
    if profession is not None and not profession.startswith(f"{username}_"):
        raise magql.ValidationError(
            {"profession": ["Profession must start with username followed by '_'."]}
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


def test_valid_user() -> None:
    """Valid input does not have errors."""
    variables = {
        "i": {
            "username": "K",
            "profession": "K_Coder",
            "hobbies": ["Reading", "Swimming", "Coding"],
        }
    }
    result = schema.execute(valid_op, variables=variables)

    assert result.errors is None
    expected_data = {
        "user": {
            "username": "K",
            "profession": "K_Coder",
            "hobbies": ["Reading", "Swimming", "Coding"],
        }
    }
    assert result.data == expected_data


def test_no_profession_provided() -> None:
    """Valid input when no profession is provided."""
    variables = {"i": {"username": "K", "hobbies": ["Reading", "Swimming"]}}
    result = schema.execute(valid_op, variables=variables)

    assert result.errors is None
    expected_data = {
        "user": {
            "username": "K",
            "profession": None,
            "hobbies": ["Reading", "Swimming"],
        }
    }
    assert result.data == expected_data


def test_invalid_profession_given_hobbies() -> None:
    """Invalid input when profession is provided but hobbies length is less than 3."""
    variables = {
        "i": {"username": "K", "profession": "K_Coder", "hobbies": ["Reading"]}
    }
    result = schema.execute(valid_op, variables=variables)
    errors = result.errors[0].extensions["input"][0]["profession"]
    assert len(result.errors) == 1
    assert result.errors[0].message == "magql argument validation"
    assert errors[0].startswith("Profession cannot be")


def test_invalid_profession_name() -> None:
    """Invalid input when profession does not start with username."""
    variables = {
        "i": {
            "username": "K",
            "profession": "Coder",
            "hobbies": ["Reading", "Swimming", "Coding"],
        }
    }
    result = schema.execute(valid_op, variables=variables)
    errors = result.errors[0].extensions["input"][0]["profession"]
    assert len(result.errors) == 1
    assert result.errors[0].message == "magql argument validation"
    assert errors[0].startswith("Profession must start with")


def test_invalid_multiple_errors():
    """Invalid input when profession violates two validations"""
    variables = {"i": {"username": "K", "profession": "Doctor", "hobbies": ["Reading"]}}
    result = schema.execute(valid_op, variables=variables)
    errors = result.errors[0].extensions["input"][0]["profession"]
    assert len(result.errors) == 1
    assert result.errors[0].message == "magql argument validation"
    assert errors[0].startswith("Profession cannot be")
    assert errors[1].startswith("Profession must start with")
