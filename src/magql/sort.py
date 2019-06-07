from sqlalchemy_utils import get_mapper


def generate_sorts(table, info, *args, **kwargs):
    sqla_sorts = []
    if "sort" in kwargs:
        class_ = get_mapper(table).class_
        gql_sorts = kwargs["sort"]
        for sort in gql_sorts:
            field_name, direction = sort[0].split('_')
            field = getattr(class_, field_name)
            if direction == 'asc':
                sort = field.asc()
            elif direction == 'desc':
                sort = field.desc()
            else:
                print("Sort not found")
            sqla_sorts.append(sort)
    return sqla_sorts
