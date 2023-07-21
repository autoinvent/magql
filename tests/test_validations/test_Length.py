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


def test_Length_validator_on_Field():
    """
    Tests the Length validator specifically for a Field in a GraphQL schema.
    Creates Fields with varying name lengths, and verifies
    that the Length validator correctly identifies valid and invalid names.
    """
    valid_name = "someField"
    valid_exact_name = "exact"
    invalid_long_name = "thisnameiswaytoolong"
    invalid_short_name = "a"
    invalid_exact_name = "notExact"

    def field_name_validator_min(info, data):
        valid_length = magql.Length(min=2)
        field_name = info.field_name
        valid_length(info, field_name, data)

    def field_name_validator_max(info, data):
        valid_length = magql.Length(max=15)
        field_name = info.field_name
        valid_length(info, field_name, data)

    def field_name_validator_minMax(info, data):
        valid_length = magql.Length(min=2, max=15)
        field_name = info.field_name
        valid_length(info, field_name, data)

    def field_name_validator_exact(info, data):
        valid_length = magql.Length(min=5, max=5)
        field_name = info.field_name
        valid_length(info, field_name, data)

    QueryRoot = magql.Object(
        "QueryRoot",
        fields={
            valid_name: magql.Field(
                "String",
                resolve=lambda obj, info: "valid_name",
                validators=[field_name_validator_minMax],
            ),
            valid_exact_name: magql.Field(
                "String",
                resolve=lambda obj, info: "valid_exact_name",
                validators=[field_name_validator_exact],
            ),
            invalid_long_name: magql.Field(
                "String",
                resolve=lambda obj, info: "invalid_long_name",
                validators=[field_name_validator_max],
            ),
            invalid_short_name: magql.Field(
                "String",
                resolve=lambda obj, info: "invalid_short_name",
                validators=[field_name_validator_min],
            ),
            invalid_exact_name: magql.Field(
                "String",
                resolve=lambda obj, info: "invalid_exact_name",
                validators=[field_name_validator_exact],
            ),
        },
    )

    s = magql.Schema()
    s.query = QueryRoot

    # Test the query with valid field names
    query_valid = f"""
        query {{
            {valid_name}
            {valid_exact_name}
        }}
    """
    result_valid = s.execute(query_valid)
    assert not result_valid.errors
    assert result_valid.data[valid_name] == "valid_name"
    assert result_valid.data[valid_exact_name] == "valid_exact_name"

    # Test the query with invalid field names
    query_invalid = f"""
        query {{
            {invalid_short_name}
            {invalid_long_name}
            {invalid_exact_name}
        }}
    """
    result_invalid = s.execute(query_invalid)
    error_messages = result_invalid.errors
    assert len(error_messages) == 3
    assert (
        error_messages[0].extensions[""][0]
        == "Must be at least 2 characters, but was 1."
    )
    assert (
        error_messages[1].extensions[""][0]
        == f"Must be at most 15 characters, but was {len(invalid_long_name)}."
    )
    assert (
        error_messages[2].extensions[""][0]
        == f"Must be exactly 5 characters, but was {len(invalid_exact_name)}."
    )


def test_Length_validator_on_Argument():
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
        fields={"dummy": magql.Field("String", resolve=lambda obj, info: "dummy")},
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


def test_Length_validator_on_InputObject():
    """
    Tests the Length validator specifically
    for the name of an InputObject in a GraphQL schema.
    Creates InputObjects with varying name lengths, and verifies
    that the Length validator correctly identifies valid and invalid names.
    """
    valid_input = "valid"
    valid_exact_input = "valid_exact"
    invalid_long_input = "invalid_long"
    invalid_short_input = "invalid_short"
    invalid_exact_input = "invalid_exact"

    # the values are not important in this case
    dummy_field = magql.InputField("String", default="DummyValue")

    def input_object_name_validator_min(info, data):
        valid_length = magql.Length(min=15)
        valid_length(info, info.field_name, data)

    def input_object_name_validator_max(info, data):
        valid_length = magql.Length(max=11)
        valid_length(info, info.field_name, data)

    def input_object_name_validator_minMax(info, data):
        valid_length = magql.Length(min=2, max=15)
        valid_length(info, info.field_name, data)

    def input_object_name_validator_exact(info, data):
        valid_length = magql.Length(min=11, max=11)
        valid_length(info, info.field_name, data)

    InputObjectTypeValid = magql.InputObject(
        "valid_name",
        fields={"field": dummy_field},
        validators=[input_object_name_validator_minMax],
    )
    InputObjectTypeValidExact = magql.InputObject(
        "valid_exact_name",
        fields={"field": dummy_field},
        validators=[input_object_name_validator_exact],
    )
    InputObjectTypeInvalidLong = magql.InputObject(
        "invalid_long_name",
        fields={"field": dummy_field},
        validators=[input_object_name_validator_max],
    )
    InputObjectTypeInvalidShort = magql.InputObject(
        "invalid_short_name",
        fields={"field": dummy_field},
        validators=[input_object_name_validator_min],
    )
    InputObjectTypeInvalidExact = magql.InputObject(
        "invalid_exact_name",
        fields={"field": dummy_field},
        validators=[input_object_name_validator_exact],
    )

    QueryRoot = magql.Object(
        "QueryRoot",
        fields={
            "valid": magql.Field(
                "String",
                resolve=lambda obj, info, input: valid_input,
                args={"input": InputObjectTypeValid},
            ),
            "valid_exact": magql.Field(
                "String",
                resolve=lambda obj, info, input: valid_exact_input,
                args={"input": InputObjectTypeValidExact},
            ),
            "invalid_long": magql.Field(
                "String",
                resolve=lambda obj, info, input: "invalid_long",
                args={"input": InputObjectTypeInvalidLong},
            ),
            "invalid_short": magql.Field(
                "String",
                resolve=lambda obj, info, input: "invalid_short",
                args={"input": InputObjectTypeInvalidShort},
            ),
            "invalid_exact": magql.Field(
                "String",
                resolve=lambda obj, info, input: "invalid_exact",
                args={"input": InputObjectTypeInvalidExact},
            ),
        },
    )

    s = magql.Schema()
    s.query = QueryRoot

    # Test the query with valid InputObject names
    query_valid = f"""
        query {{
            {valid_input}(input: {{field: "valid_name"}})
            {valid_exact_input}(input: {{field: "valid_exact_name"}})
        }}
    """
    result_valid = s.execute(query_valid)
    assert not result_valid.errors
    assert "valid" and "valid_exact" in result_valid.data

    # Test the query with invalid InputObject names
    query_invalid = f"""
        query {{
            {invalid_long_input}(input: {{field: "invalid_long"}})
            {invalid_short_input}(input: {{field: "invalid_short"}})
            {invalid_exact_input}(input: {{field: "invalid_exact"}})
        }}
    """
    result_invalid = s.execute(query_invalid)
    error_messages = result_invalid.errors
    assert len(error_messages) == 3
    assert (
        error_messages[0].extensions["input"][0][""][0]
        == "Must be at most 11 characters, but was 12."
    )
    assert (
        error_messages[1].extensions["input"][0][""][0]
        == "Must be at least 15 characters, but was 13."
    )
    assert (
        error_messages[2].extensions["input"][0][""][0]
        == "Must be exactly 11 characters, but was 13."
    )


def test_Length_validator_on_InputField():
    """
    Tests the Length validator specifically for an InputField in a GraphQL schema.
    Creates InputFields, each with a unique Length validator.
    Uses GraphQL mutations to validate the InputFields with data of various lengths.
    The tests verify the correct behaviour of the Length validator in the context of
    GraphQL input fields, by checking if it correctly identifies:
    valid, too short, too long names, and names of exact length.
    """
    valid_name = "John Doe"
    valid_name_exact = "Johny"
    invalid_name_short = "J"
    invalid_name_long = "John" * 4
    invalid_name_exact = "John"

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
        fields={"dummy": magql.Field("String", resolve=lambda obj, info: "dummy")},
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


def test_Length_validator_nested():
    """
    Tests on both an Argument and an InputField in a GraphQL schema.
    Creates an Argument and an InputField, each with a unique Length validator.
    Mutation to validate both the Argument & InputField with various lengths.
    Verifies the correct behaviour of the validator by checking if it identifies:
    valid, too short, too long names, and names of exact length.
    """

    UserArgument = magql.Argument("String", validators=[magql.Length(min=2, max=15)])

    UserInputField = magql.InputField("String", validators=[magql.Length(max=10)])

    UserInput = magql.InputObject("UserInput", fields={"name": UserInputField})

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
            "nameArgument": magql.Field("String", resolve=resolve_name_field),
            "nameInputField": magql.Field("String", resolve=resolve_name_field),
        },
    )

    @s.mutation.field(
        "createUser", User, args={"nameArgument": UserArgument, "input": UserInput}
    )
    def resolve_create_user(parent, info, nameArgument, input):
        return {"nameArgument": nameArgument, "nameInputField": input["name"]}

    # Test the mutation with valid data
    valid_name_argument = "John Doe"
    valid_name_input_field = "Johny"
    mutation_valid = f"""
        mutation {{
            createUser(
                nameArgument: "{valid_name_argument}",
                input: {{ name: "{valid_name_input_field}" }}
            ) {{
                nameArgument
                nameInputField
            }}
        }}
    """
    result_valid = s.execute(mutation_valid)
    assert not result_valid.errors
    assert result_valid.data == {
        "createUser": {
            "nameArgument": valid_name_argument,
            "nameInputField": valid_name_input_field,
        }
    }

    # Test the mutation with invalid data
    invalid_name_argument = "J"
    invalid_name_input_field = "JohnyyJohnyy"
    mutation_invalid = f"""
        mutation {{
            createUser(
                nameArgument: "{invalid_name_argument}",
                input: {{ name: "{invalid_name_input_field}" }}
            ) {{
                nameArgument
                nameInputField
            }}
        }}
    """
    result_invalid = s.execute(mutation_invalid)
    error_messages = result_invalid.errors[0].extensions
    assert len(error_messages) == 2
    assert (
        result_invalid.errors[0].extensions["nameArgument"][0]
        == "Must be between 2 and 15 characters, but was 1."
    )
    assert (
        result_invalid.errors[0].extensions["input"][0]["name"][0]
        == "Must be at most 10 characters, but was 12."
    )
