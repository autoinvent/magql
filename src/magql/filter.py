from functools import singledispatch

from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.types import VARCHAR, Integer, String
from graphql import GraphQLString, GraphQLEnumType, GraphQLInt, GraphQLInputObjectType, GraphQLID

from sqlalchemy_utils import get_mapper

StringFilter = GraphQLInputObjectType("StringFilter", {
    "operator": GraphQLEnumType("StringOperator", {"INCLUDES": "INCLUDES", "EQUALS": "EQUALS"}),
    "value": GraphQLString
})

IntFilter = GraphQLInputObjectType("IntFilter", {
    "operator": GraphQLEnumType("IntOperator", {
        "lt": "lt",
        "lte": "lte",
        "eq": "eq",
        "neq": "neq",
        "gt": "gt",
        "gte": "gte",
    }),
    "value": GraphQLInt
})

RelFilter = GraphQLInputObjectType("RelFilter", {
    "operator": GraphQLEnumType("RelOperator", {
        "INCLUDES": "INCLUDES"
    }),
    "value": GraphQLID
})


@singledispatch
def get_filter_comparator(_):
    print("Filter comparator type not found")


@get_filter_comparator.register(RelationshipProperty)
def _(_):
    def condition(filter_value, filter_operator, field):
        if filter_operator == "INCLUDES":
            return field == filter_value
        else:
            print("filter operator not found")
    return condition


@get_filter_comparator.register(VARCHAR)
@get_filter_comparator.register(String)
def _(_):
    def condition(filter_value, filter_operator, field):
        if filter_operator == "INCLUDES":
            return field.like(f"%{filter_value}%")
        elif filter_operator == "EQUALS":
            return field == filter_value
        else:
            print("filter operator not found")
    return condition


@get_filter_comparator.register(Integer)
def _(_):
    def condition(filter_value, filter_operator, field):
        if filter_operator == "lt":
            return field < filter_value
        elif filter_operator == "lte":
            return field <= filter_value
        elif filter_operator == "eq":
            return field == filter_value
        elif filter_operator == "neq":
            return field != filter_value
        elif filter_operator == "gt":
            return field > filter_value
        elif filter_operator == "gte":
            return field >= filter_value
        else:
            print("filter operator not found")
    return condition


def generate_filters(table, info, *args, **kwargs):
    sqla_filters = []
    if "filter" in kwargs:
        mapper = get_mapper(table)
        gql_filters = kwargs["filter"]
        for filter_name, gql_filter in gql_filters.items():
            gql_filter_value = gql_filter["value"]

            if filter_name in table.c:
                filter_type = table.c[filter_name].type
            elif filter_name in mapper.relationships:
                rel = mapper.relationships[filter_name]
                rel_mapper = get_mapper(rel.target)
                gql_filter_value = info.context.query(rel_mapper.class_).filter_by(id=gql_filter_value).one()
                filter_type = rel
            else:
                print("Unknown field on sqlamodel")

            sql_filter = get_filter_comparator(filter_type)(gql_filter_value, gql_filter["operator"], getattr(mapper.class_, filter_name))
            sqla_filters.append(sql_filter)
    return sqla_filters
