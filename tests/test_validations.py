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

def test_length_validator_on_argument():
    UserArgument = magql.Argument("String")

def test_length_validator_on_inputObject():
    UserInputObject = magql.InputObject("String")

def test_length_validator_on_inputField():
    UserInputField = magql.InputField("String")
