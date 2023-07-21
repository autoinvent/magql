Magql
=====

Magql is a [GraphQL][] framework for Python. It's pronounced "magical", and it is!

Magql wraps the [GraphQL-Core][] library to make it easier to work with. Magql
provides three big features over GraphQL-Core:

-   The schema is mutable. It can be defined (or generated) then modified to
    add/remove/change behavior before finalizing.
-   Types can be referenced by name, rather than using large lambda functions to
    resolve forward references.
-   Robust input validation can be applied anywhere in arbitrary input
    structures, and errors in the result can be matched back to those arbitrary
    locations.

[GraphQL]: https://graphql.org
[GraphQL-Core]: https://graphql-core-3.readthedocs.io
