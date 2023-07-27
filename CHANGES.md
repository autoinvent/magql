Version 1.0.1
-------------

Released 2023-07-26

-   Built-in scalar method overrides do not cause recursion. {issue}`88`


Version 1.0.0
-------------

Released 2023-07-24

-   Complete rewrite. {pr}`74`


Version 0.7.0
-------------

Released 2022-08-23

-   `INCLUDES` and `EQUALS` filters are case-insensitive.


Version 0.6.0
-------------

Released 2021-07-22

-   Add static typing annotations.
-   Add validation helpers.


Version 0.5.0
-------------

Released 2021-05-28

-   Add `EXISTS` and `DOESNOTEXIST` string operators for filtering.
-   Change ids to use ID graphql scalar type.


Version 0.4.1
-------------

Released 2020-04-06

-   Return `None`, not error, in single queries with no row found.


Version 0.4.0
-------------

Released 2020-04-02

-   Add pagination support.
-   Add `AuthorizationError` and remove `PermissionsError`.
-   Add `ListPayload` type for list return types.
-   Remove `Resolver` superclass on non-CRUD resolvers.
-   Fix bug where queries returned none caused by upgrading return type.
-   Remove unused marshmallow-sqlalchemy dependency.
-   Update and set minimum version for some dependencies.
-   `singledispatch` functions raise `TypeError` if no handler is registered for
    a type.
-   `Manager.manager_map` uses table names instead of tables as keys.


Version 0.3.0
-------------

Released 2020-02-13

-   Initial public version.
