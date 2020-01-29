from sqlalchemy_utils import get_mapper

from magql.logging import magql_logger


def generate_sorts(table, info, *args, **kwargs):
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
                magql_logger.warn("Sort not found")
            sqla_sorts.append(sort)
    return sqla_sorts
