from __future__ import annotations

import typing as t

from graphql import GraphQLError

from magql import Schema


def expect_data(schema: Schema, source: str, **kwargs: t.Any) -> dict[str, t.Any]:
    """Call :meth:`.Schema.execute` and return the data portion of the result.
    Raise an exception if there are any errors in the result.

    Raises the first error found, even if there are multiple errors.

    If the error is a plain GraphQL error, such as a missing required argument,
    it is raised directly. If the error is a wrapped exception, indicating an
    unhandled error in a resolver, the wrapped exception is raised.

    .. versionadded:: 1.1
    """
    result = schema.execute(source=source, **kwargs)

    if result.errors:
        error = result.errors[0]

        if error.original_error:
            raise error.original_error

        raise error

    assert result.data is not None
    return result.data


def expect_errors(schema: Schema, source: str, **kwargs: t.Any) -> list[GraphQLError]:
    """Call :meth:`.Schema.execute` and return the errors portion of the result.
    Raise an error if there are no errors.

    .. versionadded:: 1.1
    """
    result = schema.execute(source=source, **kwargs)
    assert result.errors is not None
    return result.errors


def expect_error(schema: Schema, source: str, **kwargs: t.Any) -> GraphQLError:
    """Call :meth:`.Schema.execute` and return the single error from the result.
    Raise an error if there is any data in the result, or if there is not
    exactly one error.

    .. versionadded:: 1.1
    """
    result = expect_errors(schema, source, **kwargs)

    if len(result) > 1:
        raise ValueError(
            "Expected query to return a single error, but it returned multiple."
        )

    return result[0]


def expect_validation_error(
    schema: Schema, source: str, **kwargs: t.Any
) -> dict[str, t.Any]:
    """Call :meth:`.Schema.execute` and return the single validation error content
    from the result. Raise an error if there is any data in the result, or if
    there is not exactly one validation error.

    .. versionadded:: 1.1
    """
    result = expect_error(schema, source, **kwargs)

    if result.message != "magql argument validation":
        raise ValueError("Expected a validation error.")

    assert result.extensions is not None
    return result.extensions
