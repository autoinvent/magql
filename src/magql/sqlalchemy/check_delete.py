from __future__ import annotations

import typing as t

import sqlalchemy as sa
import sqlalchemy.orm as sa_orm
from graphql import GraphQLResolveInfo

from ..check_delete import BaseCheckDelete
from ..check_delete import CheckDeleteResult
from ..search import SearchResult
from ..validators import ValidationError

if t.TYPE_CHECKING:
    from .manager import ModelManager


class CheckDelete(BaseCheckDelete):
    """Query field and resolver that shows what would be affected by deleting a row,
    without actually deleting it. Rather than creating a separate query per model, this
    is a generic API using the model name and id.

    The resolver returns :class:`.CheckDeleteResult`, which is a collection of
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
        super().__init__(field_name=field_name)

        self.managers = managers
        """Maps model names to managers. These are the models that can be checked."""

    def _validate_type(self, info: GraphQLResolveInfo, value: str, data: t.Any) -> None:
        if value not in self.managers:
            raise ValidationError(f"Unknown type '{value}'.")

    def __call__(
        self, parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any
    ) -> CheckDeleteResult:
        session: sa_orm.Session = info.context
        model = self.managers[kwargs["type"]].model
        item = session.get(model, kwargs["id"])
        mapper: sa_orm.Mapper[t.Any] = sa_orm.object_mapper(item)
        rel: sa_orm.RelationshipProperty[t.Any]
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
