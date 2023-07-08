from __future__ import annotations

import typing as t

from graphql import GraphQLResolveInfo


class ValidationError(Exception):
    def __init__(self, message: t.Union[str, list[t.Any], dict[str, t.Any]]) -> None:
        super().__init__(message)
        self.message = message


class ValueValidatorCallable(t.Protocol):
    def __call__(
        self, info: GraphQLResolveInfo, value: t.Any, data: dict[str, t.Any]
    ) -> t.Any:
        ...


class DataValidatorCallable(t.Protocol):
    def __call__(self, info: GraphQLResolveInfo, data: dict[str, t.Any]) -> None:
        ...


class Confirm:
    """Check that the input is equal to the value of another input.

    :param other: Name of the other input to compare to.
    """

    def __init__(self, other: str) -> None:
        self.other = other

    def __call__(
        self, info: GraphQLResolveInfo, value: t.Any, data: dict[str, t.Any]
    ) -> None:
        if value != data[self.other]:
            raise ValidationError(f"Must equal the value given in '{self.other}'.")


class Length:
    """Check that the input's length is within a range. Either bound is
    optional, and both bounds are inclusive.

    :param min: The length must be >= this value.
    :param max: The length must be <= this value.
    """

    def __init__(
        self, min: t.Optional[int] = None, max: t.Optional[int] = None
    ) -> None:
        self.min = min
        self.max = max

    def __call__(
        self, info: GraphQLResolveInfo, value: t.Any, data: dict[str, t.Any]
    ) -> None:
        lv = len(value)

        if (self.min is None or lv >= self.min) and (
            self.max is None or lv <= self.max
        ):
            return

        if self.max is None:
            message = f"at least {self.min}"
        elif self.min is None:
            message = f"at most {self.max}"
        elif self.min == self.max:
            message = f"exactly {self.min}"
        else:
            message = f"between {self.min} and {self.max}"

        raise ValidationError(f"Must be {message} characters, but was {lv}.")


class NumberRange:
    """Check that the input is within a range. Either bound is optional,
    and both bounds are inclusive.

    :param min: The input must be >= this value.
    :param max: The input must be <= this value.
    """

    def __init__(
        self, min: t.Optional[t.Any] = None, max: t.Optional[t.Any] = None
    ) -> None:
        self.min = min
        self.max = max

    def __call__(
        self, info: GraphQLResolveInfo, value: t.Any, data: dict[str, t.Any]
    ) -> None:
        if (self.min is None or value >= self.min) and (
            self.max is None or value <= self.max
        ):
            return

        if self.max is None:
            message = f"at least {self.min}"
        elif self.min is None:
            message = f"at most {self.max}"
        else:
            message = f"between {self.min} and {self.max}"

        raise ValidationError(f"Must be {message}.")
