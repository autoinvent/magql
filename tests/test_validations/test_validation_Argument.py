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
    The function tests the following constraints:
    *    The 'username' field must be lowercase and no more than 10 characters.
    *    The 'hobbies' field must contain at least two values,
    *       and each value must be lowercase.

    The function includes tests for:
    *    Valid inputs
    *    Invalid inputs, including an uppercase username
    *       and an empty 'hobbies' list
    *    An excessively long and uppercase username,
    *       and a 'hobbies' list with too few items and an uppercase hobby
    *    Missing arguments, specifically a
    *       missing 'username' and a missing 'hobbies' list
    *    Null arguments, specifically a null 'username' and a null 'hobbies' list
    *    Invalid types, specifically a 'username'
    *       that is not a string and a 'hobbies' list that is not a list
    *    Empty 'username' field
    """

    def resolver(parent, info, **input):
        return User(input.get("username"), input.get("hobbies"))

    LengthValidator = magql.Length(min=2, max=10)

    UserType = magql.Object(
        "User",
        fields={
            "username": magql.Field("String!"),
            "hobbies": magql.Field("[String!]"),
        },
    )

    field = magql.Field(
        UserType,
        args={
            "username": magql.Argument(
                "String!", validators=[validate_lowercase, LengthValidator]
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

    # Test with missing arguments
    # (query with a missing hobbies and a query with a missing username)
    missing_username_query = f"""
        {{
            user(hobbies: {json.dumps(valid_hobbies)})
            {{
                username
                hobbies
            }}
    }}
    """
    result = schema.execute(missing_username_query)
    assert result.errors
    assert result.errors[0].message == (
        "Field 'user' argument 'username' of type 'String!' "
        "is required, but it was not provided."
    )

    missing_hobbies_query = f"""
        {{
            user(username: "{valid_username}")
            {{
                username
                hobbies
            }}
    }}
    """
    result = schema.execute(missing_hobbies_query)
    assert not result.errors
    assert result.data["user"]["username"] == valid_username
    assert result.data["user"]["hobbies"] is None

    # Test with null arguments
    # (query with a null username and a query with a null hobbies)
    null_username_query = f"""
        {{
            user(
                username: null,
                hobbies: {json.dumps(valid_hobbies)}
            )
            {{
                username
                hobbies
            }}
    }}
    """
    result = schema.execute(null_username_query)
    assert result.errors
    assert result.errors[0].message == "Expected value of type 'String!', found null."

    null_hobbies_query = f"""
        {{
            user(
                username: "{valid_username}",
                hobbies: null
            )
            {{
                username
                hobbies
            }}
    }}
    """
    result = schema.execute(null_hobbies_query)
    assert result.errors
    assert result.errors[0].message == "object of type 'NoneType' has no len()"

    # Test with invalid types
    # (query with wrong type username and a query with wrong type hobbies)
    invalid_type_username_query = f"""
        {{
            user(
                username: 123,
                hobbies: {json.dumps(valid_hobbies)}
            )
            {{
                username
                hobbies
            }}
    }}
    """
    result = schema.execute(invalid_type_username_query)
    assert result.errors
    assert result.errors[0].message == "String cannot represent a non string value: 123"

    invalid_type_hobbies_query = f"""
        {{
            user(
                username: "{valid_username}",
                hobbies: 3
            )
            {{
                username
                hobbies
            }}
    }}
    """
    result = schema.execute(invalid_type_hobbies_query)
    assert result.errors
    assert result.errors[0].message == "String cannot represent a non string value: 3"

    # Test with empty username
    # (query with empty username "")
    empty_username_query = f"""
        {{
            user(
                username: "",
                hobbies: {json.dumps(valid_hobbies)}
            )
            {{
                username
                hobbies
            }}
    }}
    """
    result = schema.execute(empty_username_query)
    assert result.errors
    assert result.errors[0].extensions["username"][0] == "Must be lowercase."
    assert (
        result.errors[0].extensions["username"][1]
        == "Must be between 2 and 10 characters, but was 0."
    )
