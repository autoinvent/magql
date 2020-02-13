import pytest
from graphql import assert_valid_schema
from graphql import GraphQLArgument
from graphql import GraphQLBoolean
from graphql import GraphQLEnumType
from graphql import GraphQLField
from graphql import GraphQLFloat
from graphql import GraphQLID
from graphql import GraphQLInputField
from graphql import GraphQLInputObjectType
from graphql import GraphQLInt
from graphql import GraphQLList
from graphql import GraphQLNonNull
from graphql import GraphQLObjectType
from graphql import GraphQLString
from graphql import GraphQLUnionType
from graphql import validate_schema

from magql.convert import Convert
from magql.definitions import MagqlArgument
from magql.definitions import MagqlBoolean
from magql.definitions import MagqlEnumType
from magql.definitions import MagqlField
from magql.definitions import MagqlFloat
from magql.definitions import MagqlID
from magql.definitions import MagqlInputField
from magql.definitions import MagqlInputObjectType
from magql.definitions import MagqlInt
from magql.definitions import MagqlList
from magql.definitions import MagqlNonNull
from magql.definitions import MagqlObjectType
from magql.definitions import MagqlString
from magql.definitions import MagqlUnionType


class DummyInfo:  # noqa: E501
    def __init__(self, session):
        self.type_map = {
            "Test": GraphQLObjectType("Test", GraphQLField(GraphQLList(GraphQLString))),
            "TestEmptyObject": GraphQLObjectType("TestEmptyObject", {}),
            "TestNestedObjects": GraphQLObjectType(
                "TestNestedObjects",
                {
                    "EnumField": GraphQLField(
                        GraphQLEnumType("TestEnum", {"RED": 0, "GREEN": 1, "BLUE": 2})
                    ),
                    "InputField": GraphQLInputField(GraphQLNonNull(GraphQLInt)),
                    "List": GraphQLList(GraphQLString),
                    "InputObjectType": GraphQLInputObjectType(
                        "TestInputObject",
                        GraphQLNonNull(
                            GraphQLUnionType("TestUnion", [GraphQLString, GraphQLID])
                        ),
                    ),
                    "ArgumentType": GraphQLArgument(GraphQLBoolean),
                    "Float": GraphQLFloat,
                },
            ),
        }
        self.context = session


@pytest.fixture
def info(session):
    return DummyInfo(session)


@pytest.mark.parametrize(
    "to_convert",
    [
        MagqlObjectType("Test", MagqlField(MagqlList(MagqlString))),
        MagqlObjectType("TestEmptyObject", {}),
        MagqlObjectType(
            "TestNestedObjects",
            {
                "EnumField": MagqlField(
                    MagqlEnumType("TestEnum", {"RED": 0, "GREEN": 1, "BLUE": 2})
                ),
                "InputField": MagqlInputField(MagqlNonNull(MagqlInt)),
                "List": MagqlList(MagqlString),
                "InputObjectType": MagqlInputObjectType(
                    "TestInputObject",
                    MagqlNonNull(
                        MagqlUnionType(
                            "TestUnion", [MagqlString, MagqlID], print("test"),
                        )
                    ),
                ),
                "ArgumentType": MagqlArgument(MagqlBoolean),
                "Float": MagqlFloat(),
            },
        ),
    ],
)
def test_convert_object(info, session, to_convert):
    converted = to_convert.convert(info.type_map)
    assert isinstance(converted, GraphQLObjectType)
    assert converted in info.type_map.values()


def test_convert_manager(info, session, manager_collection):
    converted = Convert(manager_collection.manager_map.values())
    converted_schema = converted.generate_schema()
    schema_validator = validate_schema(converted_schema)
    assert schema_validator == []
    assert assert_valid_schema(converted_schema) is None
