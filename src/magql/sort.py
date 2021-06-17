from __future__ import annotations

import typing as t

from sqlalchemy_utils import get_mapper


class SortNotFoundError(Exception):
    def __init__(self, field_name: str, direction: str):
        super().__init__(field_name, direction)
        self.field_name = field_name
        self.direction = direction

    def __str__(self) -> str:
        return (
            f"Sort not found for"
            f" (field: {self.field_name}, direction: {self.direction})"
        )


def generate_sorts(
    table: t.Any, info: t.Any, *args: t.Any, **kwargs: t.Any
) -> t.List[t.Any]:
    sqla_sorts = []
    if "sort" in kwargs and kwargs["sort"] is not None:
        class_ = get_mapper(table).class_
        gql_sorts = kwargs["sort"]
        for sort in gql_sorts:
            field_name, direction = sort[0].rsplit("_", 1)
            field = getattr(class_, field_name)
            if direction == "asc":
                sort = field.asc()
            elif direction == "desc":
                sort = field.desc()
            else:
                raise SortNotFoundError(field_name, direction)
            sqla_sorts.append(sort)
    return sqla_sorts
