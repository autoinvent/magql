import pytest
from graphql import execute
from graphql import parse

from magql.convert import Convert

query = """
query test {
  people {
    result {
      name
    }
  }
  cars {
    result {
      name
    }
  }
  houses {
    result {
      name
    }
  }
}
"""


@pytest.fixture
def schema(manager_collection):
    manager_list = list(manager_collection.manager_map.values())
    return Convert(manager_list).generate_schema()


def test_schema(session, schema):
    document = parse(query)
    result = execute(schema, document, context_value=session)
    assert result.data["people"]["result"][0]["name"] == "Person 1"
    assert result.data["cars"]["result"][0]["name"] == "Car 1"
    assert result.data["houses"]["result"][0]["name"] == "House 1"
