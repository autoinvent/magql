v0.4.0
------

Unreleased

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


v0.3.0
------

Released 2020-02-13

-   Initial public version.
