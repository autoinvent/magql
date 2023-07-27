from __future__ import annotations

import typing as t

import graphql
import pytest


@pytest.mark.parametrize(("value", "expect"), [(1, 1), (-1, -1), ("1", 1), ("-1", -1)])
def test_parse_int(value: t.Any, expect: int) -> None:
    assert graphql.GraphQLInt.parse_value(value) == expect


@pytest.mark.parametrize(
    ("value", "expect"), [(1.0, 1.0), (-1.0, -1.0), ("1.0", 1.0), ("-1.0", -1.0)]
)
def test_parse_float(value: t.Any, expect: int) -> None:
    assert graphql.GraphQLFloat.parse_value(value) == expect


@pytest.mark.parametrize(
    ("value", "expect"),
    [
        (True, True),
        (False, False),
        ("1", True),
        ("0", False),
        ("on", True),
        ("Off", False),
        ("true", True),
        ("False", False),
    ],
)
def test_parse_boolean(value: t.Any, expect: int) -> None:
    assert graphql.GraphQLBoolean.parse_value(value) == expect
