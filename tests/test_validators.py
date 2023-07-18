import magql


def run_test(
    mutation_name,
    input_object,
    id,
    name,
    age=None,
    password=None,
    confirm_password=None,
    expected_error=None,
    error_field=None,
):
    """
    Run a test case for a GraphQL mutation.

    This function sets up a GraphQL schema with a User type
    and a mutation that creates a user. It then runs a mutation query
    with the given arguments and validates the result.
    If an error is expected,
    it checks that the error message matches the expected error.

    params:
        mutation_name: The name of the mutation to run.
        input_object: The input object type for the mutation.
        id: The ID of the object to mutate.
        name: The name of the object to mutate.
        age: The age of the object to mutate (Optional).
        password: The password of the object to mutate (Optional).
        confirm_password: The password confirmation of the object (Optional).
        expected_error: The expected error message (Optional).
        error_field: The field where the error is expected (Optional).
    """
    user_data = {}

    def resolve_name(obj, info):
        return obj.get("name")

    def resolve_age(obj, info):
        return obj.get("age")

    def resolve_password(obj, info):
        return obj.get("password")

    User = magql.Object(
        "User",
        fields={
            "name": magql.Field("String", resolve=resolve_name),
            "age": magql.Field("Int", resolve=resolve_age),
            "password": magql.Field("String", resolve=resolve_password),
        },
    )

    s = magql.Schema()

    # To provide query root type
    @s.query.field(
        "User",
        User,
        args={"id": magql.Argument(magql.Int)},
    )
    @s.mutation.field(
        mutation_name,
        User,
        args={"input": magql.Argument(input_object)},
    )
    def resolve_create_user(parent, info, input):
        id = input["id"]
        name = input["name"]
        password = input.get("password")
        user_data[id] = {"name": name}

        if "age" in input:
            age = input["age"]
            user_data[id].update({"age": age})

        if password:
            user_data[id].update({"password": password})

        return user_data[id]

    mutation = f"""
        mutation {{
            {mutation_name}(input: {{id: {id}, name: "{name}"}}) {{
                name
            }}
        }}
    """
    if age is not None:
        mutation = f"""
            mutation {{
                {mutation_name}(input: {{id: {id}, name: "{name}", age: {age}}}) {{
                    name
                    age
                }}
            }}
        """
    if password is not None and confirm_password is not None:
        mutation = f"""
            mutation {{
                {mutation_name}(input: {{
                    id: {id}, name: "{name}", password: "{password}",
                    confirm_password: "{confirm_password}"
                }}) {{
                    name
                    password
                }}
            }}
        """

    result = s.execute(mutation)

    if expected_error:
        error_message = result.errors[0].extensions["input"][0][error_field][0]
        assert expected_error in error_message
    else:
        assert not result.errors
        expected_data = {"name": name}
        if age is not None:
            expected_data["age"] = age
        if password is not None:
            expected_data["password"] = password
        assert result.data == {mutation_name: expected_data}


def test_length_validator():
    """
    Run test cases for the Length validator.

    This function tests the Length validator
    with various input lengths and expected outcomes.
    It creates input objects with name fields
    of various lengths and runs a mutation query for each,
    checking that the outcome matches the expected result.
    """
    UserInput = magql.InputObject(
        "UserInput",
        fields={
            "id": magql.InputField("Int"),
            "name": magql.InputField(
                "String", validators=[magql.Length(min=2, max=15)]
            ),
        },
    )
    run_test("createUser", UserInput, 1, "Bob")
    run_test(
        "createUser",
        UserInput,
        2,
        "B",
        expected_error="Must be between 2 and 15 characters, but was 1.",
        error_field="name",
    )
    run_test(
        "createUser",
        UserInput,
        3,
        "Very-Long-Invalid-Name",
        expected_error="Must be between 2 and 15 characters",
        error_field="name",
    )

    UserInputMin = magql.InputObject(
        "UserInputMin",
        fields={
            "id": magql.InputField("Int"),
            "name": magql.InputField("String", validators=[magql.Length(min=2)]),
        },
    )
    run_test(
        "createUserMin",
        UserInputMin,
        4,
        "A",
        expected_error="Must be at least 2 characters, but was 1.",
        error_field="name",
    )

    UserInputMax = magql.InputObject(
        "UserInputMax",
        fields={
            "id": magql.InputField("Int"),
            "name": magql.InputField("String", validators=[magql.Length(max=15)]),
        },
    )
    run_test(
        "createUserMax",
        UserInputMax,
        5,
        "Very-Long-Invalid-Name",
        expected_error="Must be at most 15 characters",
        error_field="name",
    )

    UserInputEqual = magql.InputObject(
        "UserInputEqual",
        fields={
            "id": magql.InputField("Int"),
            "name": magql.InputField("String", validators=[magql.Length(min=3, max=3)]),
        },
    )
    run_test(
        "createUserEqual",
        UserInputEqual,
        6,
        "Short",
        expected_error="Must be exactly 3 characters, but was 5.",
        error_field="name",
    )


def test_number_range_validator():
    """
    Run test cases for the NumberRange validator.

    This function tests the NumberRange validator
    with various input numbers and expected outcomes.
    It creates input objects with age fields of various
    values and runs a mutation query for each,
    checking that the outcome matches the expected result.
    """
    UserInput = magql.InputObject(
        "UserInput",
        fields={
            "id": magql.InputField("Int"),
            "name": magql.InputField("String"),
            "age": magql.InputField(
                "Int", validators=[magql.NumberRange(min=18, max=65)]
            ),
        },
    )
    run_test("createUserAge", UserInput, 1, "Bob", 25)
    run_test(
        "createUserAge",
        UserInput,
        2,
        "Bob",
        16,
        expected_error="Must be between 18 and 65",
        error_field="age",
    )
    run_test(
        "createUserAge",
        UserInput,
        3,
        "Bob",
        70,
        expected_error="Must be between 18 and 65",
        error_field="age",
    )

    UserInputMin = magql.InputObject(
        "UserInputMin",
        fields={
            "id": magql.InputField("Int"),
            "name": magql.InputField("String"),
            "age": magql.InputField("Int", validators=[magql.NumberRange(min=18)]),
        },
    )
    run_test(
        "createUserAgeMin",
        UserInputMin,
        4,
        "Bob",
        16,
        expected_error="Must be at least 18",
        error_field="age",
    )

    UserInputMax = magql.InputObject(
        "UserInputMax",
        fields={
            "id": magql.InputField("Int"),
            "name": magql.InputField("String"),
            "age": magql.InputField("Int", validators=[magql.NumberRange(max=65)]),
        },
    )
    run_test(
        "createUserAgeMax",
        UserInputMax,
        5,
        "Bob",
        70,
        expected_error="Must be at most 65",
        error_field="age",
    )


def test_confirm_validator():
    """
    Run test cases for the Confirm validator.

    This function tests the Confirm validator
    with various input strings and expected outcomes.
    It creates input objects with password and
    confirm_password fields and runs a mutation query for each,
    checking that the outcome matches the expected result.
    """
    UserInput = magql.InputObject(
        "UserInput",
        fields={
            "id": magql.InputField("Int"),
            "name": magql.InputField("String"),
            "password": magql.InputField("String"),
            "confirm_password": magql.InputField(
                "String", validators=[magql.Confirm("password")]
            ),
        },
    )
    run_test(
        "createUserPassword",
        UserInput,
        1,
        "Bob",
        password="secret",
        confirm_password="secret",
    )
    run_test(
        "createUserPassword",
        UserInput,
        2,
        "Bob",
        password="secret",
        confirm_password="not_secret",
        expected_error="Must equal the value given in 'password'",
        error_field="confirm_password",
    )
