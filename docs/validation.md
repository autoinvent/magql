Input Validation
================

```{currentmodule} magql.nodes
```

GraphQL does not define a way to perform input validation, beyond checking the
types and non-null. Its error messages have location information, but only to
the field, not to a specific argument or input field.

Magql provides a robust input validation system on top of GraphQL. One or more
validator functions can be attached to any {class}`Field`, {class}`Argument`,
{class}`InputObject`, and {class}`InputField`. Before a field's resolver is
called, validators are run on its input structure, depth first.

The structure of the inputs to a field can be arbitrarily complex. The type of
an argument can be an {class}`InputObject` instead of a scalar, and the type of
an {class}`InputField` can be another input object, and so on. A type may be
wrapped in a {class}`List` an arbitrary number of times. This makes the overall
validation system potentially very complex, although in practice a well-designed
API should not exhibit too much complexity.

There is overlap between the different validation points described below. There
are multiple ways to validate the same data, in order to support arbitrary
input, but you may want to settle on a consistent style to make it easier to
reason about your API design.


Adding a Validator
------------------

There are a few ways to add a validator to a node. These examples will show
{class}`Argument`, the most common case. Other nodes behave the same, the only
difference is the signature of the validator callable as described in the next
two sections.

When creating the argument, one or more validator callables can be passed as a
list to the `validators` parameter.

```python
import magql

def validate_lowercase(info, value, data):
    if not value.islower():
        raise magql.ValidationError("Must be lowercase.")

field = magql.Field("String", args={
    "username": magql.Argument("String", validators=[validate_lowercase])
})
```

If the argument was already defined, you can add to its validators by decorating
the function with {meth}`Argument.validator`.

```python
import magql

field = magql.Field("String", args={"username": "String"})

@field.args["username"].validator
def validate_username(info, value, data):
    if not value.islower():
        raise magql.ValidationError("Must be lowercase.")
```


Validating an `Argument` or `InputField`
----------------------------------------

The most common task is to validate an individual value, regardless of the
complexities of its type.

The validator callables to {class}`Argument` and {class}`InputField` are
*value validators*. Value validator functions must take the following arguments:

-   `info` - The GraphQL resolver info.
-   `value` - The single input value being validated.
-   `data` - The dict of input values passed to the parent node. This can be
    used to check this value against another, but could also be handled by a
    data validator on the parent, described in the next section.

The function can raise a {exc}`.ValidationError` with one of two values:

-   A single string will be appended to the list of messages for the argument.
-   A list of strings will extend the list of messages for the argument.

```python
import magql

def validate_lower(info, value, data):
    if not value.islower():
        raise magql.ValidationError(f"'{info.field_name}' must be lower case.")
```

```python
import magql

def validate_username(info, value, data):
    errors = []

    if len(value) < 8:
        errors.append("Username must be at least 8 characters.")

    if "@" in value:
        errors.append("Username must not contain '@'.")

    if errors:
        raise magql.ValidationError(errors)
```


Validating a `Field` or `InputObject`
-------------------------------------

Rather than validating an individual input value, you may want to validate the
collection of input values. For example, you could validate that an input is
required only if another input is given.

The validator callables to {class}`Field` and {class}`InputObject` are *data
validators*. Data validator functions must take the following arguments:

-   `info` - The GraphQL resolver info.
-   `data` - The dict of input values passed to the node.

If validation fails, the function should raise a {exc}`.ValidationError` with a
message in one of three forms:

-   A single string will be appended to the list of messages for the field.
-   A list of strings will extend the list of messages for the field.
-   A dict will map error messages to specific input keys. Each value can be a
    string or a list, like above. The empty string `""` key is used for the
    field itself, like above.

```python
import magql

def validate_auth(info, data):
    if not current_user.is_admin:
        raise magql.ValidationError("Must be an admin to edit this data.")
```

```python
import magql

def validate_required_together(info, data):
    if "first" in data and "second" not in data:
        raise magql.ValidationError(
            {"second": "'second' must be given if 'first' is."}
        )
```


Validating a `List`
-------------------

Any type can be wrapped in a {class}`List`, making the input a list of values
of that type. In this case, you may want to treat the list as a single value to
validate overall, or you may want to validate each item in the list.

For example, you may want to validate a list of numbers by checking that the
list has at least one value, and that each value is positive.

```python
import magql

def validate_size(info, value, data):
    if len(value) < 1:
        raise magql.ValidationError("Must provide at least one value.")

def validate_positive(info, value, data):
    if value <= 0:
        raise magql.ValidationError("Value must be greater than zero.")

field = magql.Field("[Int!]!", args={
    "values": Argument(Int.non_null.list.non_null, validators=[
        validate_size, [validate_positive]
    ])
})
```

The first validator in the `validators` list is referenced directly, it applies
to the whole list as a single value. The second validator is wrapped in another
list, which indicates that it should be applied to each item in the list value
This can be nested arbitrarily, `validators=[[[v]]]` would apply `v` to each
item in an input that is a list of lists.

Items that do not have errors will have `null` in the list of errors. For
example, `[null, "Must be greater than zero.", null]` means there were three
items and only the second was invalid. The errors will be nested in extra lists
in the same way that `validators` was.


Errors in the Result
--------------------

If any validation errors are raised, the GraphQL operation result will have the
`errors` key set. The error raised by Magql will have the `message` `magql
argument validation`, and its `extensions` will be the validation message
structure.

Each individual input will be associated with a list of errors. Errors may be
strings, or may be further mappings or lists with messages for nested input
objects and list types. Each collection of inputs will be associated with a map
that maps the names of inputs to the list of error message for that input, with
an empty string `""` key for messages related to the collection.

```json
{"errors": [{
    "message": "magql argument validation",
    "extensions": {
        "name": ["Must be lowercase.", "Must be more than 2 characters."],
        "color": {"green": ["Must be less than 256."]},
        "people": [[null, {"age": "Must be greater than 0."}]],
    }
}]}
```

With this structure, it is possible to target exactly what input in the UI
resulted in what error messages in the result. When writing a UI, you'll
presumably know how your API validates data, and can code specifically for the
shape of the errors you expect.


Reusable Validators
-------------------

Validators can be a callable class (defines `__call__`) instead of a plain
function. This is a useful pattern for making configurable validators to be
reused on different arguments. For example, a validator that enforces a max
length.

```python
import magql

class Length:
    def __init__(self, max: int):
        self.max = max

    def __call__(self, info, value, data):
        if len(value) > self.max:
            raise magql.ValidationError(f"Length must be at most {self.max}.")

info_field = magql.Field("Info", args={
    "short_help": magql.Argument("String", validators=[Length(200)])
    "full_help": magql.Argument("String", validators=[Length(800)])
})
```
