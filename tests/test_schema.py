import pytest
from graphql import execute
from graphql import parse

from .conftest import Car
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

query_pagination = """
query test($page: Page) {
  cars (page: $page){
    result {
      name
    }
    count
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


def test_page(session, schema):
    def generate_page(current, per):
        return {"page": {"current": current, "per_page": per}}

    car2 = Car(name="Car 2")
    car3 = Car(name="Car 3")
    session.add(car2)
    session.add(car3)
    session.commit()

    document = parse(query_pagination)

    # first page, one per page
    result = execute(
        schema, document, context_value=session, variable_values=generate_page(0, 1)
    )
    assert len(result.data["cars"]["result"]) == 1
    assert result.data["cars"]["result"][0]["name"] == "Car 1"
    assert result.data["cars"]["count"] == 3

    # second page, one per page
    result = execute(
        schema, document, context_value=session, variable_values=generate_page(1, 1)
    )
    assert len(result.data["cars"]["result"]) == 1
    assert result.data["cars"]["result"][0]["name"] == "Car 2"
    assert result.data["cars"]["count"] == 3

    # first page, two per page
    result = execute(
        schema, document, context_value=session, variable_values=generate_page(0, 2)
    )
    assert len(result.data["cars"]["result"]) == 2
    assert result.data["cars"]["count"] == 3

    # bad page, -2 per page
    result = execute(
        schema, document, context_value=session, variable_values=generate_page(0, -2)
    )
    assert result.errors[0].message == "Page inputs must be positive"

    # ask for a page # greater than total count
    result = execute(
        schema, document, context_value=session, variable_values=generate_page(5, 1)
    )
    assert len(result.data["cars"]["result"]) == 0

    # ask for current, per_page that exceeds total count
    result = execute(
        schema, document, context_value=session, variable_values=generate_page(2, 5)
    )
    assert len(result.data["cars"]["result"]) == 0

    # ask for per_page that exceeds total count
    result = execute(
        schema, document, context_value=session, variable_values=generate_page(0, 100)
    )
    assert len(result.data["cars"]["result"]) == 3
