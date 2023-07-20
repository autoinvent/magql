API
===

Anything documented here is part of the public API that Magql provides, unless otherwise
indicated. Anything not documented here is considered internal or private and may change
at any time.


Schema
------

```{eval-rst}
.. currentmodule:: magql.schema
.. autoclass:: Schema
```


Nodes
-----

```{eval-rst}
.. currentmodule:: magql.nodes
.. autoclass:: Object
.. autoclass:: Field
.. autoclass:: Argument
.. autoclass:: Interface
.. autoclass:: Union
.. autoclass:: InputObject
.. autoclass:: InputField
.. autoclass:: NonNull
.. autoclass:: List
.. autoclass:: Enum
.. autoclass:: Scalar
```


GraphQL Scalars
---------------

GraphQL-Core provides implementations for the 5 built-in scalar types in the GraphQL
spec. They are already used by GraphQL's built-in introspection queries, and so must be
patched by Magql rather than overridden.

```{eval-rst}
.. currentmodule:: magql.scalars
.. autodata:: String
.. autodata:: Int
.. autodata:: Float
.. autodata:: Boolean
.. autodata:: ID
```


Magql Scalars
-------------

Extra scalar types that are not provided by GraphQL-Core.

```{eval-rst}
.. currentmodule:: magql.scalars
.. autodata:: DateTime
.. autodata:: JSON
.. autodata:: Upload
```


Resolvers
---------

```{eval-rst}
.. currentmodule:: magql.nodes
.. autofunction:: resolve_attr
.. autofunction:: resolve_item
```


Validators
----------

```{eval-rst}
.. currentmodule:: magql.validators
.. autoexception:: ValidationError
    :no-inherited-members:
```


Data Source Base API
--------------------

This API is typically implemented and managed by a data source integration.

```{eval-rst}
.. currentmodule:: magql.search
.. autoclass:: Search
.. autoclass:: SearchResult
.. autodata:: search_result

.. currentmodule:: magql.check_delete
.. autoclass:: BaseCheckDelete
.. autoclass:: CheckDeleteResult
.. autodata:: check_delete_result

.. currentmodule:: magql.filters
.. autodata:: filter_item
```
