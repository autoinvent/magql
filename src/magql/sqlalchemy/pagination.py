from __future__ import annotations

import typing as t

from graphql import GraphQLResolveInfo

from ..validators import ValidationError


def validate_page(info: GraphQLResolveInfo, value: int, data: t.Any) -> None:
    """Validate the ``page`` argument to :class:`.ListResolver`."""
    if value < 1:
        raise ValidationError("Must be at least 1.")


class PerPageValidator:
    """Validate the ``per_page`` argument to :class:`.ListResolver`.

    :param max_per_page: The maximum allowed value, or ``None`` for no maximum.
    """

    def __init__(self, max_per_page: int | None = 100) -> None:
        self.max_per_page = max_per_page

    def __call__(self, info: GraphQLResolveInfo, value: int, data: t.Any) -> None:
        if value < 1:
            raise ValidationError("Must be at least 1.")

        if self.max_per_page is not None and value > self.max_per_page:
            raise ValidationError(f"Must not be greater than {self.max_per_page}.")
