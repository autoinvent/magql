class ValidationFailedError(Exception):
    def __init__(self, errors):
        if not isinstance(errors, list):
            errors = [errors]
        self.errors = errors


class AuthorizationError(Exception):
    def __init__(self, errors):
        if not isinstance(errors, list):
            errors = [errors]
        self.errors = errors
