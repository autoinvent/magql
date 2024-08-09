from __future__ import annotations

import typing as t
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import graphql
import pytest

from magql import DateTime


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


@pytest.mark.parametrize(
    ("value", "expect"),
    [
        (datetime(2024, 8, 9), "2024-08-09T00:00:00+00:00"),
        (datetime(2024, 8, 9, tzinfo=timezone.utc), "2024-08-09T00:00:00+00:00"),
        (
            datetime(2024, 8, 9, tzinfo=timezone(timedelta(hours=-8))),
            "2024-08-09T00:00:00-08:00",
        ),
    ],
)
def test_serialize_datetime(value: datetime, expect: str) -> None:
    assert DateTime.serialize(value) == expect


@pytest.mark.parametrize(
    ("value", "expect"),
    [
        ("2024-08-09", datetime(2024, 8, 9, tzinfo=timezone.utc)),
        ("2024-08-09T00:00:00+00:00", datetime(2024, 8, 9, tzinfo=timezone.utc)),
        (
            "2024-08-09T00:00:00-08:00",
            datetime(2024, 8, 9, tzinfo=timezone(timedelta(hours=-8))),
        ),
        ("bad", None),
    ],
)
def test_parse_datetime(value: datetime, expect: str | None) -> None:
    if expect is None:
        with pytest.raises(graphql.GraphQLError, match=""):
            DateTime.parse_value(value)
    else:
        assert DateTime.parse_value(value) == expect
