import pytest

from magql.definitions import MagqlObjectType
from magql.definitions import NamingConflictError


def test_name_validation():
    with pytest.raises(NamingConflictError):
        MagqlObjectType("test")
        MagqlObjectType("test")
