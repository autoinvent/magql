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

String = Scalar("String")
String._graphql_node = graphql.GraphQLString


def parse_int(value: t.Any) -> t.Any:
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            pass

    return graphql.GraphQLInt.parse_value(value)


Int = Scalar("Int")
Int._graphql_node = graphql.GraphQLInt
graphql.GraphQLInt.parse_value = parse_int


def parse_float(value: t.Any) -> t.Any:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            pass

    return graphql.GraphQLFloat.parse_value(value)


Float = Scalar("Float")
Float._graphql_node = graphql.GraphQLFloat
graphql.GraphQLFloat.parse_value = parse_float


def parse_boolean(value: t.Any) -> t.Any:
    if isinstance(value, str):
        v = value.lower()

        if v in {"1", "on", "true"}:
            value = True
        elif v in {"0", "off", "false"}:
            value = False

    return graphql.GraphQLBoolean.parse_value(value)


Boolean = Scalar("Boolean")
Boolean._graphql_node = graphql.GraphQLBoolean
graphql.GraphQLBoolean.parse_value = parse_boolean

ID = Scalar("ID")
ID._graphql_node = graphql.GraphQLID

graphql_default_scalars = [String, Int, Float, Boolean, ID]

# magql provided scalars


def parse_datetime(value: str) -> datetime:
    try:
        out = isoparse(value)
    except (TypeError, ValueError) as e:
        raise graphql.GraphQLError(f"'{value}' is not a valid DateTime.") from e

    if out.tzinfo is None:
        return out.replace(tzinfo=timezone.utc)

    return out


DateTime = Scalar(
    "DateTime",
    serialize=datetime.isoformat,
    parse_value=parse_datetime,
    description="A date and time in ISO 8601 format.",
    specified_by="ISO 8601",
)

JSON = Scalar(
    "JSON",
    description=(
        "A raw JSON value. The inner shape of the object is not specified by or queried"
        " through the GraphQL schema."
    ),
)

Upload = Scalar(
    "Upload",
    description=(
        "An uploaded file, provided alongside the GraphQL request. Should only be used"
        " as an input type."
    ),
    specified_by="https://github.com/jaydenseric/graphql-multipart-request-spec",
)

default_scalars = [DateTime, JSON, Upload]
