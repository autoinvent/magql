import json
from typing import NamedTuple

import magql


class User(NamedTuple):
    username: str
    hobbies: list


def validate_lowercase(info, value, data):
    if not value.islower():
        raise magql.ValidationError("Must be lowercase.")


def validate_size(info, value, data):
    if len(value) < 2:
        raise magql.ValidationError("Must provide at least two values.")


def test_validator_on_argument():
    """
    docstring here
    """

    def resolver(parent, info, **input):
        return User(input.get("username"), input.get("hobbies"))

    LengthValidator = magql.Length(min=2, max=10)

    UserType = magql.Object(
        "User",
        fields={"username": magql.Field("String"), "hobbies": magql.Field("[String!]")},
    )

    field = magql.Field(
        UserType,
        args={
            "username": magql.Argument(
                "String", validators=[validate_lowercase, LengthValidator]
            ),
            "hobbies": magql.Argument(
                "[String!]", validators=[validate_size, [validate_lowercase]]
            ),
        },
        resolve=resolver,
    )

    query = magql.Object("Query")
    query.fields = {"user": field}

    schema = magql.Schema()
    schema.query = query

    # Test with valid values
    valid_username = "valid"
    valid_hobbies = ["reading", "swimming"]
    valid_query = f"""
        {{
            user(
                username: "{valid_username}",
                hobbies: {json.dumps(valid_hobbies)}
            )
            {{
                username
                hobbies
            }}
    }}
    """
    result = schema.execute(valid_query)
    assert not result.errors
    assert result.data["user"]["username"] == valid_username
    assert result.data["user"]["hobbies"] == valid_hobbies

    # Test with invalid values
    # (uppercase username, empty hobbies list)
    invalid_username = "INVALID"
    invalid_hobbies = []
    invalid_query = f"""
        {{
            user(
                username: "{invalid_username}",
                hobbies: {json.dumps(invalid_hobbies)}
            )
            {{
                username
                hobbies
            }}
    }}
    """
    result = schema.execute(invalid_query)
    assert result.errors
    assert len(result.errors[0].extensions) == 2
    assert result.errors[0].extensions["username"][0] == "Must be lowercase."
    assert (
        result.errors[0].extensions["hobbies"][0] == "Must provide at least two values."
    )

    # Test with invalid values
    # (uppercase and too long username, not enough and upperclass hobbies)
    invalid_username = "INVALIDINVALID"
    invalid_hobbies = ["READING"]
    invalid_query = f"""
        {{
            user(
                username: "{invalid_username}",
                hobbies: {json.dumps(invalid_hobbies)}
                )
                {{
                    username
                    hobbies
                }}
    }}
    """
    result = schema.execute(invalid_query)
    assert result.errors
    assert len(result.errors[0].extensions) == 2
    assert len(result.errors[0].extensions["username"]) == 2
    assert len(result.errors[0].extensions["hobbies"]) == 2
    assert result.errors[0].extensions["username"][0] == "Must be lowercase."
    assert (
        result.errors[0].extensions["username"][1]
        == "Must be between 2 and 10 characters, but was 14."
    )
    assert (
        result.errors[0].extensions["hobbies"][0] == "Must provide at least two values."
    )
    assert result.errors[0].extensions["hobbies"][1] == ["Must be lowercase."]
