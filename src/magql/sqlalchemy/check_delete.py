from __future__ import annotations

import dataclasses
import typing as t

import sqlalchemy as sa
import sqlalchemy.orm as sa_orm
from graphql import GraphQLResolveInfo

from ..core import nodes
from ..core import scalars
from ..core.schema import Schema
from ..core.search import search_result
from ..core.search import SearchResult
from ..validators import ValidationError

if t.TYPE_CHECKING:
    from .manager import ModelManager


@dataclasses.dataclass()
class CheckDeleteResult:
    """The value returned by the :class:`CheckDelete` resolver.
    :data:`check_delete_result` is the Magql type corresponding to this Python type.

    The items in each list are :class:`.SearchResult`, so that UI behavior can be shared
    between :class:`CheckDelete` and :class:`.Search`.
    """

    affected: list[SearchResult] = dataclasses.field(default_factory=list)
    """Items that will have references to the deleted item removed, such as many-to-many
    or nullable foreign keys.
    """

    deleted: list[SearchResult] = dataclasses.field(default_factory=list)
    """Items that will be deleted along with the deleted item."""

    prevented: list[SearchResult] = dataclasses.field(default_factory=list)
    """Items that will not be deleted or have references removed prevent the item from
    being deleted.
    """


class CheckDelete:
    """Query field and resolver that shows what would be affected by deleting a row,
    without actually deleting it. Rather than creating a separate query per model, this
    is a generic API using the model name and id.

    The resolver returns :class:`CheckDeleteResult`, which is a collection of
    :class:`.SearchResult` items.

    -   Affected - Items that will have references to the deleted item removed, such as
        many-to-many or nullable foreign keys.
    -   Deleted - Items that will be deleted along with the deleted item.
    -   Prevented - Items that will not be deleted or have references removed prevent
        the item from being deleted.

    This shouldn't need to be created directly, it's managed by :class:`.ModelGroup`.

    :param managers: Maps model names to managers.
    :param field_name: The name to use for this field in the top-level query object.
    """

    def __init__(
        self, managers: dict[str, ModelManager], field_name: str = "check_delete"
    ) -> None:
        self.managers = managers
        """Maps model names to managers. These are the models that can be checked."""

        self.field = nodes.Field(
            check_delete_result,
            args={
                "type": nodes.Argument(
                    scalars.String.non_null, validators=[self._validate_type]
                ),
                "id": nodes.Argument(scalars.ID.non_null),
            },
            resolve=self,
        )
        """The query field.

        .. code-block:: graphql

            type Query {
                check_delete(type: String!, id: ID!): CheckDeleteResult!
            }
        """

        self.field_name = field_name
        """The name to use for this field in the top-level query object."""

    def _validate_type(self, info: GraphQLResolveInfo, value: str, data: t.Any) -> None:
        if value not in self.managers:
            raise ValidationError(f"Unknown type '{value}'.")

    def __call__(
        self, parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any
    ) -> CheckDeleteResult:
        session: sa_orm.Session = info.context
        model = self.managers[kwargs["type"]].model
        item = session.get(model, kwargs["id"])
        mapper: sa_orm.Mapper = sa_orm.object_mapper(item)
        rel: sa_orm.RelationshipProperty
        result = CheckDeleteResult()

        for key, rel in mapper.relationships.items():
            value = getattr(item, key)

            if rel.direction is sa_orm.MANYTOONE:
                if value is None:
                    continue

                result.affected.append(
                    SearchResult(
                        type=rel.entity.class_.__name__,
                        id=sa.inspect(value).identity[0],
                        value=str(value),
                    )
                )
            else:
                if len(value) == 0:
                    continue

                # could be a dict collection instead of a list
                if isinstance(value, dict):
                    value = value.values()

                if "delete" in rel.cascade:
                    # children will be deleted with the parent
                    action = result.deleted
                elif rel.direction is sa_orm.ONETOMANY and not all(
                    c.nullable for c in rel.remote_side
                ):
                    # remote foreign key is not nullable, preventing deletion
                    action = result.prevented
                else:
                    # children will be disassociated from the parent
                    action = result.affected

                target_name = rel.entity.class_.__name__
                action.extend(
                    SearchResult(
                        type=target_name,
                        id=sa.inspect(item).identity[0],
                        value=str(item),
                    )
                    for item in value
                )

        return result

    def register(self, schema: Schema) -> None:
        schema.query.fields[self.field_name] = self.field


check_delete_result = nodes.Object(
    "CheckDeleteResult",
    fields={
        "affected": search_result.non_null.list.non_null,
        "deleted": search_result.non_null.list.non_null,
        "prevented": search_result.non_null.list.non_null,
    },
)
"""The result type for the :class:`CheckDelete` query. :class:`CheckDeleteResult` is the
Python type corresponding to this Magql type.

The items in each list are :class:`.search_result`.

.. code-block:: graphql

    type CheckDeleteResult {
        affected: [SearchResult!]!
        deleted: [SearchResult!]!
        prevented: [SearchResult!]!
    }
"""
