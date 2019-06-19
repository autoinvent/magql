import pytest
from graphql import GraphQLInt
from graphql import GraphQLString
from sqlalchemy.types import Integer
from sqlalchemy.types import String
from sqlalchemy.types import VARCHAR

from magql.filter import IntFilter
from magql.filter import StringFilter
from magql.get_type import get_filter_type
from magql.get_type import get_type


get_type_parameters = [
    (String, GraphQLString),
    (VARCHAR, GraphQLString),
    (Integer, GraphQLInt),
]


@pytest.mark.parametrize("types", get_type_parameters)
def test_get_type(types):
    assert get_type(types[0]()) == types[1]


get_filter_type_parameters = [
    (String, StringFilter),
    (VARCHAR, StringFilter),
    (Integer, IntFilter),
]


@pytest.mark.parametrize("types", get_filter_type_parameters)
def test_get_filter_type(types):
    assert get_filter_type(types[0]()) == types[1]
