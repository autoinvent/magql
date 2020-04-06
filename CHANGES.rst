v0.5.0
------

Unreleased

v0.4.1
------

Released 2020-04-06

-   Return None, not error, in single queries with no row found :pr:`52`


v0.4.0
------

Released 2020-04-02

-   Add pagination support. :pr:`20`
-   Add ``AuthorizationError`` and remove ``PermissionsError``.
    :issue:`23`
-   Add ``ListPayload`` type for list return types. :pr:`15`
-   Remove ``Resolver`` superclass on non-CRUD resolvers. :pr:`15`
-   Fix bug where queries returned none caused by upgrading return type.
    :pr:`10`
-   Remove unused marshmallow-sqlalchemy dependency. :pr:`6`
-   Update and set minimum version for some dependencies :pr:`6`
-   ``singledispatch`` functions raise ``TypeError`` if no handler is
    registered for a type. :issue:`40`
-   ``Manager.manager_map`` uses table names instead of tables as keys.
    :issue:`24`


v0.3.0
------

Released 2020-02-13

-   Initial public version.
