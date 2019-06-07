import pytest
from sqlalchemy.types import VARCHAR, Integer, String
from magql.filter import StringFilter, IntFilter
from magql.get_type import get_filter_type, get_type
from graphql import GraphQLString, GraphQLInt


@pytest.mark.parametrize("types", [
    (String, GraphQLString),
    (VARCHAR, GraphQLString),
    (Integer, GraphQLInt)])
def test_get_filter_type(types):
    assert get_type(types[0]()) == types[1]

@pytest.mark.parametrize("types", [
    (String, StringFilter),
    (VARCHAR, StringFilter),
    (Integer, IntFilter)])
def test_get_filter_type(types):
    assert get_filter_type(types[0]()) == types[1]
