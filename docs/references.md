Type References
===============

```{currentmodule} magql.nodes
```

Each {class}`Scalar`, {class}`Enum`, {class}`Object`, and {class}`InputObject`
type has a unique name. {class}`NonNull` and {class}`List` are wrapper types
that modify named types. Most nodes in GraphQL have a type, such as fields and
arguments.

A type can be referenced by importing and passing the actual Python object
around. However, this can get tedious, and can cause circular import issues when
splitting up definitions across multiple files. Magql allows referring to types
by name instead of the Python object.

```python
import magql

magql.Field(magql.String)
magql.Field("String")
```

It's possible to create circular references to types. Within an object, a
field's type can be the object itself, or less directly through a chain of other
fields. For example, a `User` with a `friend` field that is another user. In
this case, you must refer to the type by name, this is called a _forward
reference_.

```python
import magql

User = magql.Object("User", fields={
    "username": "String",
    "friend" "User"
})
```


Resolving References
--------------------

The schema must have a defined type object for every type name in the graph.
Calling {meth}`.Schema.to_graphql` will traverse the graph and collect all named
type objects, then replace any string references with the corresponding object.

In the example below, the `User` object is defined when defining the second
field, so the schema will know about it and apply it to the `"User"` name in the
first field. Order does not matter, as long as the object is defined _somewhere_
in the schema.

```python
import magql

schema = magql.Schema()
schema.query.fields["user"] = magql.Field("User")
schema.mutation.fields["create_user"] = magql.Field(magql.Object("User"))
```

You can also tell the schema about a type directly, so that every reference can
be a string, avoiding the nested definition above. You can pass the type when
creating the schema, or by calling {meth}`Schema.add_type`.

```python
import magql

User = magql.Object("User")
schema = magql.Schema(types=[User])
```

```python
import magql

schema = magql.Schema()
User = magql.Object("User")
schema.add_type(User)
```

If you try to call {meth}`Schema.to_graphql` while some names are still
undefined, you'll get an error message.

```text
Could not find definitions for the following type names: User. All types must be
defined somewhere in the graph, or passed when creating the Schema.
```


Wrapping Types
--------------

Every type object has two properties, {attr}`~Object.non_null` and
{attr}`~Object.list` which return corresponding {class}`NonNull` and
{class}`List`. `List` and `NonNull` have these properties too, so you can create
arbitrarily nested structures. When using a string reference, you can use the
same syntax as GraphQL to apply wrappers.

In the following example, both fields will have the same type, a non-null list
of non-null strings.

```python
import magql

magql.Field(magql.String.non_null.list.non_null)
magql.Field("[String!]!")
```
