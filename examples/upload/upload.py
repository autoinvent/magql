from __future__ import annotations

import typing as t
from pathlib import Path

import flask_magql
from flask import Blueprint
from flask import current_app
from flask import Flask
from flask import send_file
from flask import url_for
from flask_sqlalchemy_lite import SQLAlchemy
from graphql import GraphQLResolveInfo
from magql_sqlalchemy import ModelManager
from magql_sqlalchemy.resolvers import CreateResolver
from magql_sqlalchemy.resolvers import UpdateResolver
from sqlalchemy import orm
from werkzeug import Response
from werkzeug.datastructures import FileStorage

import magql
from magql import Argument
from magql import Field

db = SQLAlchemy()
schema = magql.Schema()
magql_ext = flask_magql.MagqlExtension(schema)


class Model(orm.DeclarativeBase):
    pass


class Document(Model):
    __tablename__ = "document"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
    title: orm.Mapped[str]
    filename: orm.Mapped[str | None]
    """The original filename provided when uploading."""

    def save_file(self, file: FileStorage) -> None:
        """Given a file object from ``request.files``, store the provided
        filename and save the file to a set location and name.
        """
        self.filename = file.filename
        file.save(self.file_path)

    @property
    def file_path(self) -> Path:
        """The path to the file in the instance folder."""
        return (Path(current_app.instance_path) / "document") / f"{self.id}_file"

    @property
    def file_url(self) -> str:
        """The URL that download's this document's file."""
        return url_for("document.download", id=self.id)


document_manager = ModelManager(Document)
document_manager.register(schema)
# Add the file_url field to read the corresponding property.
document_manager.object.fields["file_url"] = Field("String!")
# Add the file argument which will hold the file data. Required for create,
# optional for update.
document_manager.create_field.args["file"] = Argument("Upload!")
document_manager.update_field.args["file"] = Argument("Upload")
# The default model resolvers that will be wrapped with extra behavior.
default_document_create = CreateResolver(Document)
default_document_update = UpdateResolver(Document)


@document_manager.create_field.resolver
def resolve_document_create(
    parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any
) -> Document:
    """Create the document in the database and save the file."""
    # Remove file from args, it will be handled separately.
    file: FileStorage = kwargs.pop("file")
    # Create the document in the database.
    doc: Document = default_document_create(parent, info, **kwargs)
    # Save the file using the created document.
    doc.save_file(file)
    db.session.commit()
    return doc


@document_manager.update_field.resolver
def resolve_document_update(
    parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any
) -> Document:
    """Update the document in the database, optional save a new file."""
    file: FileStorage | None = kwargs.pop("file", None)
    doc: Document = default_document_update(parent, info, **kwargs)

    # File is optional, may just be updating the title or filename.
    if file is not None:
        doc.save_file(file)
        db.session.commit()

    return doc


bp = Blueprint("document", __name__, url_prefix="/document")


@bp.route("/download/<int:id>")
def download(id: int) -> Response:
    doc = db.session.get(Document, id)
    return send_file(doc.file_path, download_name=doc.filename, as_attachment=True)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_ENGINES"] = {"default": "sqlite:///upload.sqlite"}
    # Create the instance folder and document folder for saving files.
    (Path(current_app.instance_path) / "document").mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    magql_ext.init_app(app)
    app.register_blueprint(bp)

    with app.app_context():
        Model.metadata.create_all(db.engine)

    return app
