import magql

################################################################################################
def test_length_validator_on_field():
    length_validator = magql.Length(min=2, max=15)

    def resolve_user_field(parent, info):
        value = parent.get("name")
        if not length_validator(value):
            raise Exception(f"Field validation error: {length_validator.message}")
        return value

    UserField = magql.Field("String", resolve=resolve_user_field)

################################################################################################
def test_length_validator_on_argument():
    UserArgumentMinMax = magql.Argument("String", validators=[magql.Length(min=2, max=15)])
    UserArgumentMin = magql.Argument("String", validators=[magql.Length(min=2)])
    UserArgumentMax = magql.Argument("String", validators=[magql.Length(max=15)])

    def resolve_name_field(user, info):
        return user['name']
    
    # Create an Object type for the User
    User = magql.Object(
        "User",
        fields={
            "name": magql.Field("String", resolve=resolve_name_field),
        },
    )

    # Set up a dummy query root
    QueryRoot = magql.Object(
        "QueryRoot",
        fields={
            "dummy": magql.Field("String", resolve=lambda obj, info: "dummy"),
        },
    )

    # Mutation using the UserArgument for validation
    s = magql.Schema()

    # Assign the query root type to the schema
    s.query = QueryRoot

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
    def resolve_create_user(parent, info, name):
        return {"name": name}
    
    # Test the mutation with valid data
    for mutation_name in ["createUserMinMax", "createUserMin", "createUserMax"]:
        mutation = f"""
            mutation {{
                {mutation_name}(name: "John Doe") {{
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

################################################################################################
def test_length_validator_on_inputObject():
    # Define an input object type with a single field that has a length validator
    UserInputMinMax = magql.InputObject(
        "UserInputMinMax",
        fields={
            "name": magql.InputField("String", validators=[magql.Length(min=2, max=15)]),
        },
    )
    UserInputMin = magql.InputObject(
        "UserInputMin",
        fields={
            "name": magql.InputField("String", validators=[magql.Length(min=2)]),
        },
    )
    UserInputMax = magql.InputObject(
        "UserInputMax",
        fields={
            "name": magql.InputField("String", validators=[magql.Length(max=15)]),
        },
    )

    def resolve_name_field(user, info):
        return user['name']
    
    # Create an Object type for the User
    User = magql.Object(
        "User",
        fields={
            "name": magql.Field("String", resolve=resolve_name_field),
        },
    )

    # Set up a dummy query root
    QueryRoot = magql.Object(
        "QueryRoot",
        fields={
            "dummy": magql.Field("String", resolve=lambda obj, info: "dummy"),
        },
    )

    # Mutation using the UserInput for validation
    s = magql.Schema()

    # Assign the query root type to the schema
    s.query = QueryRoot

    @s.mutation.field("createUserMinMax", User, args={"input": UserInputMinMax})
    @s.mutation.field("createUserMin", User, args={"input": UserInputMin})
    @s.mutation.field("createUserMax", User, args={"input": UserInputMax})

    def resolve_create_user(parent, info, input):
        # For simplicity, we'll just return the input as the User object
        return input

    # Test the mutation with valid data
    mutation = """
        mutation {
            createUserMinMax(input: { name: "John Doe" }) {
                name
            }
        }
    """
    result = s.execute(mutation)
    assert result.data == {"createUserMinMax": {"name": "John Doe"}}
    assert not result.errors

    # Test the mutation with invalid data
    mutation = """
        mutation {
            createUserMinMax(input: { name: "J" }) {
                name
            }
        }
    """
    result = s.execute(mutation)
    assert result.errors
    assert result.errors[0].extensions["input"][0]['name'][0] == "Must be between 2 and 15 characters, but was 1."

################################################################################################
def test_length_validator_on_inputField():
    UserInputField = magql.InputField("String")
