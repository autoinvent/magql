from __future__ import annotations

import dataclasses
import typing as t

from graphql import GraphQLResolveInfo

from . import nodes
from . import scalars
from .schema import Schema


@dataclasses.dataclass()
class SearchResult:
    """The :class:`.Search`, and :class:`Search` provider functions, must return a list
    of these values. :data:`search_result` is the Magql type corresponding to this
    Python type.

    A UI should be able to link to a given result by its type and id.
    """

    type: str
    """The model name."""

    id: t.Any
    """The row id."""

    value: str
    """The value to display as the result."""

    extra: dict[str, t.Any] | None = None
    """Arbitrary extra data about the result."""


class SearchProvider(t.Protocol):
    """The signature that all search provider functions must have."""

    def __call__(self, context: t.Any, value: str) -> list[SearchResult]:
        ...


_SearchProvider = t.TypeVar("_SearchProvider", bound=SearchProvider)


class Search:
    """Query field and resolver that performs a global search and returns results for
    any object type. This is handled generically by registering a list of provider
    functions. Each function is called with the search term, combining all results.

    The resolver returns a list of :class:`SearchResult` items.

    :param providers: List of search provider functions.
    :param field_name: The name to use for this field in the top-level query object.
    """

    def __init__(
        self,
        providers: list[SearchProvider] | None = None,
        field_name: str = "search",
    ) -> None:
        if providers is None:
            providers = []

        self.providers: list[SearchProvider] = providers

        self.field: nodes.Field = nodes.Field(
            search_result.non_null.list.non_null,
            args={"value": nodes.Argument(scalars.String.non_null)},
            resolve=self,
        )
        """The query field.

        .. code-block:: text

            type Query {
                search(value: String!): [SearchResult!]!
            }
        """

        self.field_name: str = field_name
        """The name to use for this field in the top-level query object."""

    def __call__(
        self, parent: t.Any, info: GraphQLResolveInfo, **kwargs: t.Any
    ) -> list[SearchResult]:
        context = info.context
        value = kwargs["value"]
        out = []

        for f in self.providers:
            out.extend(f(context, value))

        return out

    def provider(self, f: _SearchProvider) -> _SearchProvider:
        """Decorate a function to append to the list of providers."""
        self.providers.append(f)
        return f

    def register(self, schema: Schema) -> None:
        """If at least one search provider is registered, register the field on the
        given :class:`.Search` instance.

        :param schema: The schema instance to register on.
        """
        if self.providers:
            schema.query.fields[self.field_name] = self.field


search_result: nodes.Object = nodes.Object(
    "SearchResult",
    fields={
        "type": scalars.String.non_null,
        "id": scalars.ID.non_null,
        "value": scalars.String.non_null,
        "extra": scalars.JSON,
    },
)
"""The result type for the :class:`.Search` query. :class:`SearchResult` is the Python
type corresponding to this Magql type.

.. code-block:: text

    type SearchResult {
        type: String!
        id: ID!
        value: String!
        extra: JSON
    }
"""
