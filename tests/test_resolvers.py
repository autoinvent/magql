from decimal import Decimal

import pytest
from tests.conftest import base
from tests.conftest import Car
from tests.conftest import House
from tests.conftest import Person

from magql.resolver_factory import CreateResolver
from magql.resolver_factory import DeleteResolver
from magql.resolver_factory import SingleResolver
from magql.resolver_factory import UpdateResolver


def compare(output, test_input):
    for key, value in test_input.items():
        output_value = getattr(output, key)
        if isinstance(output_value, list):
            for instance in output_value:
                if isinstance(instance, base):
                    assert instance.id in value
        elif isinstance(output_value, base):
            assert output_value.id == value
        else:
            assert output_value == value


@pytest.mark.parametrize(
    "input_data",
    [
        (House, {"name": "House 2", "inhabitants": [1]}),
        (
            Car,
            {
                "name": "Car 2",
                "drivers": [1],
                "mpg": 25.6,
                "top_speed": Decimal("105.333"),
            },
        ),
        (Person, {"name": "Person 2", "age": 30, "car": 1, "house": 1}),
    ],
)
def test_create_resolver(input_data, info, session):
    test_class = input_data[0]
    test_input = input_data[1]
    resolve = CreateResolver(test_class.__table__)

    output = resolve(None, info, input=test_input)

    compare(output, test_input)


@pytest.mark.parametrize(
    "input_data",
    [
        (House, 1, {"name": "House 2", "inhabitants": [1]}),
        (
            Car,
            1,
            {
                "name": "Car 2",
                "drivers": [1],
                "mpg": 33.8,
                "top_speed": Decimal("94.825"),
            },
        ),
        (Person, 1, {"name": "Person 2", "age": 30, "car": 1, "house": 1}),
    ],
)
def test_update_resolver(input_data, info, session):
    test_class = input_data[0]
    test_id = input_data[1]
    test_input = input_data[2]
    resolve = UpdateResolver(test_class.__table__)

    output = resolve(None, info, id=test_id, input=test_input)

    compare(output, test_input)


@pytest.mark.parametrize("input_data", [(House, 1), (Car, 1), (Person, 1)])
def test_delete_resolvers(input_data, info, session):
    test_class = input_data[0]
    test_id = input_data[1]
    resolve = DeleteResolver(test_class.__table__)

    resolve(None, info, id=test_id)

    del_inst = session.query(test_class).filter_by(id=test_id).one_or_none()

    assert del_inst is None


@pytest.mark.parametrize("model", [House, Car, Person])
@pytest.mark.parametrize("model_id", [1, 2])
def test_single_resolvers(model, model_id, session, info):
    resolver = SingleResolver(model.__table__)
    resolved_value = resolver(None, info, id=model_id)
    queried_value = session.query(model).filter_by(id=model_id).one_or_none()
    if queried_value is not None:
        assert queried_value == resolved_value
    else:
        assert resolved_value["result"] is None
