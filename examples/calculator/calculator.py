from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import flask_magql
from flask import Flask
from graphql import GraphQLResolveInfo

import magql

schema = magql.Schema()


@dataclass
class Result:
    v: float


@schema.query.field("start", "Result!", args={"v": magql.Argument("Float!", default=0)})
def resolve_start(parent: None, info: GraphQLResolveInfo, **kwargs: Any) -> Result:
    return Result(kwargs["v"])


result_object = magql.Object("Result", fields={"v": "Float!"})
schema.add_type(result_object)


@result_object.field("add", "Result!", args={"v": "Float!"})
def resolve_add(parent: Result, info: GraphQLResolveInfo, **kwargs: Any) -> Result:
    return Result(parent.v + kwargs["v"])


@result_object.field("sub", "Result!", args={"v": "Float!"})
def resolve_sub(parent: Result, info: GraphQLResolveInfo, **kwargs: Any) -> Result:
    return Result(parent.v - kwargs["v"])


@result_object.field("mul", "Result!", args={"v": "Float!"})
def resolve_mul(parent: Result, info: GraphQLResolveInfo, **kwargs: Any) -> Result:
    return Result(parent.v * kwargs["v"])


@result_object.field("div", "Result!", args={"v": "Float!"})
def resolve_div(parent: Result, info: GraphQLResolveInfo, **kwargs: Any) -> Result:
    return Result(parent.v / kwargs["v"])


@result_object.field("mod", "Result!", args={"v": "Float!"})
def resolve_mod(parent: Result, info: GraphQLResolveInfo, **kwargs: Any) -> Result:
    return Result(parent.v % kwargs["v"])


magql_ext = flask_magql.MagqlExtension(schema)


def create_app() -> Flask:
    app = Flask(__name__)
    magql_ext.init_app(app)
    return app
