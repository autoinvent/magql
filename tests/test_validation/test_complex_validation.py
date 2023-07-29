from __future__ import annotations

import typing as t
from dataclasses import dataclass

import graphql

import magql.validators


@dataclass
class City:
    name: str
    isCalifornia: bool


@dataclass
class State:
    name: str
    abbreviation: str
    senators: list[str] | None


@dataclass
class Location:
    city: City
    state: State | None


@dataclass
class User:
    username: str
    hobbies: list[str] | None
    location: Location | None
    friends: list[str] | None
    languages: list[str] | None
    job: str | None


# Validators for username
def validate_username_contains_vowel(
    info: graphql.GraphQLResolveInfo, value: str, data: dict[str, t.Any]
) -> None:
    if not any(letter in value.lower() for letter in "aeiou"):
        raise magql.ValidationError("Username must contain at least one vowel.")


# Validators for city
def validate_city_name_capitalized(
    info: graphql.GraphQLResolveInfo, value: str, data: dict[str, t.Any]
) -> None:
    if not value[0].isupper():
        raise magql.ValidationError(
            "First letter of the city name must be capitalized."
        )


# Validators for state
def validate_state_name_capitalized(
    info: graphql.GraphQLResolveInfo, value: str, data: dict[str, t.Any]
) -> None:
    if not value[0].isupper():
        raise magql.ValidationError(
            "First letter of the state name must be capitalized."
        )


def validate_state_abbreviation_uppercase(
    info: graphql.GraphQLResolveInfo, value: str, data: dict[str, t.Any]
) -> None:
    if not value.isupper():
        raise magql.ValidationError("The state abbreviation must be uppercase.")


def validate_senators_count(
    info: graphql.GraphQLResolveInfo, value: list[str], data: dict[str, t.Any]
) -> None:
    if len(value) != 2:
        raise magql.ValidationError("A state must have exactly 2 senators.")


def validate_senators_uppercase(
    info: graphql.GraphQLResolveInfo, value: str, data: dict[str, t.Any]
) -> None:
    if not value.isupper():
        raise magql.ValidationError("Senators' names must be uppercase.")


# Validators for hobbies
def validate_hobbies_count(
    info: graphql.GraphQLResolveInfo, value: list[str], data: dict[str, t.Any]
) -> None:
    if len(value) > 4:
        raise magql.ValidationError("Too many hobbies. Maximum is 4.")


# Validators for friends
def validate_friends_count(
    info: graphql.GraphQLResolveInfo, value: list[str], data: dict[str, t.Any]
) -> None:
    if len(value) > 3:
        raise magql.ValidationError("Too many friends. Maximum is 3.")


# Validators for languages
def validate_languages_count(
    info: graphql.GraphQLResolveInfo, value: list[str], data: dict[str, t.Any]
) -> None:
    if len(value) < 2:
        raise magql.ValidationError("Too few languages. Minimum is 2.")


def validate_languages_lowercase(
    info: graphql.GraphQLResolveInfo, value: str, data: dict[str, t.Any]
) -> None:
    if not value.islower():
        raise magql.ValidationError("Languages must be lowercase.")


# Validators for jobs
def validate_job_lowercase(
    info: graphql.GraphQLResolveInfo, value: str, data: dict[str, t.Any]
) -> None:
    if not value.islower():
        raise magql.ValidationError("Job must be lowercase.")


# Validators for location_input
def validate_location_input(
    info: graphql.GraphQLResolveInfo, data: dict[str, t.Any]
) -> None:
    state_name = data["state"]["name"].lower()
    is_california = data["city"]["isCalifornia"]
    if (state_name == "california" and not is_california) or (
        state_name != "california" and is_california
    ):
        raise magql.ValidationError(
            'If the state name is "California", '
            'then "isCalifornia" must be true, and vice versa.'
        )


# Validators for user_input
def validate_user_input(
    info: graphql.GraphQLResolveInfo, data: dict[str, t.Any]
) -> None:
    if data["job"] == "programmer" and len(data["languages"]) < 3:
        raise magql.ValidationError(
            'Job "programmer" requires knowledge of at least 3 langauges.'
        )


CityType = magql.Object(
    "City",
    fields={
        "name": "String!",
        "isCalifornia": "Boolean!",
    },
)

StateType = magql.Object(
    "State",
    fields={
        "name": "String!",
        "abbreviation": "String!",
        "senators": "[String!]",
    },
)

LocationType = magql.Object(
    "Location",
    fields={
        "city": "City!",
        "state": "State",
    },
)

CityInput = magql.InputObject(
    "CityInput",
    fields={
        "name": magql.InputField(
            "String!", validators=[validate_city_name_capitalized]
        ),
        "isCalifornia": "Boolean!",
    },
)

StateInput = magql.InputObject(
    "StateInput",
    fields={
        "name": magql.InputField(
            "String!", validators=[validate_state_name_capitalized]
        ),
        "abbreviation": magql.InputField(
            "String!", validators=[validate_state_abbreviation_uppercase]
        ),
        "senators": magql.InputField(
            "[String!]",
            validators=[
                validate_senators_count,
                [validate_senators_uppercase],  # type: ignore[list-item]
            ],
        ),
    },
)

LocationInput = magql.InputObject(
    "LocationInput",
    fields={
        "city": "CityInput!",
        "state": "StateInput",
    },
    validators=[validate_location_input],
)

UserInput = magql.InputObject(
    "UserInput",
    fields={
        "username": magql.InputField(
            "String!",
            validators=[
                validate_username_contains_vowel,
                magql.validators.Length(min=4, max=10),
            ],
        ),
        "username_confirm": magql.InputField(
            "String!", validators=[magql.validators.Confirm("username")]
        ),
        "hobbies": magql.InputField(
            "[String!]",
            validators=[
                validate_hobbies_count,
                [magql.validators.Length(min=4)],  # type: ignore[list-item]
            ],
        ),
        "location": magql.InputField("LocationInput!"),
        "friends": magql.InputField(
            "[String!]",
            validators=[
                validate_friends_count,
                [magql.validators.Length(max=6)],  # type: ignore[list-item]
            ],
        ),
        "languages": magql.InputField(
            "[String!]",
            validators=[
                validate_languages_count,
                [validate_languages_lowercase],  # type: ignore[list-item]
            ],
        ),
        "job": magql.InputField("String", validators=[validate_job_lowercase]),
    },
    validators=[validate_user_input],
)

schema = magql.Schema(
    types=[
        magql.Object(
            "User",
            fields={
                "username": "String!",
                "hobbies": "[String!]",
                "location": "Location!",
                "friends": "[String!]",
                "languages": "[String!]",
                "job": "String",
            },
        ),
        CityType,
        StateType,
        LocationType,
        CityInput,
        StateInput,
        LocationInput,
        UserInput,
    ]
)


@schema.query.field("user", "User!", args={"input": magql.Argument("UserInput!")})
def resolve_user_create(
    parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
) -> User:
    input = kwargs["input"]
    location_input = input.get("location")
    city_input = location_input.get("city")
    city = City(
        name=city_input.get("name"),
        isCalifornia=city_input.get("isCalifornia"),
    )
    state_input = location_input.get("state")
    state = (
        State(
            name=state_input.get("name"),
            abbreviation=state_input.get("abbreviation"),
            senators=state_input.get("senators"),
        )
        if state_input
        else None
    )
    location = Location(city=city, state=state)

    return User(
        username=input["username"],
        hobbies=input.get("hobbies"),
        location=location,
        friends=input.get("friends"),
        languages=input.get("languages"),
        job=input.get("job"),
    )


valid_op = """\
query($i: UserInput!) {
  user(input: $i) {
    username
    hobbies
    location {
      city {
        name
        isCalifornia
      }
      state {
        name
        abbreviation
        senators
      }
    }
    friends
    languages
    job
  }
}
"""


def test_valid_user() -> None:
    """Valid user input does not have errors."""
    variables = {
        "i": {
            "username": "validuser",
            "username_confirm": "validuser",
            "hobbies": ["gaming", "reading"],
            "location": {
                "city": {
                    "name": "Los_Angeles",
                    "isCalifornia": True,
                },
                "state": {
                    "name": "California",
                    "abbreviation": "CA",
                    "senators": ["SENATOR1", "SENATOR2"],
                },
            },
            "friends": ["John", "Doe"],
            "languages": ["python", "java", "c++"],
            "job": "programmer",
        }
    }
    result = schema.execute(valid_op, variables=variables)
    assert result.errors is None
    assert result.data == {
        "user": {
            "username": "validuser",
            "hobbies": ["gaming", "reading"],
            "location": {
                "city": {
                    "name": "Los_Angeles",
                    "isCalifornia": True,
                },
                "state": {
                    "name": "California",
                    "abbreviation": "CA",
                    "senators": ["SENATOR1", "SENATOR2"],
                },
            },
            "friends": ["John", "Doe"],
            "languages": ["python", "java", "c++"],
            "job": "programmer",
        }
    }


def test_invalid_individual_input() -> None:
    """
    * Test invalid individual inputs for a user:
    - The username doesn't contain a vowel & not enough characters
    - The username_confirm doesn't match the username.
    - The job field is not in lowercase.
    """
    variables = {
        "i": {
            "username": "bbb",
            "username_confirm": "ccc",
            "hobbies": ["gaming", "reading"],
            "location": {
                "city": {
                    "name": "Los_angeles",
                    "isCalifornia": True,
                },
                "state": {
                    "name": "California",
                    "abbreviation": "CA",
                    "senators": ["SENATOR1", "SENATOR2"],
                },
            },
            "friends": ["John", "Doe"],
            "languages": ["python", "java"],
            "job": "PROGRAMMER",
        }
    }
    result = schema.execute(valid_op, variables=variables)
    assert result.errors and len(result.errors) == 1
    assert result.errors[0].extensions
    username_err = result.errors[0].extensions["input"][0]["username"]
    confirm_err = result.errors[0].extensions["input"][0]["username_confirm"]
    job_err = result.errors[0].extensions["input"][0]["job"]
    assert username_err[0] == "Username must contain at least one vowel."
    assert username_err[1] == "Length must be between 4 and 10, but was 3."
    assert confirm_err[0] == "Must equal the value given in 'username'."
    assert job_err[0] == "Job must be lowercase."


def test_invalid_list_inputs() -> None:
    """
    * Test mixed invalid list inputs for a user:
    - The number of hobbies exceeds the maximum limit.
    - The length of some hobbies is less than the minimum requirement.
    - The number of friends exceeds the maximum limit.
    - The length of some friend's names exceeds the maximum limit.
    - The number of languages is less than the minimum requirement.
    - The languages are not lowercase.
    - The job is progammer, but languages is less than minimum requirement.
    """
    variables = {
        "i": {
            "username": "validuser",
            "username_confirm": "validuser",
            "hobbies": ["valid", "valid2", "no", "valid3", "oh"],
            "location": {
                "city": {
                    "name": "Los_Angeles",
                    "isCalifornia": True,
                },
                "state": {
                    "name": "California",
                    "abbreviation": "CA",
                    "senators": ["SENATOR1", "SENATOR2"],
                },
            },
            "friends": ["Johnnie", "Doe", "Jennifer", "Smith"],
            "languages": ["Python"],
            "job": "programmer",
        }
    }
    result = schema.execute(valid_op, variables=variables)
    assert result.errors and len(result.errors) == 1
    assert result.errors[0].extensions
    input_err = result.errors[0].extensions["input"][0][""]
    hobbies_err = result.errors[0].extensions["input"][0]["hobbies"]
    friends_err = result.errors[0].extensions["input"][0]["friends"]
    languages_err = result.errors[0].extensions["input"][0]["languages"]
    assert input_err[0].startswith('Job "programmer" requires')
    assert hobbies_err[0] == "Too many hobbies. Maximum is 4."
    assert friends_err[0] == "Too many friends. Maximum is 3."
    assert languages_err[0] == "Too few languages. Minimum is 2."
    assert hobbies_err[1] == [
        None,
        None,
        "Length must be at least 4, but was 2.",
        None,
        "Length must be at least 4, but was 2.",
    ]
    assert friends_err[1] == [
        "Length must be at most 6, but was 7.",
        None,
        "Length must be at most 6, but was 8.",
        None,
    ]
    assert languages_err[1] == ["Languages must be lowercase."]


def test_invalid_inputObject_inputs() -> None:
    """
    * Test invalid input objects for a user:
    - The city name is not capitalized.
    - The state name is not capitalized.
    - The state abbreviation is not in uppercase.
    - The number of senators exceeds the limit.
    - The senator's names are not in uppercase.
    - The amount of senators violates the limit.
    """
    variables = {
        "i": {
            "username": "validuser",
            "username_confirm": "validuser",
            "hobbies": ["gaming", "reading"],
            "location": {
                "city": {
                    "name": "phoenix",
                    "isCalifornia": True,
                },
                "state": {
                    "name": "arizona",
                    "abbreviation": "Az",
                    "senators": ["senator1", "SENATOR2", "senator3"],
                },
            },
            "friends": ["John", "Doe"],
            "languages": ["python", "java", "c++"],
            "job": "programmer",
        }
    }
    result = schema.execute(valid_op, variables=variables)
    assert result.errors and len(result.errors) == 1
    assert result.errors[0].extensions
    extensions = result.errors[0].extensions
    input_err = extensions["input"][0]["location"][0][""]
    city_err = extensions["input"][0]["location"][0]["city"][0]["name"]
    state_name_err = extensions["input"][0]["location"][0]["state"][0]["name"]
    state_abb_err = extensions["input"][0]["location"][0]["state"][0]["abbreviation"]
    senator_err = extensions["input"][0]["location"][0]["state"][0]["senators"]
    assert input_err[0].startswith('If the state name is "California",')
    assert city_err[0] == "First letter of the city name must be capitalized."
    assert state_name_err[0] == "First letter of the state name must be capitalized."
    assert state_abb_err[0] == "The state abbreviation must be uppercase."
    assert senator_err[0] == "A state must have exactly 2 senators."
    assert senator_err[1] == [
        "Senators' names must be uppercase.",
        None,
        "Senators' names must be uppercase.",
    ]
