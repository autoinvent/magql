import logging

from inflection import underscore
from sqlalchemy import func
from sqlalchemy.orm import lazyload
from sqlalchemy.orm import subqueryload
from sqlalchemy_utils import ChoiceType
from sqlalchemy_utils import get_mapper

from .errors import AuthorizationError
from .errors import ValidationFailedError
from .filter import generate_filters
from .sort import generate_sorts


def js_underscore(word):
    # add config
    return underscore(word)


class Resolver:
    """
    The super class for all builtin CRUD magql resolvers. Establishes
    the call order of the resolve functions. Resolve is broken down into
    3 main sections, :func:`pre-resolve`, :func:`resolve`, and
    :func:`post-resolve`. :func:`re-resolve` allows modification of the
    arguments that will be passed to :func:`resolve`. :func:`resolve`
    is broken down into 4 sections, :func:`retrieve_value`, :func:`authorize`,
    :func:`validate`, and :func:`mutate`. :func:`resolve` returns a value
    that can be modified by :func:`post_resolve`, which can perform side
    effects such as commiting the session. The order of these functions
    is the suggested way of organizing the resolve order such that overriding
    and/or extending the functionality is easiest.
    """

    def __call__(self, parent, info, *args, **kwargs):
        """
        Default resolve method, establishes and executes the default
        resolve flow
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        :return: the resolved value that is returned to GraphQL
        """
        parent, info, args, kwargs = self.pre_resolve(parent, info, *args, **kwargs)
        try:
            resolved_value = self.resolve(parent, info, *args, **kwargs)
        except ValidationFailedError as validation_errors:
            return {"errors": list(validation_errors.args)}
        except AuthorizationError as authorize_errors:
            return {"errors": list(authorize_errors.args)}
        post_resolved_value = self.post_resolve(
            resolved_value, parent, info, *args, **kwargs
        )
        return post_resolved_value

    def pre_resolve(self, parent, info, *args, **kwargs):
        """
        Allows for modification of the passed parameters
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        :return: the parameters that will be passed to :func:`resolve`
        """
        return parent, info, args, kwargs

    def post_resolve(self, resolved_value, parent, info, *args, **kwargs):
        """
        Allows for modification of the returned value to GraphQl and
        performing of side effects
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        :return: The value to be returned to GraphQL
        """
        return resolved_value

    def authorize(self, instance, parent, info, *args, **kwargs):
        """
        Provides a space to perform authorization. Raise an AuthError
        to stop execution and have the resolve method return an error
        message based on the string error in the error object
        :param instance: The value returned by :func:`retrieve_value`
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        """
        return None

    def validate(self, instance, parent, info, *args, **kwargs):
        """
        Provides a space to perform validation. Raise an ValidationError
        to stop execution and have the resolve method return an error
        message based on the string error in the error object
        :param instance: The value returned by :func:`retrieve_value`
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        """
        return None

    def mutate(self, value, parent, info, *args, **kwargs):
        """
        Provides a space to mutate the resolved value. Necessarily will
        do nothing in queries.
        :param value: The value returned by
        :func:`retrieve_value`
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        :return: the value that will be returned to GraphQL
        """
        return value

    def retrieve_value(self, parent, info):
        """
        Retrieves (or creates) the value that the resolver will operate
        on and return. By default performs dot operation on the parent
        object using the field_name parameter of the info dict
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        :return: the value that will be operated on and returned to GraphQL
        """
        return getattr(parent, underscore(info.field_name))

    def resolve(self, parent, info, *args, **kwargs):
        """
        Establishes the call order of the resolve sub_functions
        :func:`retrieve_value`, :func:`authorize`, :func:`validate`,
        and :func:`mutate`. When subclassing, define one of these
        subfunctions to overwrite or extend the functionality in a
        granular manner. To override functionality in a more major way
        define a new resolve function to perform desired behavior.
        :param parent: gql parent. is whatever was returned by the
        parent resolver
        :param info: gql info dictionary
        :return: The value to be returned to GraphQL
        """
        value = self.retrieve_value(parent, info, *args, **kwargs)

        self.authorize(value, parent, info, *args, **kwargs)

        self.validate(value, parent, info, *args, **kwargs)

        value = self.mutate(value, parent, info, *args, **kwargs)

        return value


class ResultResolver:
    """
    Result Resolver retrieves the result key off of the payload object
    :param parent: GraphQL Payload object
    :param info: gql info dictionary
    :return: The results field on the payload object
    """

    def __call__(self, parent, info, *args, **kwargs):
        return parent


class CountResolver:
    def __call__(self, parent, info, *args, **kwargs):
        return info.context.info.get("count")


class CamelResolver:
    """
    Identical to graphql's default_field_resolver except the field_name
    is converted to snake case
    :param parent: gql parent. is whatever was returned by the
    parent resolver
    :param info: gql info dictionary
    :return: The value to be returned to GraphQL
    """

    def __call__(self, parent, info, *args, **kwargs):
        source = parent
        # TODO: Look into a way to generate info
        #  dictionary so the code does not need to be
        # copied or circumvent all together in a different way
        field_name = underscore(info.field_name)
        value = (
            source.get(field_name)
            if isinstance(source, dict)
            else getattr(source, field_name, None)
        )
        if callable(value):
            return value(info, **args)
        return value


class CheckDeleteResolver:
    """
    Resolver for the function that checks to see what will be deleted
    """

    def __init__(self, tables):
        self.tables = tables

    def __call__(self, parent, info, *args, **kwargs):
        for table in self.tables:
            try:
                class_ = get_mapper(table).class_
            except ValueError:
                continue
            # TODO: switch over frontend to class name
            if class_.__name__ == kwargs["tableName"]:
                id_ = kwargs["id"]
                session = info.context
                instance = session.query(class_).filter_by(id=id_).one()
                session.delete(instance)
                cascades = []
                for obj in session.deleted:
                    cascades.append(obj)

                session.rollback()

                return cascades


class SQLAlchemyTableUnionResolver:
    """
    Resolver that determines which type is being return from the delete check.
    This resolver is tied to the use of sqlalchemy
    """

    def __init__(self, magql_name_to_table):
        self.magql_name_to_table = magql_name_to_table

    def __call__(self, parent, info, *args, **kwargs):
        for magql_name, table in self.magql_name_to_table.items():
            if isinstance(parent, get_mapper(table).class_):
                for gql_type in info.return_type.of_type.types:
                    if gql_type.name == magql_name:
                        return gql_type
        raise Exception("Type not found")


class EnumResolver(Resolver):
    def retrieve_value(self, parent, info):
        """
        Resolve Enums which need to get the code from the value
        :param parent: gql parent. is whatever was returned by
        the parent resolver
        :param info: gql info dictionary
        :return: getattr(parent, info.field_Name)
        """
        if not parent:
            return None
        field_name = underscore(info.field_name)
        return getattr(getattr(parent, field_name), "code", None)


class TableResolver(Resolver):  # noqa: B903
    """
    A subclass of :class:`Resolver` that adds a table so that it can be
    reused in :class:`QueryResolver` and :class:`MutationResolver`.
    """

    def __init__(self, table):
        """
        MutationResolver can be overriden by
        :param table: a sqlalchemy table
        """
        self.table = table
        self.table_class = get_mapper(table).class_
        super().__init__()


class MutationResolver(TableResolver):
    """
    Subclass of :class:`TableResolver`. Initialized with a schema for
    validating the inputs. Its resolve method will call its validate
    method and return either the requested data of the changed object
    or an error dict filled with errors.
    """

    # def __call__(self, parent, info, *args, **kwargs):
    #     """
    #     Checks if a schema has been set and if so validates the mutation.
    #     Otherwise it just resolves the mutation.
    #     :param parent: parent object required by GraphQL, always None because
    #     mutations are always top level.
    #     :param info: GraphQL info dictionary
    #     :param args: Not used in automatic generation but left in in case
    #     overriding the validate or call methods.
    #     :param kwargs: Holds user inputs.
    #     :return:
    #     """
    #     return super(MutationResolver, self).__call__(parent, info, *args, **kwargs)

    def input_to_instance_values(self, input, mapper, session):
        """
        Helper method that converts the values in the input into values
        that can be passed into the creation of the instance. This
        returns scalars as themselves and passed id's as an object or
        list of objects that can be set in the creation call.
        :param input: The user's input dictionary containing the fields
        that are desired to be created.
        :param mapper: The mapper for the table that is being created
        :param session: The SQLAlchemy session
        :return: A dict of field names to values that will be added/changed on
        the newly created/modified object.
        """
        instance_values = {}
        for key, value in input.items():
            key = underscore(key)
            if key in mapper.c:
                col_type = mapper.c[key].type
                if isinstance(col_type, ChoiceType):
                    for enum_tuple in col_type.choices:
                        if value == enum_tuple[1]:
                            value = enum_tuple[0]
                            break
            if key in mapper.relationships:
                target = get_mapper(mapper.relationships[key].target).class_
                query = session.query(target)
                if value:
                    if isinstance(value, list):
                        value = query.filter(target.id.in_(value)).all()
                    else:
                        value = query.filter(target.id == value).one()
            instance_values[key] = value
        return instance_values

    # Post resolve will add and commit the created value
    def post_resolve(self, resolved_value, parent, info, *args, **kwargs):
        """
        Adds and commits the mutated value to the session
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        :return: The value to be returned to GraphQL
        """
        session = info.context
        session.add(resolved_value)
        session.commit()
        return resolved_value


class ModelInputResolver(MutationResolver):
    def pre_resolve(self, parent, info, *args, **kwargs):
        """
        Converts ids of rels to actual values and handles enums
        :param parent: parent object required by GraphQL, always None because
        mutations are always top level.
        :param info: GraphQL info dictionary
        :param args: Not used in automatic generation but left in in case
        overriding the validate or call methods.
        :param kwargs: Holds user inputs.
        :return: The modified arguments
        """
        session = info.context
        mapper = get_mapper(self.table)
        kwargs["input"] = self.input_to_instance_values(
            kwargs["input"], mapper, session
        )

        return parent, info, args, kwargs


class CreateResolver(ModelInputResolver):
    """
    A subclass of :class:`MutationResolver`. Takes a dict of field values
    as input and creates an instance of the associated table with those
    fields.
    """

    def retrieve_value(self, parent, info, *args, **kwargs):
        """
        Creates an empty row in the table that will be modified by mutate.
        :param parent: parent object required by GraphQL, always None because
        mutations are always top level.
        :param info: GraphQL info dictionary
        :param args: Not used in automatic generation but left in in case
        overriding the validate or call methods.
        :param kwargs: Holds user inputs.
        :return: The instance with newly modified values
        """
        mapper = get_mapper(self.table)

        # TODO: Replace with dictionary spread operator
        instance = mapper.class_()
        return instance

    def mutate(self, instance, parent, info, *args, **kwargs):
        """
        Updates the passed instance to have the values specified
        in the query arguments
        :param value: The value returned by
        :func:`retrieve_value`
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        :return: the newly created value that will be returned to GraphQL
        """
        for key, value in kwargs["input"].items():
            setattr(instance, key, value)
        return instance


class UpdateResolver(ModelInputResolver):
    """
    A subclass of :class:`MutationResolver`. Takes a dict of field values
    and an id as input and updates the instance specified by id with
    fields specified by fields.
    """

    def retrieve_value(self, parent, info, *args, **kwargs):
        """
        Updates the instance of the associated table with the id passed.
        Performs setattr on the key/value pairs.
        :param parent: parent object required by GraphQL, always None because
        mutations are always top level.
        :param info: GraphQL info dictionary
        :param args: Not used in automatic generation but left in in case
        overriding the validate or call methods.
        :param kwargs: Holds user inputs.
        :return: The instance with newly modified valuesf
        """
        session = info.context
        mapper = get_mapper(self.table)

        id_ = kwargs["id"]
        return session.query(mapper.class_).filter_by(id=id_).one()

    def mutate(self, instance, parent, info, *args, **kwargs):
        """
        Updates the passed instance to have the values specified
        in the query arguments
        :param value: The value returned by
        :func:`retrieve_value`
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        :return: the updated value that will be returned to GraphQL
        """
        for key, value in kwargs["input"].items():
            setattr(instance, key, value)
        return instance


class DeleteResolver(MutationResolver):
    """
    A subclass of :class:`MutationResolver`. Takes an id and deletes
    the instance specified by id.
    """

    def retrieve_value(self, parent, info, *args, **kwargs):
        """
        Retrieves the row in the table that matches the id in the args,
        if such a row exists
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        :return: the value that will be operated on and returned to GraphQL,
        in this case the row with id matching the requested id
        """
        session = info.context
        mapper = get_mapper(self.table)
        id_ = kwargs["id"]
        return session.query(mapper.class_).filter_by(id=id_).one()

    def mutate(self, instance, parent, info, *args, **kwargs):
        """
        Deletes the passed instance from the session
        :param value: The value returned by
        :func:`retrieve_value`
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        :return: the value that was deleted
        """
        session = info.context
        session.delete(instance)
        return instance

    def post_resolve(self, resolved_value, parent, info, *args, **kwargs):
        """
        Deletes the value from the session and commits the deletion
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        :return: The value to be returned to GraphQL, in this case the
        deleted value
        """
        session = info.context
        session.delete(resolved_value)
        session.commit()
        return resolved_value


class QueryResolver(TableResolver):
    """
    A subclass of :class:`TableResolver`, the super class for
    :class:`SingleResolver` and :class:`ManyResolver`
    """

    def generate_query(self, info):
        """
        Generates a basic query based on the mapped class
        :param info: GraphQL info dict, used to hold the SQLA session
        :return: A SQLAlchemy query based on the mapped class,
        session.query(ModelClass)
        """
        session = info.context
        mapper = get_mapper(self.table)
        return session.query(mapper.class_)


class SingleResolver(QueryResolver):
    """
    A subclass of :class:`QueryResolver`. Takes an id and queries for
    the instance specified by id.
    """

    def post_resolve(self, resolved_value, parent, info, *args, **kwargs):
        return resolved_value if resolved_value else {"result": resolved_value}

    def retrieve_value(self, parent, info, *args, **kwargs):
        """
        Retrieves the row in the table that matches the id in the args,
        if such a row exists
        :param parent: gql parent. The value returned by the
        parent resolver. See GraphQL docs for more info
        :param info: GraphQL info dictionary, see GraphQL docs for more
        info
        :return: the value that will be operated on and returned to GraphQL,
        in this case the row with id matching the requested id
        """
        query = self.generate_query(info)
        return query.filter_by(id=kwargs["id"]).one_or_none()


class ManyResolver(QueryResolver):
    """
    A subclass of :class:`QueryResolver`. By default queries for all
    instances of the table that it is associated with. Can be filtered and
    sorted with keyword args.
    """

    def get_count(self, q):
        count_func = func.count()
        count_q = (
            q.options(lazyload("*"))
            .statement.with_only_columns([count_func])
            .order_by(None)
        )
        return q.session.execute(count_q).scalar()

    def generate_subqueryloads(self, field_node, load_path=None):
        """
        A helper function that allows the generation of the top level
        query to only have to perform one query with subqueryloads to
        eager load the data that will be accessed due to the structure
        of the query. Recursively builds a list of subquery loads
        that are applied to the base query.
        :param field_node: The document ast node that is used to determine
        what relationships are accessed by the query
        :param load_path: The load path that should be appended to
        in order to build the correct subquery
        :return:  A list of all subqueries needed to eagerly load
        all data accessed as a result of the query
        """
        options = []

        # A node is a lead if all of its children are scalars
        for selection in field_node.selection_set.selections:
            # selections with no sub selection_sets are scalars
            if selection.selection_set is None:
                continue
            field_name = js_underscore(selection.name.value)

            if field_name not in get_mapper(self.table).relationships:
                continue

            if load_path is None:
                extended_load_path = subqueryload(field_name)
            else:
                extended_load_path = load_path.subqueryload(field_name)
            options = options + self.generate_subqueryloads(
                selection, extended_load_path
            )

        # if all children are leaves then this is the last node,
        if len(options) == 0:
            return [load_path] if load_path is not None else []
        return options

    def generate_query(self, info):
        """
        Generates a query based on the document ast
        :param info: GraphQL info dict.
        :return: A SQLAlchemy query with any needed subquery loads
        appended
        """
        field_name = info.field_name
        field_node = [
            selection
            for selection in info.operation.selection_set.selections
            if selection.name.value == field_name
        ]
        if len(field_node) != 1:
            logging.getLogger(__name__).warning(
                f"Duplicate queries defined for {field_name!r}."
            )
        options = self.generate_subqueryloads(field_node[0])
        query = QueryResolver.generate_query(self, info).distinct()
        for option in options:
            query = query.options(option)

        return query

    def retrieve_value(self, parent, info, *args, **kwargs):
        """
        Returns all rows in a table. Uses subquery loads to improve
        querying by loading each relationship based on the query request
        :param parent: parent object required by GraphQL, always None because
        mutations are always top level.
        :param info:
        :param args: Not used but left in so that it can be used if a
        method is overriden
        :param kwargs: Holds the filters and sorts that can be used
        :return: A list of all rows in the table that match the
        filter, sorted by the given sort parameter.
        """
        query = self.generate_query(info)

        filters = generate_filters(self.table, info, **kwargs)
        for filter_ in filters:
            query = query.filter(filter_)
        sorts = generate_sorts(self.table, info, **kwargs)
        for sort in sorts:
            query = query.order_by(sort)

        paginated = False

        if info.variable_values.get("page") is not None:
            paginated = True
            current = info.variable_values.get("page").get("current")
            per_page = info.variable_values.get("page").get("per_page")
            if current is None or current < 1:
                current = 1
            if per_page is None or per_page < 1:
                per_page = 10

        info.context.info["count"] = self.get_count(query)

        if paginated:
            offset = (current - 1) * per_page
            return query.distinct().limit(per_page).offset(offset).all()

        return query.all()
