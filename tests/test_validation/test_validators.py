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


def test_valid_user() -> None:
    """Valid input does not have errors."""
    result = schema.execute(
        valid_op,
        variables={
            "u": "validuser",
            "p": "validpass",
            "pc": "validpass",
            "e": "validemail@example.com",
            "g": "A",
            "h": "1.75",
            "w": "70",
            "a": "25",
            "ex": "5",
        },
    )
    assert result.errors is None
    assert result.data == {
        "user": {
            "username": "validuser",
            "password": "validpass",
            "password_confirm": "validpass",
            "email": "validemail@example.com",
            "grade": "A",
            "height": 1.75,
            "weight": 70,
            "age": 25,
            "experience": 5,
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
)
def test_invalid_fields(field, variable, value, error_msg):
    """Invalid input when field values are not valid."""
    variables = {
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
    # Set the value for the field being tested
    variables[variable] = value
    result = schema.execute(valid_op, variables=variables)
    assert result.errors and len(result.errors) == 1
    assert result.errors[0].message == "magql argument validation"
    assert result.errors[0].extensions
    assert result.errors[0].extensions[field][0] == error_msg


# def test_invalid_username_length() -> None:
#     """Invalid input when username length is not between 2 and 10."""
#     result = schema.execute(
#         valid_op,
#         variables={
#             "u": "a",
#             "p": "validpass",
#             "pc": "validpass",
#             "e": "validemail@example.com",
#             "g": "A",
#             "h": "1.75",
#             "w": "70",
#             "a": "25",
#             "ex": "5",
#         },
#     )
#     assert result.errors and len(result.errors) == 1
#     assert result.errors[0].message == "magql argument validation"
#     assert result.errors[0].extensions
#     username_error = result.errors[0].extensions["username"][0]
#     assert username_error == "Length must be between 2 and 10, but was 1."

# def test_invalid_password_length() -> None:
#     """Invalid input when password length is less than 8."""
#     result = schema.execute(
#         valid_op,
#         variables={
#             "u": "validuser",
#             "p": "pass",
#             "pc": "pass",
#             "e": "validemail@example.com",
#             "g": "A",
#             "h": "1.75",
#             "w": "70",
#             "a": "25",
#             "ex": "5",
#         },
#     )
#     assert result.errors and len(result.errors) == 1
#     assert result.errors[0].message == "magql argument validation"
#     assert result.errors[0].extensions
#     password_error = result.errors[0].extensions["password"][0]
#     assert password_error == "Length must be at least 8, but was 4."

# def test_invalid_password_confirmation() -> None:
#     """Invalid input when password confirmation does not match the password."""
#     result = schema.execute(
#         valid_op,
#         variables={
#             "u": "validuser",
#             "p": "validpass",
#             "pc": "invalidpass",
#             "e": "validemail@example.com",
#             "g": "A",
#             "h": "1.75",
#             "w": "70",
#             "a": "25",
#             "ex": "5",
#         },
#     )
#     assert result.errors and len(result.errors) == 1
#     assert result.errors[0].message == "magql argument validation"
#     assert result.errors[0].extensions
#     confirm_error = result.errors[0].extensions["password_confirm"][0]
#     assert confirm_error == "Must equal the value given in 'password'."

# def test_invalid_email_length() -> None:
#     """Invalid input when email length is more than 50."""
#     result = schema.execute(
#         valid_op,
#         variables={
#             "u": "validuser",
#             "p": "validpass",
#             "pc": "validpass",
#             "e": "a" * 51 + "@example.com",
#             "g": "A",
#             "h": "1.75",
#             "w": "70",
#             "a": "25",
#             "ex": "5",
#         },
#     )
#     assert result.errors and len(result.errors) == 1
#     assert result.errors[0].message == "magql argument validation"
#     assert result.errors[0].extensions
#     email_error = result.errors[0].extensions["email"][0]
#     assert email_error == "Length must be at most 50, but was 63."

# def test_invalid_grade_length() -> None:
#     """Invalid input when grade length is not 1."""
#     result = schema.execute(
#         valid_op,
#         variables={
#             "u": "validuser",
#             "p": "validpass",
#             "pc": "validpass",
#             "e": "validemail@example.com",
#             "g": "AB",
#             "h": "1.75",
#             "w": "70",
#             "a": "25",
#             "ex": "5",
#         },
#     )
#     assert result.errors and len(result.errors) == 1
#     assert result.errors[0].message == "magql argument validation"
#     assert result.errors[0].extensions
#     grade_error = result.errors[0].extensions["grade"][0]
#     assert grade_error == "Length must be exactly 1, but was 2."

# def test_invalid_height_range() -> None:
#     """Invalid input when height is not between 0.0 and 2.5."""
#     result = schema.execute(
#         valid_op,
#         variables={
#             "u": "validuser",
#             "p": "validpass",
#             "pc": "validpass",
#             "e": "validemail@example.com",
#             "g": "A",
#             "h": "3.0",
#             "w": "70",
#             "a": "25",
#             "ex": "5",
#         },
#     )
#     assert result.errors and len(result.errors) == 1
#     assert result.errors[0].message == "magql argument validation"
#     assert result.errors[0].extensions
#     height_error = result.errors[0].extensions["height"][0]
#     assert height_error == "Must be between 0.0 and 2.5."


# def test_invalid_weight_max() -> None:
#     """Invalid input when weight is above 200."""
#     result = schema.execute(
#         valid_op,
#         variables={
#             "u": "validuser",
#             "p": "validpass",
#             "pc": "validpass",
#             "e": "validemail@example.com",
#             "g": "A",
#             "h": "1.75",
#             "w": "201",
#             "a": "25",
#             "ex": "5",
#         },
#     )
#     assert result.errors and len(result.errors) == 1
#     assert result.errors[0].message == "magql argument validation"
#     assert result.errors[0].extensions
#     weight_error = result.errors[0].extensions["weight"][0]
#     assert weight_error == "Must be at most 200."

# def test_invalid_age_min() -> None:
#     """Invalid input when age is below 0."""
#     result = schema.execute(
#         valid_op,
#         variables={
#             "u": "validuser",
#             "p": "validpass",
#             "pc": "validpass",
#             "e": "validemail@example.com",
#             "g": "A",
#             "h": "1.75",
#             "w": "70",
#             "a": "-1",
#             "ex": "5",
#         },
#     )
#     assert result.errors and len(result.errors) == 1
#     assert result.errors[0].message == "magql argument validation"
#     assert result.errors[0].extensions
#     age_error = result.errors[0].extensions["age"][0]
#     assert age_error == "Must be at least 0."

# def test_invalid_experience_value() -> None:
#     """Invalid input when experience is not equal to 5."""
#     result = schema.execute(
#         valid_op,
#         variables={
#             "u": "validuser",
#             "p": "validpass",
#             "pc": "validpass",
#             "e": "validemail@example.com",
#             "g": "A",
#             "h": "1.75",
#             "w": "70",
#             "a": "25",
#             "ex": "4",
#         },
#     )
#     assert result.errors and len(result.errors) == 1
#     assert result.errors[0].message == "magql argument validation"
#     assert result.errors[0].extensions
#     experience_error = result.errors[0].extensions["experience"][0]
#     assert experience_error == "Must be between 5 and 5."
