from __future__ import annotations

import dataclasses
import typing as t

from graphql import GraphQLResolveInfo

from . import nodes
from . import scalars
from .schema import Schema


@dataclasses.dataclass()
class SearchResult:
    type: str
    id: t.Any
    value: str
    extra: dict[str, t.Any] | None = None


class SearchProvider(t.Protocol):
    def __call__(self, context: t.Any, value: str) -> list[SearchResult]:
        ...


_SearchProvider = t.TypeVar("_SearchProvider", bound=SearchProvider)


class Search:
    def __init__(
        self,
        providers: list[SearchProvider] | None = None,
        field_name: str = "search",
    ) -> None:
        if providers is None:
            providers = []

        self.providers: list[SearchProvider] = providers
        self.field = nodes.Field(
            search_result.non_null.list.non_null,
            args={"value": nodes.Argument(scalars.String.non_null)},
            resolve=self,
        )
        self.field_name = field_name

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
        self.providers.append(f)
        return f

    def register(self, schema: Schema) -> None:
        if self.providers:
            schema.query.fields[self.field_name] = self.field


search_result = nodes.Object(
    "SearchResult",
    fields={
        "type": scalars.String.non_null,
        "id": scalars.ID.non_null,
        "value": scalars.String.non_null,
        "extra": scalars.JSON,
    },
)
