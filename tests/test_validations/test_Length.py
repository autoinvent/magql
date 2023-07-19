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
        try:
            UserField.validate(info, data)
        except magql.ValidationError as e:
            raise AssertionError(f"Unexpected ValidationError: {e.message}") from e

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
        else:
            raise AssertionError(
                "Expected ValidationError, but no exception was raised."
            )

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
        else:
            raise AssertionError(
                "Expected ValidationError, but no exception was raised."
            )

    # Test the field with invalid data (not exact)
    data = {"name": invalid_name_exact}
    error_message = "Must be exactly 5 characters, but was 4."
    try:
        UserFieldExact.validate(info, data)
    except magql.ValidationError as e:
        assert "name" in e.message
        assert e.message["name"][0] == error_message
    else:
        raise AssertionError("Expected ValidationError, but no exception was raised.")

    # Test the field with valid data (exact)
    data = {"name": valid_name_exact}
    try:
        UserFieldExact.validate(info, data)
    except magql.ValidationError as e:
        raise AssertionError(f"Unexpected ValidationError: {e.message}") from e


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
            "name": magql.Field("String", resolve=resolve_name_field),
        },
    )

    @s.mutation.field(
        "createUserMinMax",
        User,
        args={"name": UserArgumentMinMax},
    )
    @s.mutation.field(
        "createUserMin",
        User,
        args={"name": UserArgumentMin},
    )
    @s.mutation.field(
        "createUserMax",
        User,
        args={"name": UserArgumentMax},
    )
    @s.mutation.field(
        "createUserExact",
        User,
        args={"name": UserArgumentExact},
    )
    def resolve_create_user(parent, info, name):
        return {"name": name}

    # Test the mutation with valid data
    valid_name = "John Doe"
    for mutation_name in ["createUserMinMax", "createUserMin", "createUserMax"]:
        mutation = f"""
            mutation {{
                {mutation_name}(name: "{valid_name}") {{
                    name
                }}
            }}
        """
        result = s.execute(mutation)
        assert result.data == {mutation_name: {"name": "John Doe"}}
        assert not result.errors

    # Test the mutation with invalid data
    for mutation_name, error_message in [
        ("createUserMinMax", "Must be between 2 and 15 characters, but was 1."),
        ("createUserMin", "Must be at least 2 characters, but was 1."),
        ("createUserMax", "Must be at most 15 characters, but was 16."),
    ]:
        invalid_name = "J" if "Min" in mutation_name else "John Doe" * 2
        mutation = f"""
            mutation {{
                {mutation_name}(name: "{invalid_name}") {{
                    name
                }}
            }}
        """
        result = s.execute(mutation)
        assert result.errors
        assert result.errors[0].extensions["name"][0] == error_message

    # Test the mutation with valid data (exact length)
    valid_exact_name = "Johny"
    mutation = f"""
        mutation {{
            createUserExact(name: "{valid_exact_name}") {{
                name
            }}
        }}
    """
    result = s.execute(mutation)
    assert result.data == {"createUserExact": {"name": "Johny"}}
    assert not result.errors

    # Test the mutation with invalid data (exact length)
    invalid_exact_name = "John"
    error_message = "Must be exactly 5 characters, but was 4."
    mutation = f"""
        mutation {{
            createUserExact(name: "{invalid_exact_name}") {{
                name
            }}
        }}
    """
    result = s.execute(mutation)
    assert result.errors
    assert result.errors[0].extensions["name"][0] == error_message


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
    for user_input_object in [
        UserInputObjectMinMax,
        UserInputObjectMin,
        UserInputObjectMax,
    ]:
        try:
            user_input_object.validate(info, data)
        except magql.ValidationError as e:
            raise AssertionError(f"Unexpected ValidationError: {e.message}") from e

    # Test the input objects with invalid data (too short)
    data = invalid_input_short
    for user_input_object, error_message in [
        (UserInputObjectMinMax, "Must be between 2 and 15 characters, but was 1."),
        (UserInputObjectMin, "Must be at least 2 characters, but was 1."),
    ]:
        try:
            user_input_object.validate(info, data)
        except magql.ValidationError as e:
            assert "name" in e.message
            assert e.message["name"][0] == error_message

    # Test the input objects with invalid data (too long)
    data = invalid_input_long
    for user_input_object, error_message in [
        (UserInputObjectMinMax, "Must be between 2 and 15 characters, but was 16."),
        (UserInputObjectMax, "Must be at most 15 characters, but was 16."),
    ]:
        try:
            user_input_object.validate(info, data)
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
    try:
        UserInputObjectExact.validate(info, data)
    except magql.ValidationError as e:
        raise AssertionError(f"Unexpected ValidationError: {e.message}") from e


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
            "name": magql.Field("String", resolve=resolve_name_field),
        },
    )

    @s.mutation.field("createUserMinMax", User, args={"input": UserInputMinMax})
    @s.mutation.field("createUserMin", User, args={"input": UserInputMin})
    @s.mutation.field("createUserMax", User, args={"input": UserInputMax})
    @s.mutation.field("createUserExact", User, args={"input": UserInputExact})
    def resolve_create_user(parent, info, input):
        return input

    # Test the mutation with valid data
    for mutation_name in ["createUserMinMax", "createUserMin", "createUserMax"]:
        mutation = f"""
            mutation {{
                {mutation_name}(input: {{ name: "John Doe" }}) {{
                    name
                }}
            }}
        """
        result = s.execute(mutation)
        assert result.data == {mutation_name: {"name": "John Doe"}}
        assert not result.errors

    # Test the mutation with invalid data
    for mutation_name, error_message in [
        ("createUserMinMax", "Must be between 2 and 15 characters, but was 1."),
        ("createUserMin", "Must be at least 2 characters, but was 1."),
        ("createUserMax", "Must be at most 15 characters, but was 16."),
    ]:
        invalid_name = "J" if "Min" in mutation_name else "John Doe" * 2
        mutation = f"""
            mutation {{
                {mutation_name}(input: {{ name: "{invalid_name}" }}) {{
                    name
                }}
            }}
        """
        result = s.execute(mutation)
        assert result.errors
        assert result.errors[0].extensions["input"][0]["name"][0] == error_message

    # Test the mutation with valid data (exact length)
    valid_name_exact = "Johny"
    mutation = f"""
        mutation {{
            createUserExact(input: {{ name: "{valid_name_exact}" }}) {{
                name
            }}
        }}
    """
    result = s.execute(mutation)
    assert result.data == {"createUserExact": {"name": "Johny"}}
    assert not result.errors

    # Test the mutation with invalid data (exact length)
    invalid_name_exact = "John"
    error_message = "Must be exactly 5 characters, but was 4."
    mutation = f"""
        mutation {{
            createUserExact(input: {{ name: "{invalid_name_exact}" }}) {{
                name
            }}
        }}
    """
    result = s.execute(mutation)
    assert result.errors
    assert result.errors[0].extensions["input"][0]["name"][0] == error_message


# TODO: FINISH IMPLEMENTATION
def test_nested_validators():
    """
    docstring here
    """
    info = Mock(spec=GraphQLResolveInfo)

    def FieldValidatorWrapper(info, data):
        length_validator = magql.Length(min=2, max=10)
        try:
            length_validator(info, data["name"], data)
        except magql.ValidationError as e:
            raise magql.ValidationError({"name": e.message}) from e

    def InputObjectValidatorWrapper(info, data):
        length_validator = magql.Length(max=5)
        try:
            length_validator(info, data["name"], data)
        except magql.ValidationError as e:
            raise magql.ValidationError({"name": e.message}) from e

    # Validator at Field Level
    ##############################################################
    UserField = magql.Field("String", validators=[FieldValidatorWrapper])

    # Validator at Argument Level
    ##############################################################
    argument_validator = magql.Length(min=5)
    UserArgument = magql.Argument("String", validators=[argument_validator])

    # Validator at InputObject Level
    ##############################################################
    UserInputObject = magql.InputObject(
        "UserInput", validators=[InputObjectValidatorWrapper]
    )

    # Validator at InputField Level
    ##############################################################
    input_field_validator = magql.Length(min=5, max=5)
    UserInputField = magql.InputField("String", validators=[input_field_validator])

    # Test behavior violating validators and verify error messages

    # Behavior violating Field Validator
    try:
        UserField.validate(info, {"name": "J"})
    except magql.ValidationError as e:
        assert len(e.message) == 1  # Error message count
        assert e.message["name"][0] == "Must be between 2 and 10 characters, but was 1."

    # Behavior violating Argument Validator
    try:
        UserArgument.validate(info, "Jay", {"name": "Jay"})
    except magql.ValidationError as e:
        assert len(e.message) == 1  # Error message count
        assert e.message[0] == "Must be at least 5 characters, but was 3."

    # Behavior violating InputObject Validator
    try:
        UserInputObject.validate(info, {"name": "JohnDoeJohnDoe"})
    except magql.ValidationError as e:
        assert len(e.message) == 1  # Error message count
        assert e.message["name"][0] == "Must be at most 5 characters, but was 14."

    # Behavior violating InputField Validator
    try:
        UserInputField.validate(info, "JohnDoe", {"name": "JohnDoe"})
    except magql.ValidationError as e:
        assert len(e.message) == 1  # Error message count
        assert e.message[0] == "Must be exactly 5 characters, but was 7."


# UserField_Validator = magql.Length(min=2, max=10)
# UserField = magql.Field("String", validators=[UserField_Validator])
# UserArgument_Validator = magql.Length(min=3, max=11)
# UserArgument = magql.Argument("String", validators=[UserArgument_Validator])
# UserInputObject_Validator = magql.Length(min=4, max=12)
# UserInputObject = magql.InputObject("String", validators=[UserInputObject_Validator])
# UserInputField_Validator = magql.Length(min=5, max=5)
# UserInputField = magql.InputField("String", validators=[UserInputField_Validator])
