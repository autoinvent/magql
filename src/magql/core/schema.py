from __future__ import annotations

import itertools
import typing as t
from collections import deque

import graphql

from . import nodes
from . import scalars


class Schema:
    _graphql_schema: graphql.GraphQLSchema | None = None

    def __init__(
        self,
        types: list[nodes.NamedType] | None = None,
        description: str | None = None,
    ):
        self.query = nodes.Object("Query")
        self.mutation = nodes.Object("Mutation")
        self.type_map: dict[str, nodes.NamedType | None] = {}
        self.description = description

        if types is None:
            types = []

        # Passed in types can override magql default scalars, but nothing can override
        # graphql default scalars because they are referenced by graphql internally.
        for item in itertools.chain(
            scalars.default_scalars, types, scalars.graphql_default_scalars
        ):
            self.type_map[item.name] = item

    def add_type(self, type: nodes.NamedType) -> None:
        self.type_map[type.name] = type

    def _find_nodes(self) -> None:
        """Replace any type name references in the graph with the type object, and
        collect named types in :attr:`type_map`. If a name is not defined in the graph
        or the schema, it is left as a reference in the graph, and has a value of none
        in ``type_map``.

        This requires iterating over the graph twice, once to collect the types and once
        to apply them. This is because a type may be defined after a reference to it has
        already been seen. It's not clear how a single iteration solution would work, or
        whether it would perform better. Performance is unlikely to be an issue here
        anyway.
        """
        type_map = self.type_map
        q: t.Deque[nodes.Type] = deque(type_map.values())
        q.append(self.query)
        q.append(self.mutation)
        seen: t.Set[nodes.Node] = set()

        while q:
            type = q.popleft()

            if type is None or type in seen:
                continue

            seen.add(type)

            if isinstance(type, str):
                if type not in type_map:
                    type_map[type] = None

                continue

            if isinstance(type, nodes.NamedType):
                type_map[type.name] = type

            q.extend(type._find_nodes())

        del type_map[self.query.name], type_map[self.mutation.name]

        for node in (n for n in seen if not isinstance(n, str)):
            node._apply_types(type_map)

    def to_graphql(self) -> graphql.GraphQLSchema:
        if self._graphql_schema is not None:
            return self._graphql_schema

        self._find_nodes()
        unmapped = sorted(k for k, v in self.type_map.items() if v is None)

        if unmapped:
            names = ", ".join(f"'{name}'" for name in unmapped)
            raise KeyError(
                f"Could not find definitions for the following type names: {names}. All"
                " types must be defined somewhere in the graph, or passed when creating"
                " the Schema."
            )

        query = None
        mutation = None

        if self.query.fields:
            query = self.query._to_graphql()

        if self.mutation.fields:
            mutation = self.mutation._to_graphql()

        self._graphql_schema = schema = graphql.GraphQLSchema(
            query=query,
            mutation=mutation,
            description=self.description,
        )
        return schema

    def execute(
        self,
        source: str | graphql.Source,
        root: t.Any = None,
        context: t.Any = None,
        variables: dict[str, t.Any] | None = None,
        operation: str | None = None,
    ) -> graphql.ExecutionResult:
        schema = self.to_graphql()
        return graphql.graphql_sync(
            schema,
            source=source,
            root_value=root,
            context_value=context,
            variable_values=variables,
            operation_name=operation,
        )
