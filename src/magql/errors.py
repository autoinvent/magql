from __future__ import annotations

import typing as t


class ValidationFailedError(Exception):
    def __init__(self, errors: t.Union[t.List, t.Any]):
        if not isinstance(errors, list):
            errors = [errors]
        self.errors = errors


class AuthorizationError(Exception):
    def __init__(self, errors: t.Union[t.List, t.Any]):
        if not isinstance(errors, list):
            errors = [errors]
        self.errors = errors
