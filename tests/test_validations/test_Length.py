from unittest.mock import Mock

from graphql import GraphQLResolveInfo

import magql

"""
This test file validates the behavior of the
length validator when applied on different levels of the schema.
It covers the following scenarios:
*    - Validation of [Field | Argument | InputObject | InputField]
*       - with valid data.
*    - Validation of [Field | Argument | InputObject | InputField]
*       - with invalid data, including too short and too long values.
*    - Validation of [Field | Argument | InputObject | InputField]
*       - with an exact length requirement.
*    - Validation of [Field & Argument & InputObject & InputField]
*       - with valid and invalid data.
"""


def test_length_validator_on_field():
    """
    Tests the Length validator specifically for an Field in a GraphQL schema.
    Creates Fields, each with a unique Length validator
    Uses wrapper functions to apply the validators.
    The Fields are validated using the `.validate` method
    from _DataValidatorNode with data of various lengths.
    The tests ensure that the Length validator correctly identifies:
    valid, too short, too long names, and names of exact length within the Fields.
    """
    valid_name = "John Doe"
    valid_name_exact = "Johny"
    invalid_name_short = "J"
    invalid_name_long = "John Doe" * 2
    invalid_name_exact = "John"

    def resolve_field(obj, info):
        return obj["name"]

    def length_validator_min_wrapper(info, data):
        length_validator = magql.Length(min=2)
        try:
            length_validator(info, data["name"], data)
        except magql.ValidationError as e:
            raise magql.ValidationError({"name": e.message}) from e

    def length_validator_max_wrapper(info, data):
        length_validator = magql.Length(max=15)
        try:
            length_validator(info, data["name"], data)
        except magql.ValidationError as e:
            raise magql.ValidationError({"name": e.message}) from e

    def length_validator_min_max_wrapper(info, data):
        length_validator = magql.Length(min=2, max=15)
        try:
            length_validator(info, data["name"], data)
        except magql.ValidationError as e:
            raise magql.ValidationError({"name": e.message}) from e

    def length_validator_exact_wrapper(info, data):
        length_validator = magql.Length(min=5, max=5)
        try:
            length_validator(info, data["name"], data)
        except magql.ValidationError as e:
            raise magql.ValidationError({"name": e.message}) from e

    UserFieldMin = magql.Field(
        "String", validators=[length_validator_min_wrapper], resolve=resolve_field
    )

    UserFieldMax = magql.Field(
        "String", validators=[length_validator_max_wrapper], resolve=resolve_field
    )

    UserFieldMinMax = magql.Field(
        "String", validators=[length_validator_min_max_wrapper], resolve=resolve_field
    )

    UserFieldExact = magql.Field(
        "String", validators=[length_validator_exact_wrapper], resolve=resolve_field
    )

    info = Mock(spec=GraphQLResolveInfo)
    # Test the fields with valid data
    data = {"name": valid_name}
    for UserField in [UserFieldMin, UserFieldMax, UserFieldMinMax]:
        UserField.validate(info, data)

    # Test the field with invalid data (too short)
    data = {"name": invalid_name_short}
    for UserField, error_message in [
        (UserFieldMin, "Must be at least 2 characters, but was 1."),
        (UserFieldMinMax, "Must be between 2 and 15 characters, but was 1."),
    ]:
        try:
            UserField.validate(info, data)
        except magql.ValidationError as e:
            assert "name" in e.message
            assert e.message["name"][0] == error_message

    # Test the field with invalid data (too long)
    data = {"name": invalid_name_long}
    for UserField, error_message in [
        (UserFieldMax, "Must be at most 15 characters, but was 16."),
        (UserFieldMinMax, "Must be between 2 and 15 characters, but was 16."),
    ]:
        try:
            UserField.validate(info, data)
        except magql.ValidationError as e:
            assert "name" in e.message
            assert e.message["name"][0] == error_message

    # Test the field with invalid data (not exact)
    data = {"name": invalid_name_exact}
    error_message = "Must be exactly 5 characters, but was 4."
    try:
        UserFieldExact.validate(info, data)
    except magql.ValidationError as e:
        assert "name" in e.message
        assert e.message["name"][0] == error_message

    # Test the field with valid data (exact)
    data = {"name": valid_name_exact}
    UserFieldExact.validate(info, data)


def test_length_validator_on_argument():
    """
    Tests the Length validator specifically for an Argument in a GraphQL schema.
    Creates Arguments, each with a unique Length validator.
    Uses GraphQL mutations to validate the Arguments with data of various lengths.
    The tests verify the correct behaviour of the Length validator in the context of
    GraphQL input fields, by checking if it correctly identifies:
    valid, too short, too long names, and names of exact length.
    """
    UserArgumentMinMax = magql.Argument(
        "String", validators=[magql.Length(min=2, max=15)]
    )
    UserArgumentMin = magql.Argument("String", validators=[magql.Length(min=2)])
    UserArgumentMax = magql.Argument("String", validators=[magql.Length(max=15)])
    UserArgumentExact = magql.Argument(
        "String", validators=[magql.Length(min=5, max=5)]
    )

    def resolve_name_field(parent, info):
        field_name = info.field_name
        return parent[field_name]

    QueryRoot = magql.Object(
        "QueryRoot",
        fields={
            "dummy": magql.Field("String", resolve=lambda obj, info: "dummy"),
        },
    )
    s = magql.Schema()
    s.query = QueryRoot

    User = magql.Object(
        "User",
        fields={
            "nameMin": magql.Field("String", resolve=resolve_name_field),
            "nameMax": magql.Field("String", resolve=resolve_name_field),
            "nameMinMax": magql.Field("String", resolve=resolve_name_field),
            "nameExact": magql.Field("String", resolve=resolve_name_field),
        },
    )

    @s.mutation.field(
        "createUser",
        User,
        args={
            "nameMin": UserArgumentMin,
            "nameMax": UserArgumentMax,
            "nameMinMax": UserArgumentMinMax,
            "nameExact": UserArgumentExact,
        },
    )
    def resolve_create_user(parent, info, nameMin, nameMax, nameMinMax, nameExact):
        return {
            "nameMin": nameMin,
            "nameMax": nameMax,
            "nameMinMax": nameMinMax,
            "nameExact": nameExact,
        }

    # Test the mutation with valid data
    valid_name = "John Doe"
    valid_name_exact = "Johny"
    mutation_valid = f"""
        mutation {{
            createUser(
                nameMin: "{valid_name}",
                nameMax: "{valid_name}",
                nameMinMax: "{valid_name}",
                nameExact: "{valid_name_exact}"
            ) {{
                nameMin
                nameMax
                nameMinMax
                nameExact
            }}
        }}
    """
    result_valid = s.execute(mutation_valid)
    assert not result_valid.errors
    assert result_valid.data == {
        "createUser": {
            "nameMin": valid_name,
            "nameMax": valid_name,
            "nameMinMax": valid_name,
            "nameExact": valid_name_exact,
        }
    }

    # Test the mutation with invalid data
    invalid_name_short = "J"
    invalid_name_long = "John" * 4
    invalid_name_exact = "John"
    mutation_invalid = f"""
        mutation {{
            createUser(
                nameMin: "{invalid_name_short}",
                nameMax: "{invalid_name_long}",
                nameMinMax: "{invalid_name_long}",
                nameExact: "{invalid_name_exact}"
            ) {{
                nameMin
                nameMax
                nameMinMax
                nameExact
            }}
        }}
    """
    result_invalid = s.execute(mutation_invalid)
    error_messages = result_invalid.errors[0].extensions
    assert len(error_messages) == 4
    assert error_messages["nameMin"][0] == "Must be at least 2 characters, but was 1."
    assert error_messages["nameMax"][0] == "Must be at most 15 characters, but was 16."
    assert (
        error_messages["nameMinMax"][0]
        == "Must be between 2 and 15 characters, but was 16."
    )
    assert error_messages["nameExact"][0] == "Must be exactly 5 characters, but was 4."


def test_length_validator_on_inputObject():
    """
    Tests the Length validator specifically for an InputObject in a GraphQL schema.
    Creates InputObjects, each with a unique Length validator
    Uses wrapper functions to apply the validators.
    The InputObjects are validated using the `.validate` method
    from _DataValidatorNode with data of various lengths.
    The tests ensure that the Length validator correctly identifies:
    valid, too short, too long names, and names of exact length within the InputObjects.
    """
    valid_input = {"name": "John Doe"}
    valid_input_exact = {"name": "Johny"}
    invalid_input_short = {"name": "J"}
    invalid_input_long = {"name": "John Doe" * 2}
    invalid_input_exact = {"name": "John"}

    UserInputField = magql.InputField("String")

    def length_validator_min_max_wrapper(info, data):
        length_validator = magql.Length(min=2, max=15)
        try:
            length_validator(info, data["name"], data)
        except magql.ValidationError as e:
            raise magql.ValidationError({"name": e.message}) from e

    def length_validator_min_wrapper(info, data):
        length_validator = magql.Length(min=2)
        try:
            length_validator(info, data["name"], data)
        except magql.ValidationError as e:
            raise magql.ValidationError({"name": e.message}) from e

    def length_validator_max_wrapper(info, data):
        length_validator = magql.Length(max=15)
        try:
            length_validator(info, data["name"], data)
        except magql.ValidationError as e:
            raise magql.ValidationError({"name": e.message}) from e

    def length_validator_exact_wrapper(info, data):
        length_validator = magql.Length(min=5, max=5)
        try:
            length_validator(info, data["name"], data)
        except magql.ValidationError as e:
            raise magql.ValidationError({"name": e.message}) from e

    UserInputObjectMinMax = magql.InputObject(
        "UserInputMinMax",
        fields={"name": UserInputField},
        validators=[length_validator_min_max_wrapper],
    )

    UserInputObjectMin = magql.InputObject(
        "UserInputMin",
        fields={"name": UserInputField},
        validators=[length_validator_min_wrapper],
    )

    UserInputObjectMax = magql.InputObject(
        "UserInputMax",
        fields={"name": UserInputField},
        validators=[length_validator_max_wrapper],
    )

    UserInputObjectExact = magql.InputObject(
        "UserInputExact",
        fields={"name": UserInputField},
        validators=[length_validator_exact_wrapper],
    )

    info = Mock(spec=GraphQLResolveInfo)

    # Test the input objects with valid data
    data = valid_input
    for UserInputObject in [
        UserInputObjectMinMax,
        UserInputObjectMin,
        UserInputObjectMax,
    ]:
        UserInputObject.validate(info, data)

    # Test the input objects with invalid data (too short)
    data = invalid_input_short
    for UserInputObject, error_message in [
        (UserInputObjectMinMax, "Must be between 2 and 15 characters, but was 1."),
        (UserInputObjectMin, "Must be at least 2 characters, but was 1."),
    ]:
        try:
            UserInputObject.validate(info, data)
        except magql.ValidationError as e:
            assert "name" in e.message
            assert e.message["name"][0] == error_message

    # Test the input objects with invalid data (too long)
    data = invalid_input_long
    for UserInputObject, error_message in [
        (UserInputObjectMinMax, "Must be between 2 and 15 characters, but was 16."),
        (UserInputObjectMax, "Must be at most 15 characters, but was 16."),
    ]:
        try:
            UserInputObject.validate(info, data)
        except magql.ValidationError as e:
            assert "name" in e.message
            assert e.message["name"][0] == error_message

    # Test the input objects with invalid data (not exact)
    data = invalid_input_exact
    error_message = "Must be exactly 5 characters, but was 4."
    try:
        UserInputObjectExact.validate(info, data)
    except magql.ValidationError as e:
        assert "name" in e.message
        assert e.message["name"][0] == error_message

    # Test the input objects with valid data (exact)
    data = valid_input_exact
    UserInputObjectExact.validate(info, data)


def test_length_validator_on_inputField():
    """
    Tests the Length validator specifically for an InputField in a GraphQL schema.
    Creates InputFields, each with a unique Length validator.
    Uses GraphQL mutations to validate the InputFields with data of various lengths.
    The tests verify the correct behaviour of the Length validator in the context of
    GraphQL input fields, by checking if it correctly identifies:
    valid, too short, too long names, and names of exact length.
    """
    UserInputFieldMinMax = magql.InputField(
        "String", validators=[magql.Length(min=2, max=15)]
    )
    UserInputFieldMin = magql.InputField("String", validators=[magql.Length(min=2)])
    UserInputFieldMax = magql.InputField("String", validators=[magql.Length(max=15)])
    UserInputFieldExact = magql.InputField(
        "String", validators=[magql.Length(min=5, max=5)]
    )

    UserInputMinMax = magql.InputObject(
        "UserInputMinMax", fields={"name": UserInputFieldMinMax}
    )
    UserInputMin = magql.InputObject("UserInputMin", fields={"name": UserInputFieldMin})
    UserInputMax = magql.InputObject("UserInputMax", fields={"name": UserInputFieldMax})
    UserInputExact = magql.InputObject(
        "UserInputExact", fields={"name": UserInputFieldExact}
    )

    def resolve_name_field(user, info):
        return user["name"]

    QueryRoot = magql.Object(
        "QueryRoot",
        fields={
            "dummy": magql.Field("String", resolve=lambda obj, info: "dummy"),
        },
    )
    s = magql.Schema()
    s.query = QueryRoot

    User = magql.Object(
        "User",
        fields={
            "nameMin": magql.Field("String", resolve=resolve_name_field),
            "nameMax": magql.Field("String", resolve=resolve_name_field),
            "nameMinMax": magql.Field("String", resolve=resolve_name_field),
            "nameExact": magql.Field("String", resolve=resolve_name_field),
        },
    )

    @s.mutation.field("createUserMin", User, args={"input": UserInputMin})
    @s.mutation.field("createUserMax", User, args={"input": UserInputMax})
    @s.mutation.field("createUserMinMax", User, args={"input": UserInputMinMax})
    @s.mutation.field("createUserExact", User, args={"input": UserInputExact})
    def resolve_create_user(parent, info, input):
        return input

    # Test the mutation with valid data
    valid_name = "John Doe"
    valid_name_exact = "Johny"
    mutation_valid = f"""
        mutation {{
            createUserMin(input: {{ name: "{valid_name}" }}) {{ nameMin }}
            createUserMax(input: {{ name: "{valid_name}" }}) {{ nameMax }}
            createUserMinMax(input: {{ name: "{valid_name}" }}) {{ nameMinMax }}
            createUserExact(input: {{ name: "{valid_name_exact}" }}) {{ nameExact }}
        }}
    """
    result_valid = s.execute(mutation_valid)
    assert not result_valid.errors
    assert result_valid.data == {
        "createUserMin": {"nameMin": valid_name},
        "createUserMax": {"nameMax": valid_name},
        "createUserMinMax": {"nameMinMax": valid_name},
        "createUserExact": {"nameExact": valid_name_exact},
    }

    # Test the mutation with invalid data
    invalid_name_short = "J"
    invalid_name_long = "John" * 4
    invalid_name_exact = "John"
    mutation_invalid = f"""
        mutation {{
            createUserMin(input: {{ name: "{invalid_name_short}" }}) {{ nameMin }}
            createUserMax(input: {{ name: "{invalid_name_long}" }}) {{ nameMax }}
            createUserMinMax(input: {{ name: "{invalid_name_long}" }}) {{ nameMinMax }}
            createUserExact(input: {{ name: "{invalid_name_exact}" }}) {{ nameExact }}
        }}
    """
    result_invalid = s.execute(mutation_invalid)
    error_messages = result_invalid.errors
    assert len(error_messages) == 4
    assert (
        result_invalid.errors[0].extensions["input"][0]["name"][0]
        == "Must be at least 2 characters, but was 1."
    )
    assert (
        result_invalid.errors[1].extensions["input"][0]["name"][0]
        == "Must be at most 15 characters, but was 16."
    )
    assert (
        result_invalid.errors[2].extensions["input"][0]["name"][0]
        == "Must be between 2 and 15 characters, but was 16."
    )
    assert (
        result_invalid.errors[3].extensions["input"][0]["name"][0]
        == "Must be exactly 5 characters, but was 4."
    )


# TODO: FINISH IMPLEMENTATION
# def test_nested_validators():
#     schema = magql.Schema()
# schema.query = magql.Object(
#     "RootQuery",
#     fields={
#         "dummy": magql.Field(
#             "String", resolve=lambda obj, info: "dummy")
#         }
#     )

# user_input = magql.InputObject(
#     name="UserInput",
#     fields=dict(
#         username=magql.InputField(
#             type=magql.String,
#             validators=[magql.Length(3, 8)]
#             ),
#         password=magql.InputField(
#             type=magql.String,
#             validators=[magql.Length(5, 10)]
#             ),
#     ),
#     validators=[magql.Length(4, 10)],
# )

#     user_object = magql.Object(
#         name="User",
#         fields=dict(
#             username=magql.Field(type=magql.String),
#             password=magql.Field(type=magql.String),
#         )
#     )

#     schema.mutation = magql.Object(
#         name="Mutation",
#         fields=dict(
#             createUser=magql.Field(
#                 type=user_object,
#                 args=dict(
#                     user=magql.Argument(
#                         type=user_input,
#                         validators=[magql.Length(6, 12)],
#                     )
#                 ),
#                 resolve=lambda user: user,
#                 validators=[magql.Length(8, 16)],
#             ),
#         ),
#     )

#     mutation = """
#         mutation {
#             createUser(user: {username: "short", password: "longpassword"}) {
#                 username
#                 password
#             }
#         }
#     """

#     result = schema.execute(mutation)

#     # Check that the result contains error messages for each level
#     assert "Must be between 8 and 16 characters, but was 7." in result.errors
#     assert "Must be between 6 and 12 characters, but was 5." in result.errors
#     assert "Must be between 4 and 10 characters, but was 3." in result.errors
#     assert "Must be between 3 and 8 characters, but was 5." in result.errors
#     assert "Must be between 5 and 10 characters, but was 12." in result.errors
