from __future__ import annotations

from datetime import datetime
from datetime import timezone

import flask_magql
import magql_sqlalchemy
import sqlalchemy as sa
import sqlalchemy.orm as sa_orm
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

import magql


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


db = SQLAlchemy()


class User(db.Model):
    id = sa.Column(sa.Integer, primary_key=True)
    username = sa.Column(sa.String, unique=True)
    tasks = sa_orm.relationship("Task", back_populates="user")


class Task(db.Model):
    id = sa.Column(sa.Integer, primary_key=True)
    message = sa.Column(sa.String, nullable=False)
    user_id = sa.Column(sa.ForeignKey("user.id"))
    user = sa_orm.relationship(User, back_populates="tasks")
    created_at = sa.Column(sa.DateTime, nullable=False, default=now_utc)
    done_at = sa.Column(sa.DateTime)

    @property
    def done(self) -> bool:
        return self.done_at is not None

    @done.setter
    def done(self, value: bool) -> None:
        if value:
            self.done_at = datetime.now(timezone.utc)
        else:
            self.done_at = None


schema = magql.Schema()
model_group = magql_sqlalchemy.ModelGroup.from_declarative_base(db.Model)

task_manager = model_group.managers["Task"]
task_manager.object.fields["done"] = magql.Field("Boolean!")
del task_manager.create_field.args["created_at"]
del task_manager.create_field.args["done_at"]
del task_manager.update_field.args["done_at"]
task_manager.update_field.args["done"] = magql.Argument("Boolean")

model_group.register(schema)
magql_ext = flask_magql.MagqlExtension(schema)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tasks.db"
    db.init_app(app)
    magql_ext.init_app(app)

    with app.app_context():
        db.create_all()

    return app
