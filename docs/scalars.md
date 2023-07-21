Scalar Types
============

```{currentmodule} magql.scalars
```

Fields with scalar types are *leaf* nodes in the graph, as opposed to objects
that provide more fields. GraphQL defines five default scalar types, and Magql
provides a few more useful types. It's also possible to define your own types.

Scalar types manage converting input data from JSON to Python, and output data
from Python to JSON. Executing a GraphQL operation validates the data against
the types before calling the resolvers.


GraphQL Built-In Scalars
------------------------

The following types are defined by the GraphQL spec. Magql provides wrappers
around the types from GraphQL-Core, so that they can be referenced in Magql.
It also patches the converters to work with string data from HTML forms.

-   {data}`String`
-   {data}`Int` accepts values as strings.
-   {data}`Float` accepts values as strings.
-   {data}`Boolean` accepts the strings 1, true, on, 0 false, and off.
-   {data}`ID` converts ints and floats to strings.


Magql Built-In Scalars
----------------------

Magql provides the following additional types:

-   {data}`DateTime` is a date, time, and timezone in ISO 8601 format.
-   {data}`JSON` is an arbitrary blob of JSON data.
-   {data}`Upload` is a placeholder to indicate a file upload with the
    [graphql-multipart-request-spec][multipart]

[multipart]: https://github.com/jaydenseric/graphql-multipart-request-spec


Custom Scalars
--------------

If you have a data type that is not natively representable in JSON, you can
write a custom scalar that can convert Python data to and from JSON data.

For example, there is no JSON equivalent to a Python {class}`~decimal.Decimal`.
Instead, we can represent it as a JSON string.

```python
import decimal
import magql

Decimal = magql.Scalar(
    name="Decimal",
    serialize=str,
    parse_value=decimal.Decimal,
    description="An arbitrary-precision decimal number given as a string.",
    specified_by="https://docs.python.org/3/library/decimal.html"
)
schema = magql.Schema(types=[Decimal])

@schema.query.field("add", Decimal, args={"a": "Decimal", "b": "Decimal"})
def resolve_add(parent, info, **kwargs):
    a = kwargs.pop("a")
    b = kwargs.pop("b")
    return a + b
```

```pycon
>>> schema.execute("""query { add("1.1", "2.2") }""").data
{'add': '3.3'}
```

Remember, this only defines the scalar on the server. It's important to fill in
`description` and `specified_by` for custom scalars. This information will be
present in the schema document and introspection, and serves as documentation
for others to know how to implement the type.
