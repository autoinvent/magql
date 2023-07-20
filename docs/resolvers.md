Resolvers
=========

```{currentmodule} magql.nodes
```

Every {class}`Field` has a resolver function that is called to get the output
value for the field. This can be simple, like accessing an attribute by name
(the default), or can be something more complex like a computation, database
call, or even a request to another API.


Signature
---------

Each resolver callable must take the same three arguments. The resolver must
return data that matches (or can be coerced by) the field's type.

-   `parent` - The object that was resolved to get to this field. For example
    the parent of a `username` field might be an instance of a `User` class.
-   `info` - The {class}`~graphql.type.GraphQLResolveInfo` that describes the
    current operation. This has an attribute `context` that can be used to store
    arbitrary data, which can be useful for passing around a shared database
    connection or cache.
-   `**kwargs` - The values passed for any arguments on the field. By the time
    the resolver is called, GraphQL-Core will have checked the type and non-null
    of each argument, and Magql will have run {doc}`validation`. You can write
    out individual argument names instead of `**`, but static type checking
    tools may not handle that correctly.

The resolver can raise {exc}`.ValidationError` to show an error in the result
instead of data. You'll typically want to use the full validation system
described below and at {doc}`validation` instead of writing it all in the
resolver.


Specifying a Resolver
---------------------

There are a few different ways to define a {class}`Field` with its resolver. A
default resolver is used if none is given, described in the next section.

When creating the field, a resolver callable can be passed as the `resolve`
parameter.

```python
import magql

def resolve_greet(parent, info, **kwargs):
    return "Hello, World!"

field = magql.Field("String", resolve=resolve_greet)
```

If the field was already defined, you can assign a new resolver by decorating
the function with {meth}`Field.resolver` (or passing the function to it).

```python
import magql

field = magql.Field("String")

@field.resolver
def resolve_greet(parent, info, **kwargs):
    return "Hello, World!"

# or
field.resolver(resolve_greet)
```

If you have an {class}`Object` defined, you can decorate a resolver with
{meth}`Object.field` to add a field and its resolver simultaneously.

```python
import magql

User = magql.Object("User")

@User.field("greet", "String")
def resolve_user_greet(parent, info, **kwargs):
    return f"Hello, {parent.username}!"
```


Default Resolver
----------------

If you don't specify the resolver for a field, the default resolver
{func}`resolve_attr` accesses the attribute with the same name as the field
from the parent object, like `getattr(parent, field_name)`. If instead of
objects your data is dicts, you can specify {func}`resolve_item` instead,
which does `parent[field_name]`.

This default is much simpler than the one provided by GraphQL-Core. Core's
default will try the attribute, fall back to the item, then check if the value
is callable and call it if so. While trying multiple ways is convenient if you
have mixed data, Magql assumes you're more likely to be working with dataclasses
or database models, and that those classes were written without GraphQL in mind
so their methods don't act like resolvers.


Input Validation
----------------

Magql provides a robust input validation system beyond what GraphQL specifies.
When resolving a field, Magql will run any registered validators for the field
and its input structure before calling the field's resolver. If validation
fails, the resolver will not be called, and an error will be shown in the
result.

See {doc}`validation`.


Running Code Before Resolving
-----------------------------

You may want to run some code before the validators or resolvers. Some use cases
include keeping an audit log of queries, and checking authorization before
processing or querying any data. In this case, you can add a "pre-resolve"
function to the field. This takes the same arguments as a resolver callable
(described above), but does not return a value. It may raise
{exc}`.ValidationError` to stop resolving early.

```python
import logging
import magql

logger = logging.getLogger(__name__)
field = magql.Field("String")

@field.pre_resolver
def audit_access(parent, info, **kwargs):
    logger.info("{'.'.join(info.path.as_list())} was accessed.")
```
