from __future__ import annotations

import dataclasses
import typing as t

from graphql import GraphQLResolveInfo

from . import nodes
from . import scalars
from .schema import Schema
from .search import search_result
from .search import SearchResult


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


check_delete_result: nodes.Object = nodes.Object(
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

.. code-block:: text

    type CheckDeleteResult {
        affected: [SearchResult!]!
        deleted: [SearchResult!]!
        prevented: [SearchResult!]!
    }
"""


class BaseCheckDelete:
    """Base class for implementations of the ``check_delete`` query.

    Query field and resolver that shows what would be affected by deleting a row,
    without actually deleting it. Rather than creating a separate query per model, this
    is a generic API using the model name and id.

    The resolver returns :class:`.CheckDeleteResult`, which is a collection of
    :class:`.SearchResult` items.

    -   Affected - Items that will have references to the deleted item removed, such as
        many-to-many or nullable foreign keys.
    -   Deleted - Items that will be deleted along with the deleted item.
    -   Prevented - Items that will not be deleted or have references removed prevent
        the item from being deleted.

    This shouldn't need to be created directly, it's implemented and managed by a
    specific data source integration.

    :param field_name: The name to use for this field in the top-level query object.
    """

    def __init__(self, field_name: str = "check_delete") -> None:
        self.field: nodes.Field = nodes.Field(
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

        .. code-block:: text

            type Query {
                check_delete(type: String!, id: ID!): CheckDeleteResult!
            }
        """

        self.field_name: str = field_name
        """The name to use for this field in the top-level query object."""

    def _validate_type(self, info: GraphQLResolveInfo, value: str, data: t.Any) -> None:
        """Validate that the ``type`` argument is a known type that can be checked."""
        raise NotImplementedError

    def __call__(
        self, parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any
    ) -> CheckDeleteResult:
        raise NotImplementedError

    def register(self, schema: Schema) -> None:
        """Register the field on the given :class:`.Search` instance.

        :param schema: The schema instance to register on.
        """
        schema.query.fields[self.field_name] = self.field
