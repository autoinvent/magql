Getting Started
===============

```{currentmodule} magql
```

This will walk you through some of Magql's features, which are described in more
detail in the rest of the documentation. Read [GraphQL's tutorial][gt] first to
understand how a GraphQL schema is constructed.

[gt]: https://graphql.org/learn/


A Simple Example
----------------

The {class}`.Schema` is the entry point into the API, and provides
{attr}`~.Schema.query` and {attr}`~.Schema.mutation` objects to register fields
on. Each {class}`.Field` has a type and a resolver function that returns data of
that type. If the field defines arguments, and they are given in the operation,
they will be passed to the resolver.

```python
import magql

schema = magql.Schema()

@schema.query.field("greet", "String!", args={
    "name": magql.Argument("String!", default="World")
})
def resolve_greet(parent, info, **kwargs):
    name = kwargs.pop("name")
    return f"Hello, {name}!"
```

After defining the API, call {meth}`.Schema.execute` to execute an operation.

```pycon
>>> schema.execute("""query { greet }""").data
{'greet': 'Hello, World!'}

>>> schema.execute("""query { greet(name: "Magql") }""")
{'greet': 'Hello, Magql!'}
```


Integrations
------------

Magql provides all the parts needed to define a complex and powerful GraphQL
API, but it's still a manual process. There are extensions that integrate Magql
with other libraries to make this easier.

-   [Magql-SQLAlchemy][] generates a complete API given a SQLAlchemy declarative
    model class. Includes item, list (with filter, sort, page), create, update,
    delete, search, and check delete operations. Validates ids and unique
    constraints.
-   [Flask-Magql][] serves a Magql schema with Flask. Implements the multipart
    file upload GraphQL extension. Provides [GraphiQL][] and [Conveyor][] UIs.

[magql-sqlalchemy]: https://github.com/autoinvent/magql-sqlalchemy/
[flask-magql]: https://github.com/autoinvent/flask-magql/
[GraphiQL]: https://github.com/graphql/graphiql/
[Conveyor]: https://github.com/autoinvent/conveyor/


Operations
----------

After building the graph (the schema), operations are executed on it. An
operation describes a traversal of the graph. Each field is a step to take on a
path through the graph. The result of each resolver is either data in the
output, or the parent data for the next field in the path.

GraphQL distinguishes operations as queries which access data, or mutations
which change data. This distinction is only at the top-level, the fields you add
to the {attr}`.Schema.query` and {attr}`.Schema.mutation` objects. Every field's
resolver is a function, so any field could potentially do anything when it is
resolved. Using the `query` and `muatation` distinction is a convention that
makes it easier to reason about the API.

Technically, the GraphQL spec says that queries can be executed in parallel,
while mutations must be executed in order. And there's a third operation,
subscription, which is a query that continues to stream results. However, Magql
isn't currently implemented in a way where this matters. It's still a useful way
to think about what goes where.


Types and References
--------------------

The type of each {class}`.Field` can be a {class}`.Scalar` or {class}`.Enum`, or
an {class}`.Object` with more fields, creating a graph. Each field can have
arguments, which also have a type. An argument type can be {class}`.Scalar` or
{class}`.Enum`, but it uses {class}`.InputObject` with {class}`.InputField` for
complex data, instead of {class}`.Object`. This can all be a bit confusing, but
here's the outline:

-   A {class}`.Field` is an output, a {class}`.Argument` is an input.
-   {class}`.Scalar` and {class}`.Enum` describe single values for both input
    and output.
-   {class}`.Object` with {class}`.Field` describes complex output data.
-   {class}`.InputObject` with {class}`.InputField` describes complex input
    data.

Types can be referred to by their name, rather than needing to import their
Python objects everywhere. As long as the schema knows about the named type, it
will be applied correctly when creating the GraphQL schema. Referring to types
by name is more convenient, and also allows circular and forward references.

Types can be wrapped with {class}`.NonNull` and {class}`.List`. Every type has
{attr}`~.Object.non_null` and {attr}`~.Object.list` properties that do the same.
When referring to types by name, the GraphQL syntax for non-null `Type!` and
list `[Type]` can be used.

The following examples are equivalent.

```python
Field(NonNull(List(NonNull(user_object))))
Field(user_object.non_null.list.non_null)
Field("[User!]!")
```

See {doc}`references` and {doc}`scalars` for more information.


Defining Structure
------------------

Definition starts at fields on the {attr}`.Schema.query` and
{attr}`.Schema.mutation` objects. Other {class}`.Object` and
{class}`.InputObject` types can be defined and added with
{meth}`.Schema.add_type` so that they may be referenced by name.

```python
import magql

schema = magql.Schema()
user_object = magql.Object("User", fields={"id": "Int!", "name": "String!"})
user_input = magql.InputObject("UserInput")
schema.add_type(user_object)
```

When defining an object's `fields`, the values can be just the type name or
object instead of a {class}`.Field` object, which is convenient if you don't
need further customization or will do it later. The following examples are
equivalent.

```python
Object("User", fields={"id": Field("Int!")})
Object("User", fields={"id": Int.non_null})
Object("User", fields={"id": "Int!"})
```

This works in places that take collections during init. After a node is defined,
you can modify its attributes in place. However, you must use the correct nodes
at this point, the type shortcut no longer applies.

-   The `Object.fields` param takes a type in place of {class}`.Field`. The the
    {attr}`.Object.fields` attr can be modified.
-   The `Field.args` param takes a type in place of {class}`.Argument`. Then the
    {attr}`.Field.args` attr can be modified.
-   The `InputObject.fields` param takes a type in place of
    {class}`.InputField`. Then the {attr}`.InputField.fields` attr can be
    modified.

Some nodes provide decorators for a quick way to add or modify behavior:

-   {meth}`.Object.field` adds a {class}`.Field` to an object by decorating its
    resolver.
-   {meth}`.Field.resolver` decorates a new resolver function for the field.
    {meth}`.Field.pre_resolver` is similar.
-   {meth}`.Argument.validator`, {meth}`.InputField.validator`,
    {meth}`.Field.validator` and {meth}`.InputObject.validator` decorate a
    validator callable to add to the list of validators.

Everything about any node can be modified after it is created, not only the
attributes and decorators shown here. However, all modifications are "locked"
once {meth}`.Schema.to_graphql` is called.


Resolvers and Validation
------------------------

Each {class}`.Field` has a resolver function that is called when the field is
traversed during an operation. If the field's type is an object, it returns the
next object to traverse, or if it is a scalar it returns the data for output.

Resolver functions all take the same three arguments, `parent`, `info`, and
`**kwargs`. `parent` is the object "above" the current field, such as a `User`
for a `username` field. `kwargs` is a dict of arguments passed to the field,
which will have been validated already.

Magql generates a resolver with three different stages. The callables in each
stage can raise {exc}`.ValidationError` to add an error to the output instead of
data. Before any of the resolver system runs, GraphQL scalars will have already
converted the input values to the appropriate types.

1.  {meth}`.Field.pre_resolver` can decorate a function used to perform checks
    before the validators and resolver run, such as checking authentication or
    audit logging access.
2.  {meth}`.Field.validate` is called to validate the input data. Arguments,
    input fields, fields, and input objects can all have validators. List types
    can have validators for the whole list or each item in the list. Each node
    has a {meth}`~.Argument.validator` decorator to add another validator.
3.  The field's resolver is called with the validated input arguments to get the
    output value. The default resolver accesses `parent.field_name`.
    {meth}`.Field.resolver` can decorate a new resolver callable.

If validation errors occur, an error with the message `magql argument
validation` will be present in `result.errors`. Its `extensions` property has
error messages in a structure that matches that of the argument structure.

See {doc}`resolvers` and {doc}`validation` for more information.
