from functools import singledispatch

from inflection import camelize
from sqlalchemy import Boolean
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import Time
from sqlalchemy import Unicode
from sqlalchemy import UnicodeText
from sqlalchemy import VARCHAR
from sqlalchemy_utils import ChoiceType
from sqlalchemy_utils import EmailType
from sqlalchemy_utils import JSONType
from sqlalchemy_utils import PhoneNumberType
from sqlalchemy_utils import URLType

from .definitions import MagqlBoolean
from .definitions import MagqlEnumType
from .definitions import MagqlFloat
from .definitions import MagqlInt
from .definitions import MagqlNonNull
from .definitions import MagqlString
from .filter import BooleanFilter
from .filter import DateFilter
from .filter import EnumFilter
from .filter import FloatFilter
from .filter import IntFilter
from .filter import StringFilter


@singledispatch
def _get_magql_type(type_, column):
    """
    Returns the corrsponding GraphQL type to the given SQLA column type
    :param type: The type of the SQLA column
    :return: The corresponding GraphQL type
    """
    raise TypeError(
        "No type registered for column type"
        f" {type_.__class__.__name__!r} from {column!r}."
    )


def get_magql_type(col):
    return _get_magql_type(col.type, col)


def is_required(col):
    """
    Checks whether a scalar SQLAlchemy column is required or not
    :param col: SQLAlchemy column
    :return: Whether or not the column is required
    """
    return not col.nullable and not col.default and not col.primary_key


def get_magql_required_type(col):
    type_ = get_magql_type(col)
    if is_required(col):
        return MagqlNonNull(type_)
    else:
        return type_


@_get_magql_type.register(JSON)
@_get_magql_type.register(JSONType)
@_get_magql_type.register(DateTime)
@_get_magql_type.register(Text)
@_get_magql_type.register(Date)
@_get_magql_type.register(UnicodeText)
@_get_magql_type.register(Unicode)
@_get_magql_type.register(URLType)
@_get_magql_type.register(PhoneNumberType)
@_get_magql_type.register(EmailType)
@_get_magql_type.register(Time)
@_get_magql_type.register(String)
@_get_magql_type.register(VARCHAR)
def _get_string_type(type, column):
    # if "image" in column.info:
    #     return MagqlFile()
    return MagqlString()


@_get_magql_type.register(Boolean)
def _get_boolean_type(type, column):
    return MagqlBoolean()


@_get_magql_type.register(Integer)
def _get_integer_type(type, column):
    return MagqlInt(MagqlInt.parse_value_accepts_string)


@_get_magql_type.register(Float)
@_get_magql_type.register(Numeric)
def _get_float_type(type, column):
    return MagqlFloat(MagqlFloat.parse_value_accepts_string)


@_get_magql_type.register(ChoiceType)
def _get_choice_type(type_, column):
    # name = camelize(column.table.name) + camelize(column.name) + "EnumType"
    # enums = dict((key, value) for key, value in type.choices)
    # rm = GraphQLEnumType(name, enums)
    # return rm
    name = camelize(column.table.name) + camelize(column.name) + "EnumType"
    enums = {key: key for key, value in type_.choices}
    return MagqlEnumType(name, enums)


def get_magql_filter_type(type_, base_type):
    return _get_magql_filter_type(type_.type, base_type)


@singledispatch
def _get_magql_filter_type(column, base_type):
    """
    Returns the filter based on the given type
    :param type: The type of the SQLAlchemy column
    :return:  The Autogenerated GraphQL filter object
    """
    raise TypeError(
        f"No filter registered for column type {column.__class__.__name__!r}."
    )


@_get_magql_filter_type.register(JSON)
@_get_magql_filter_type.register(JSONType)
@_get_magql_filter_type.register(DateTime)
@_get_magql_filter_type.register(Text)
@_get_magql_filter_type.register(Date)
@_get_magql_filter_type.register(UnicodeText)
@_get_magql_filter_type.register(Unicode)
@_get_magql_filter_type.register(URLType)
@_get_magql_filter_type.register(PhoneNumberType)
@_get_magql_filter_type.register(EmailType)
@_get_magql_filter_type.register(Time)
@_get_magql_filter_type.register(String)
@_get_magql_filter_type.register(VARCHAR)
def _get_string_filter(type, base_type):
    return StringFilter


@_get_magql_filter_type.register(Date)
@_get_magql_filter_type.register(DateTime)
def _get_date_filter(type, base_type):
    return DateFilter


@_get_magql_filter_type.register(Integer)
def _get_integer_filter(type, base_type):
    return IntFilter


@_get_magql_filter_type.register(Float)
@_get_magql_filter_type.register(Numeric)
def _get_float_filter(type, base_type):
    return FloatFilter


@_get_magql_filter_type.register(Boolean)
def _get_boolean_filter(type, base_type):
    return BooleanFilter


@_get_magql_filter_type.register(ChoiceType)
def _get_choice_filter(type_, base_type):
    return EnumFilter(base_type)
