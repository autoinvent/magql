import pytest
from graphql import execute
from graphql import parse

from .conftest import Car
from magql.convert import Convert


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


def generate_page(current, per_page):
    return {"page": {"current": current, "per_page": per_page}}


@pytest.fixture
def schema(manager_collection):
    manager_list = list(manager_collection.manager_map.values())
    return Convert(manager_list).generate_schema()


def test_single_query(session, schema, single_query):
    document = parse(single_query)
    result = execute(schema, document, context_value=session)
    assert result.data["person"]["result"]["name"] == "Person 1"
    assert result.data["car"]["result"]["name"] is None
    assert result.data["house"]["result"]["name"] is None


def test_many_query(session, schema, many_query):
    document = parse(many_query)
    result = execute(schema, document, context_value=session)
    assert result.data["people"]["result"][0]["name"] == "Person 1"
    assert result.data["cars"]["result"][0]["name"] == "Car 1"
    assert result.data["houses"]["result"][0]["name"] == "House 1"


@pytest.mark.parametrize(
    ("page", "expected_count", "result_length"),
    [
        (generate_page(1, 1), 3, 1),
        (generate_page(2, 1), 3, 1),
        (generate_page(1, 2), 3, 2),
        (generate_page(-1, 2), 3, 2),
        (generate_page(-1, 2), 3, 2),
        (generate_page(6, 1), 3, 0),
        (generate_page(5, 5), 3, 0),
        (generate_page(1, 100), 3, 3),
    ],
)
def test_page(session, schema, page, expected_count, result_length):
    document = parse(query_pagination)

    car2 = Car(name="Car 2")
    car3 = Car(name="Car 3")
    session.add(car2)
    session.add(car3)
    session.commit()

    result = execute(schema, document, context_value=session, variable_values=page)
    assert len(result.data["cars"]["result"]) == result_length
    assert result.data["cars"]["count"] == expected_count
