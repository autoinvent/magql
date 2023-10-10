from __future__ import annotations

import typing as t
from dataclasses import dataclass

import graphql
import pytest

import magql.validators


@dataclass
class User:
    username: str
    password: str
    password_confirm: str
    email: str
    grade: str
    height: float
    weight: int
    age: int
    experience: int


UserType = magql.Object(
    "User",
    fields={
        "username": "String!",
        "password": "String!",
        "password_confirm": "String!",
        "email": "String!",
        "grade": "String!",
        "height": "Float!",
        "weight": "Int!",
        "age": "Int!",
        "experience": "Int!",
    },
)

schema = magql.Schema(types=[UserType])


@schema.query.field(
    "user",
    UserType,
    args={
        "username": magql.Argument(
            "String!",
            validators=[
                magql.validators.Length(min=2, max=10),
            ],
        ),
        "password": magql.Argument(
            "String!",
            validators=[magql.validators.Length(min=8)],
        ),
        "password_confirm": magql.Argument(
            "String!",
            validators=[magql.validators.Confirm("password")],
        ),
        "email": magql.Argument(
            "String!",
            validators=[magql.validators.Length(max=50)],
        ),
        "grade": magql.Argument(
            "String!",
            validators=[magql.validators.Length(min=1, max=1)],
        ),
        "height": magql.Argument(
            "Float!",
            validators=[magql.validators.NumberRange(min=0.0, max=2.5)],
        ),
        "weight": magql.Argument(
            "Int!",
            validators=[magql.validators.NumberRange(max=200)],
        ),
        "age": magql.Argument(
            "Int!",
            validators=[magql.validators.NumberRange(min=0)],
        ),
        "experience": magql.Argument(
            "Int!",
            validators=[magql.validators.NumberRange(min=5, max=5)],
        ),
    },
)
def resolve_user_create(
    parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
) -> User:
    return User(
        username=kwargs["username"],
        password=kwargs["password"],
        password_confirm=kwargs["password_confirm"],
        email=kwargs["email"],
        grade=kwargs["grade"],
        height=kwargs["height"],
        weight=kwargs["weight"],
        age=kwargs["age"],
        experience=kwargs["experience"],
    )


valid_op = """\
query(
  $u: String!,
  $p: String!,
  $pc: String!,
  $e: String!,
  $g: String!,
  $h: Float!,
  $w: Int!,
  $a: Int!,
  $ex: Int!
) {
  user(
    username: $u,
    password: $p,
    password_confirm: $pc,
    email: $e,
    grade: $g,
    height: $h,
    weight: $w,
    age: $a,
    experience: $ex
  ) {
    username
    password
    password_confirm
    email
    grade
    height
    weight
    age
    experience
  }
}
"""


@pytest.fixture
def valid_user_data() -> dict[str, t.Union[str, float, int]]:
    return {
        "u": "validuser",
        "p": "validpass",
        "pc": "validpass",
        "e": "validemail@example.com",
        "g": "A",
        "h": 1.75,
        "w": 70,
        "a": 25,
        "ex": 5,
    }


def test_valid_user(valid_user_data: dict[str, t.Union[str, float, int]]) -> None:
    """Valid input does not have errors."""
    result = schema.execute(valid_op, variables=valid_user_data)
    assert result.errors is None
    assert result.data == {
        "user": {
            "username": valid_user_data["u"],
            "password": valid_user_data["p"],
            "password_confirm": valid_user_data["pc"],
            "email": valid_user_data["e"],
            "grade": valid_user_data["g"],
            "height": valid_user_data["h"],
            "weight": valid_user_data["w"],
            "age": valid_user_data["a"],
            "experience": valid_user_data["ex"],
        }
    }


@pytest.mark.parametrize(
    "field, variable, value, error_msg",
    [
        ("username", "u", "a", "Length must be between 2 and 10, but was 1."),
        ("password", "p", "pass", "Length must be at least 8, but was 4."),
        (
            "password_confirm",
            "pc",
            "invalidpass",
            "Must equal the value given in 'password'.",
        ),
        (
            "email",
            "e",
            "a" * 51 + "@example.com",
            "Length must be at most 50, but was 63.",
        ),
        ("grade", "g", "AB", "Length must be exactly 1, but was 2."),
        ("height", "h", 3.0, "Must be between 0.0 and 2.5."),
        ("weight", "w", 201, "Must be at most 200."),
        ("age", "a", -1, "Must be at least 0."),
        ("experience", "ex", 4, "Must be between 5 and 5."),
    ],
    ids=[
        "invalid_username_length",
        "invalid_password_length",
        "invalid_password_confirm",
        "invalid_email_length",
        "invalid_grade_length",
        "invalid_height_range",
        "invalid_weight_range",
        "invalid_age_range",
        "invalid_experience_range",
    ],
)
def test_invalid_fields(
    valid_user_data: dict[str, t.Union[str, float, int]],
    field: str,
    variable: str,
    value: t.Union[str, float, int],
    error_msg: str,
) -> None:
    """
    * Test various invalid input cases for each field in the User GraphQL type.

    For each parameter set, the function executes a GraphQL query using the
    provided invalid value for the specified field. It then verifies that the
    error message returned by the GraphQL execution matches the expected error
    message.

    The purpose of this function is to ensure that the validation rules for
    each field in the User GraphQL type are correctly enforced.

    :param field: The name of the field in the User GraphQL type to test.
    :param variable: The corresponding variable name in the GraphQL query.
    :param value: The invalid input value to use for testing.
    :param error_msg: The expected error message when the invalid input is used.
    """
    valid_user_data[variable] = value
    result = schema.execute(valid_op, variables=valid_user_data)
    assert result.errors and len(result.errors) == 1
    assert result.errors[0].message == "magql argument validation"
    assert result.errors[0].extensions
    assert result.errors[0].extensions[field][0] == error_msg
