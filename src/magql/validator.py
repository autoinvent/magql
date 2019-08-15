from collections import defaultdict

from marshmallow_sqlalchemy import field_for

validator_overrides = defaultdict(lambda: {})


def get_validator_overrides(model):
    return validator_overrides[model].copy()


def validator(model, field_name):
    def validator_decorator(validator_function):
        # tuple key/ value pair or nested?
        validator_overrides[model][field_name] = field_for(
            model, field_name, validate=validator_function
        )

        def validate(*args, **kwargs):
            return validator_function(*args, **kwargs)

        return validate

    return validator_decorator


class ValidationFailedError(Exception):
    def __init__(self, errors):
        if not isinstance(errors, list):
            errors = [errors]
        self.errors = errors
