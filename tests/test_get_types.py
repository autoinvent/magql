import pytest
from sqlalchemy import Column
from sqlalchemy import DECIMAL
from sqlalchemy.types import Float
from sqlalchemy.types import Integer
from sqlalchemy.types import Numeric
from sqlalchemy.types import REAL
from sqlalchemy.types import String
from sqlalchemy.types import VARCHAR

from magql.definitions import MagqlFloat
from magql.definitions import MagqlInt
from magql.definitions import MagqlString
from magql.filter import IntFilter
from magql.filter import StringFilter
from magql.type import get_magql_filter_type
from magql.type import get_magql_type


get_magql_type_parameters = [
    (Column(String), MagqlString),
    (Column(VARCHAR), MagqlString),
    (Column(Integer), MagqlInt),
    (Column(Float), MagqlFloat),
    (Column(Numeric), MagqlFloat),
    (Column(REAL), MagqlFloat),
    (Column(DECIMAL), MagqlFloat),
]


@pytest.mark.parametrize("types", get_magql_type_parameters)
def test_get_type(types):
    assert isinstance(get_magql_type(types[0]), types[1])


get_magql_filter_type_parameters = [
    (Column(String), None, StringFilter),
    (Column(VARCHAR), None, StringFilter),
    (Column(Integer), None, IntFilter),
]


@pytest.mark.parametrize("types", get_magql_filter_type_parameters)
def test_get_filter_type(types):
    assert get_magql_filter_type(types[0], types[1]) == types[2]
