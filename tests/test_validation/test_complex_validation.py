from __future__ import annotations

import typing as t
from dataclasses import dataclass

import graphql

import magql
from magql.testing import expect_data
from magql.testing import expect_validation_error


@dataclass
class Depth:
    stringValue: list[list[list[list[str]]]] | None
    intValue: list[list[int]] | None


# stringValue Validators (InputField)
def validate_first_list_length(
    info: graphql.GraphQLResolveInfo, value: t.Any, data: dict[str, t.Any]
) -> None:
    if len(value) != 2:
        raise magql.ValidationError("Outer list must have at exactly 2 items.")


def validate_second_list_length(
    info: graphql.GraphQLResolveInfo, value: t.Any, data: dict[str, t.Any]
) -> None:
    if len(value) != 3:
        raise magql.ValidationError("Middle list must have at exactly 3 items.")


def validate_third_list_length(
    info: graphql.GraphQLResolveInfo, value: t.Any, data: dict[str, t.Any]
) -> None:
    if len(value) != 4:
        raise magql.ValidationError("Inner list must have at exactly 4 items.")


def validate_contains_special_character(
    info: graphql.GraphQLResolveInfo, value: str, data: dict[str, t.Any]
) -> None:
    special_characters = "!#$%&'()*+,-./:;<=>?@[]^_`{|}~"
    if not any(char in special_characters for char in value):
        raise magql.ValidationError("Must contain a special character.")


# intValue Validators (InputField)
def validate_integer_properties(
    info: graphql.GraphQLResolveInfo, value: t.Any, data: dict[str, t.Any]
) -> None:
    errors = [
        message
        for condition, message in [
            (value % 2 != 0, "Must be even."),
            (value < 0, "Must be positive."),
        ]
        if condition
    ]
    if errors:
        raise magql.ValidationError([errors])


# DepthInput Validators (InputObject)
def validate_user_input(
    info: graphql.GraphQLResolveInfo, data: dict[str, t.Any]
) -> None:
    stringValue = data.get("stringValue")
    intValue = data.get("intValue")
    if stringValue and intValue and len(intValue) < len(stringValue):
        raise magql.ValidationError(
            "Length of intValue should not be shorter than the length of stringValue."
        )


DepthInput = magql.InputObject(
    "DepthInput",
    fields={
        "stringValue": magql.InputField(
            "[[[String!]]]!",
            validators=[
                validate_first_list_length,
                [
                    validate_second_list_length,
                    [validate_third_list_length, [validate_contains_special_character]],
                ],  # type: ignore[list-item]
            ],
        ),
        "intValue": magql.InputField(
            "[[Int!]]",
            validators=[[[validate_integer_properties]]],  # type: ignore[list-item]
        ),
    },
    validators=[validate_user_input],
)

schema = magql.Schema(
    types=[
        magql.Object(
            "Depth",
            fields={
                "stringValue": "[[[String!]]]",
                "intValue": "[[Int!]]",
            },
        ),
        DepthInput,
    ]
)


@schema.query.field("depth", "Depth!", args={"input": magql.Argument("DepthInput!")})
def resolve_depth(
    parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
) -> Depth:
    input = kwargs["input"]
    return Depth(
        stringValue=input.get("stringValue"),
        intValue=input.get("intValue"),
    )


valid_op = """\
query($i: DepthInput!) {
  depth(input: $i) {
    stringValue
    intValue
  }
}
"""


def test_valid_input() -> None:
    """Valid input does not have errors."""
    variables = {
        "i": {
            "stringValue": [
                [
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                ],
                [
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                ],
            ],
            "intValue": [[2, 4], [98, 2, 44], [4]],
        }
    }
    result = expect_data(schema, valid_op, variables=variables)
    assert result == {
        "depth": {
            "stringValue": [
                [
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                ],
                [
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                ],
            ],
            "intValue": [[2, 4], [98, 2, 44], [4]],
        }
    }


def test_invalid_items() -> None:
    """Test case for validating the contents of nested lists in the query.
    'stringValue': some strings do not contain special chars
    'intValue': some integers are negative | odd
    Also verifies the capability of the validation logic to
    return multiple error messages for a single item when necessary.
    """
    variables = {
        "i": {
            "stringValue": [
                [
                    ["noSpecial", "#special", "!special", "noSpecial"],
                    ["!special", "noSpecial", "!special", "#special"],
                    ["!special", "#special", "noSpecial", "#special"],
                ],
                [
                    ["!special", "noSpecial", "!special", "#special"],
                    ["!special", "#special", "noSpecial", "noSpecial"],
                    ["noSpecial", "#special", "!special", "#special"],
                ],
            ],
            "intValue": [[2, 4, -4], [1, 2], [-43, -4, 3]],
        }
    }
    result = expect_validation_error(schema, valid_op, variables=variables)
    assert result["input"][0]["stringValue"][0] == [
        [
            [
                "Must contain a special character.",
                None,
                None,
                "Must contain a special character.",
            ],
            [None, "Must contain a special character.", None, None],
            [None, None, "Must contain a special character.", None],
        ],
        [
            [None, "Must contain a special character.", None, None],
            [
                None,
                None,
                "Must contain a special character.",
                "Must contain a special character.",
            ],
            ["Must contain a special character.", None, None, None],
        ],
    ]
    assert result["input"][0]["intValue"][0] == [
        [None, None, ["Must be positive."]],
        [["Must be even."], None],
        [
            ["Must be even.", "Must be positive."],
            ["Must be positive."],
            ["Must be even."],
        ],
    ]


def test_invalid_nested_lists() -> None:
    """Test case for validating the structure of nested lists in the query.
    'stringValue': Lists do not adhere to required length specifications.
    Validates the incorrect list lengths at each nesting level.
    """
    variables = {
        "i": {
            "stringValue": [
                [
                    ["!special", "#special"],
                    ["!special", "#special", "!special"],
                    ["!special", "#special", "!special", "#special"],
                    ["!special"],
                ],
                [
                    ["!special", "#special", "!special"],
                    ["!special", "#special", "!special"],
                ],
                [
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                ],
            ],
        }
    }
    result = expect_validation_error(schema, valid_op, variables=variables)
    assert result["input"][0]["stringValue"] == [
        "Outer list must have at exactly 2 items.",
        [
            "Middle list must have at exactly 3 items.",
            [
                "Inner list must have at exactly 4 items.",
                "Inner list must have at exactly 4 items.",
                None,
                "Inner list must have at exactly 4 items.",
            ],
            "Middle list must have at exactly 3 items.",
            [
                "Inner list must have at exactly 4 items.",
                "Inner list must have at exactly 4 items.",
            ],
            None,
        ],
    ]


def test_invalid_object() -> None:
    """Test case for validating the structure of the overall input object.
    'intValue': Its length is shorter than 'stringValue'.
    Asserts ability to validate a collection of inputs.
    """
    variables = {
        "i": {
            "stringValue": [
                [
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                ],
                [
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                    ["!special", "#special", "!special", "#special"],
                ],
            ],
            "intValue": [[2, 4]],
        }
    }
    result = expect_validation_error(schema, valid_op, variables=variables)
    assert (
        result["input"][0][""][0]
        == "Length of intValue should not be shorter than the length of stringValue."
    )


def test_invalid_combined() -> None:
    """Comprehensive test case that combines all possible invalid inputs.
    Validates the ability to handle multiple types of input errors simultaneously.
    """
    variables = {
        "i": {
            "stringValue": [
                [
                    ["noSpecial", "noSpecial"],
                    ["!special", "noSpecial", "!special"],
                    ["!special", "noSpecial", "!special", "#special"],
                    ["!special"],
                ],
                [
                    ["!special", "noSpecial", "!special"],
                    ["!special", "noSpecial", "!special"],
                ],
                [
                    ["!special", "!Special", "nospecial", "#special"],
                    ["!special", "noSpecial", "!special", "#special"],
                    ["nospecial", "!Special", "!special", "#special"],
                ],
            ],
            "intValue": [[1, -4, 2], [2, -3]],
        }
    }
    result = expect_validation_error(schema, valid_op, variables=variables)
    assert result["input"][0]["stringValue"] == [
        "Outer list must have at exactly 2 items.",
        [
            "Middle list must have at exactly 3 items.",
            [
                "Inner list must have at exactly 4 items.",
                [
                    "Must contain a special character.",
                    "Must contain a special character.",
                ],
                "Inner list must have at exactly 4 items.",
                [None, "Must contain a special character.", None],
                [None, "Must contain a special character.", None, None],
                "Inner list must have at exactly 4 items.",
            ],
            "Middle list must have at exactly 3 items.",
            [
                "Inner list must have at exactly 4 items.",
                [None, "Must contain a special character.", None],
                "Inner list must have at exactly 4 items.",
                [None, "Must contain a special character.", None],
            ],
            [
                [None, None, "Must contain a special character.", None],
                [None, "Must contain a special character.", None, None],
                ["Must contain a special character.", None, None, None],
            ],
        ],
    ]
    assert result["input"][0]["intValue"][0] == [
        [["Must be even."], ["Must be positive."], None],
        [None, ["Must be even.", "Must be positive."]],
    ]
    assert (
        result["input"][0][""][0]
        == "Length of intValue should not be shorter than the length of stringValue."
    )
