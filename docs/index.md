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

Check out these integrations that make building an API easy:

-   [Magql-SQLAlchemy][] creates a full-featured API from SQLAlchemy models.
-   [Flask-Magql][] serves a Magql GraphQL schema and API using Flask.

Magql is the core library, and other integrations can be built around it as
well. If you use a different data source or web app framework, or something else
with GraphQL, we're happy to help you create an integration and grow our
ecosystem.

[GraphQL]: https://graphql.org
[GraphQL-Core]: https://graphql-core-3.readthedocs.io
[Magql-SQLAlchemy]: https://magql-sqlalchemy.autoinvent.dev
[Flask-Magql]: https://flask-magql.autoinvent.dev

```{toctree}
:hidden:

start
references
resolvers
validation
scalars
api
changes
license
```
