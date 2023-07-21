from __future__ import annotations

import itertools
import typing as t
from collections import deque

import graphql

from . import nodes
from . import scalars


class Schema:
    """A schema describes all the types and fields in a GraphQL API. Collectively, the
    objects and fields form the graph, and the remaining types define inputs and
    outputs. Unlike GraphQL-Core, Magql's schema and nodes can be modified after
    definition, before finally being converted to a GraphQL-Core schema.

    :param types: Maps names to defined type instances (objects, input objects,
        enums, and scalars). Used to provide type definitions for types that are only
        referred to by name in the graph. (forward references).
    :param description: Help text to show in the schema.
    """

    _graphql_schema: graphql.GraphQLSchema | None = None
    """Cached result of :meth:`to_graphql`."""

    def __init__(
        self,
        types: list[nodes.NamedType] | None = None,
        description: str | None = None,
    ):
        self.query: nodes.Object = nodes.Object("Query")
        """The object containing the top-level query fields."""

        self.mutation: nodes.Object = nodes.Object("Mutation")
        """The object containing the top-level mutation fields."""

        self.type_map: dict[str, nodes.NamedType | None] = {}
        """Maps names to type instances. Initially populated only with default types and
        passed in types, then filled in when calling :meth:`to_graphql`. If the types
        have only partially been defined so far, some values may be ``None``.
        """

        self.description: str | None = description
        """Help text to show in the schema."""

        if types is None:
            types = []

        # Passed in types can override magql default scalars, but nothing can override
        # graphql default scalars because they are referenced by graphql internally.
        for item in itertools.chain(
            scalars.default_scalars, types, scalars.graphql_default_scalars
        ):
            self.type_map[item.name] = item

    def add_type(self, type: nodes.NamedType) -> None:
        """Add a named type to :attr:`type_map`. Used to provide type definitions for
        types that are only referred to by name in the graph (forward references).

        :param type: The named type instance to add.
        """
        self.type_map[type.name] = type

    def _find_nodes(self) -> None:
        """Replace any type name references in the graph with the type instance, and
        collect named types in :attr:`type_map`. If a name is not defined in the graph
        or the schema, it is left as a reference in the graph, and has a value of
        ``None`` in ``type_map``.

        This requires iterating over the graph twice, once to collect all nodes and once
        to apply types. This is because a type may be defined after a reference to it
        has already been seen. It's not clear how a single iteration solution would
        work, or whether it would perform better. Performance is unlikely to be an issue
        here anyway.
        """
        type_map = self.type_map
        q: t.Deque[nodes.Node | str | None] = deque(type_map.values())
        q.append(self.query)
        q.append(self.mutation)
        seen: t.Set[nodes.Node | str] = set()

        # Breadth-first traversal of the graph to collect all nodes, starting at the
        # top-level query and mutation objects.
        while q:
            node = q.popleft()

            if node is None or node in seen:
                continue

            seen.add(node)

            if isinstance(node, str):
                # Remove non-null ! and list [] marks, handled by _apply_types below.
                while True:
                    if node[-1] == "!":
                        node = node[:-1]
                    elif node[0] == "[":
                        node = node[1:-1]
                    else:
                        break

                if node not in type_map:
                    # Record a type name with no definition.
                    type_map[node] = None

                continue

            if isinstance(node, nodes.NamedType):
                # Record a defined named type.
                type_map[node.name] = node

            # Add all nodes this one can see to the end of the queue.
            q.extend(node._find_nodes())

        # Remove the top-level query and mutation objects from the map, they can't be
        # used as types elsewhere.
        del type_map[self.query.name], type_map[self.mutation.name]

        # For each node seen, replace any type name reference with its instance. If the
        # types were fully defined, no string names will remain in the graph.
        for node in seen:
            if isinstance(node, str):
                continue

            node._apply_types(type_map)

    def to_graphql(self) -> graphql.GraphQLSchema:
        """Finalize the Magql schema by converting it and all its nodes to a
        GraphQL-Core schema. Will return the same instance each time it is called.

        Changes to the Magql schema after this is called will not be reflected in the
        GraphQL schema.

        Each GraphQL node will have a ``node.extensions["magql"]`` key with a reference
        back to the Magql node that generated it.
        """
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
            extensions={"magql_schema": self},
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
        """Execute a GraphQL operation (query or mutation). Shortcut for calling
        :meth:`to_magql` then calling :func:`graphql.graphql_sync` on the
        GraphQL schema.

        The schema from :meth:`to_magql` is cached, so calling this multiple times will
        not result in multiple compilations.

        .. code-block:: python

            s.execute(...)

            # equivalent to
            gs = s.to_graphql()
            import graphql
            graphql.graphql_sync(gs, ...)

        Only the basic arguments to ``graphql_sync`` are accepted, advanced use should
        call it directly.

        :param source: The operation (query or mutation) written in GraphQL language to
            execute on the schema.
        :param root: The parent data passed to top-level field resolvers.
        :param context: Passed to resolvers as ``info.context``. Useful for passing
            through shared resources such as a database connection or cache.
        :param variables: Maps placeholder names in the source to input values passed
            along with the request.
        :param operation: The name of the operation if the source defines multiple.
        """
        schema = self.to_graphql()
        return graphql.graphql_sync(
            schema,
            source=source,
            root_value=root,
            context_value=context,
            variable_values=variables,
            operation_name=operation,
        )

    def to_document(self) -> str:
        """Format the schema as a document in the GraphQL schema language. Shortcut for
        calling :meth:`to_magql` then calling :func:`graphql.graphql_sync`.
        """
        return graphql.print_schema(self.to_graphql())
