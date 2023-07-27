from __future__ import annotations

import typing as t
from datetime import datetime
from datetime import timezone

import graphql
from dateutil.parser import isoparse

from .nodes import Scalar

# Can't replace graphql default scalars, as they are already referenced by directives
# and introspection types. Instead, mutate them in place and set up magql scalars to
# reference them.

String: Scalar = Scalar("String")
"""Built-in GraphQL ``String`` type."""
String._graphql_node = graphql.GraphQLString


def parse_int(value: t.Any) -> t.Any:
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            pass

    return _original_parse_int(value)


Int: Scalar = Scalar("Int")
"""Built-in GraphQL ``Int`` type. Extends GraphQL-Core implementation to accept string
values. Strings are common when using HTML forms.
"""
Int._graphql_node = graphql.GraphQLInt
_original_parse_int = graphql.GraphQLInt.parse_value
graphql.GraphQLInt.parse_value = parse_int  # type: ignore[method-assign]


def parse_float(value: t.Any) -> t.Any:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            pass

    return _original_parse_float(value)


Float: Scalar = Scalar("Float")
"""Built-in GraphQL ``Float`` type. Extends GraphQL-Core implementation to accept string
values. Strings are common when using HTML forms.
"""
Float._graphql_node = graphql.GraphQLFloat
_original_parse_float = graphql.GraphQLFloat.parse_value
graphql.GraphQLFloat.parse_value = parse_float  # type: ignore[method-assign]


def parse_boolean(value: t.Any) -> t.Any:
    if isinstance(value, str):
        v = value.lower()

        if v in {"1", "on", "true"}:
            value = True
        elif v in {"0", "off", "false"}:
            value = False

    return _original_parse_boolean(value)


Boolean: Scalar = Scalar("Boolean")
"""Built-in GraphQL ``Boolean`` type. Extends GraphQL-Core implementation to accept
common case-insensitive string values; 1, on, true; 0, off, false. In particular, HTML
forms send "on".
"""
Boolean._graphql_node = graphql.GraphQLBoolean
_original_parse_boolean = graphql.GraphQLBoolean.parse_value
graphql.GraphQLBoolean.parse_value = parse_boolean  # type: ignore[method-assign]

ID: Scalar = Scalar("ID")
"""Built-in GraphQL ``ID`` type. Accepts strings, ints, and floats, converting them all
to strings.
"""
ID._graphql_node = graphql.GraphQLID

graphql_default_scalars: list[Scalar] = [String, Int, Float, Boolean, ID]

# magql provided scalars


def parse_datetime(value: str) -> datetime:
    try:
        out = isoparse(value)
    except (TypeError, ValueError) as e:
        raise graphql.GraphQLError(f"'{value}' is not a valid DateTime.") from e

    if out.tzinfo is None:
        return out.replace(tzinfo=timezone.utc)

    return out


DateTime: Scalar = Scalar(
    "DateTime",
    serialize=datetime.isoformat,
    parse_value=parse_datetime,
    description="A date, time, and timezone in ISO 8601 format.",
    specified_by="ISO 8601",
)
"""Date, time, and timezone in ISO 8601 format. Uses dateutil's ``isoparse``. Input
without a timezone is assumed to be UTC. Always returns a timezone-aware
:class:`~datetime.DateTime` value.
"""

JSON: Scalar = Scalar(
    "JSON",
    description=(
        "A raw JSON value. The inner shape of the object is not specified by or queried"
        " through the GraphQL schema."
    ),
)
"""A raw JSON value. The inner shape of the object is not specified by or queried
through the GraphQL schema. Useful for large blobs of opaque data, such as GeoJSON.
"""

Upload: Scalar = Scalar(
    "Upload",
    description=(
        "An uploaded file, provided alongside the GraphQL request. Should only be used"
        " as an input type."
    ),
    specified_by="https://github.com/jaydenseric/graphql-multipart-request-spec",
)
"""An uploaded file, provided alongside the GraphQL request. Should only be used as an
input type. See https://github.com/jaydenseric/graphql-multipart-request-spec. The spec
is implemented by Magql's Flask integration.
"""

default_scalars: list[Scalar] = [DateTime, JSON, Upload]
