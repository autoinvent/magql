"""
This is an example of how unique constraint validation may be setup.

Fields are camelcase & returned w/ specific format to be interpreted by conveyor.

Use as a guide for writing your own validation.
"""

import json
import inflection


def unique_constraint_error(group):
    return {
        "group": [
            # get field names in proper camel-case format
            inflection.camelize(value, uppercase_first_letter=False) for value in group
        ],
        # frontend "conveyor-redux" will interpret this type and create the appropriate message
        "type": "UNIQUE_CONSTRAINT",
    }


class UniqueConstraint:

    def __init__(self, fields, error=unique_constraint_error):
        """
        :param fields: tuple (field2, field2) or (field1,)
        """
        self.fields = fields
        self.error = error

    def __call__(self, model, input_dict, instance, **kwargs):
        errors_dict = {}
        query = model.query

        for f in self.fields:

            if input_dict.get(f, False) is None:
                return {}

            if f not in input_dict and getattr(instance, f, None) is None:
                # only check instance.f if 'f' is not in input_dict
                return {}

            if f in input_dict.keys():
                query = query.filter(getattr(model, f) == input_dict[f])
            elif instance is not None:
                query = query.filter(getattr(model, f) == getattr(instance, f))

        if query.count() != 0:
            for f in self.fields:

                # errors don't count if fields are not changing.
                # if multiple sets of fields are checked per model, validation
                # may be running on fields not in 'input_dict'. avoid a situation
                # where model queries itself and give false positive error
                if f in input_dict.keys():
                    if f in errors_dict:
                        errors_dict[f].extend([self.error(self.fields)])
                    else:
                        errors_dict[f] = [self.error(self.fields)]

        return errors_dict


class MutationValidation:
    """
    Create an Instance of a MutationValidation object:

        Foo = UniqueConstraint(fields=('A',))
        Bar = UniqueConstraint(fields=('a', 'b', 'c'))

        validation = MutationValidation(
                    model=Book,
                    valid_list=[Foo, Bar],
                )

    When you need to validate an input:

        validation(**kwargs)

    ... where **kwargs = {input: { someField: value }, id: '3'}.
    'id' only exists for update operations.

    This class will find errors and raise an Exception. The resulting
    errors have the following format, where the field name is camel case:

        { 'someField' : ['List', 'Of', 'Errors'] }

    Validators (classes in valid_list) are custom written like so:

        class Foo:
            __call__(self, model, input_dict, instance, **kwargs):
                return errors_dict

    ... where 'errors_dict' has the following format, with the field name in snake case:

        { 'some_field' : ['List of errors'] }

    """

    def __init__(self, db, model, valid_list, continue_on_error=True):
        """
        :param db: object; reference to the database
        :param model: object; model being validated
        :param valid_list: list of validator classes, evaluated in that order
        :param continue_on_error: continue validating if error occurs
        """
        self.db = db
        self.model = model
        self.valid_list = valid_list
        self.continue_on_error = continue_on_error
        self.errors = {}

    def __call__(self, **kwargs):
        input_dict = kwargs["input"]

        if kwargs.get("id"):
            kwargs["instance"] = self.db.session.query(self.model).get(kwargs.get("id"))
        else:
            kwargs["instance"] = None

        self.errors = {}
        self._validate(input_dict, **kwargs)
        self._prep_errors()
        self._raise_error()

    def _add_errors(self, errors_dict):
        for k, v in errors_dict.items():
            if k in self.errors:
                self.errors[k].extend(v)
            else:
                self.errors[k] = v

    def _validate(self, input_dict, **kwargs):
        for valid in self.valid_list:
            e = valid(self.model, input_dict, **kwargs)
            self._add_errors(e)
            if (not self.continue_on_error) and e:
                break

    def _prep_errors(self):
        self.errors = dict(
            ((inflection.camelize(key, uppercase_first_letter=False)), value)
            for (key, value) in self.errors.items()
        )

    def _raise_error(self):
        if self.errors:
            raise Exception(json.dumps(self.errors))
