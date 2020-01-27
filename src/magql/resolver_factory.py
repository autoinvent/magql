from inflection import underscore
from sqlalchemy.orm import subqueryload
from sqlalchemy_utils import ChoiceType
from sqlalchemy_utils import get_mapper

from magql.filter import generate_filters
from magql.magql_logging import magql_logger
from magql.sort import generate_sorts
from magql.validator import ValidationFailedError


def js_underscore(word):
    # add config
    return underscore(word)


class Resolver:
    """
    Base Resolver that is a callable that acts as the default resolver
    performing dot operation on the parent object through the field
    info.field_name
    """

    def __init__(self):
        self.overriden_resolve = None

    def __call__(self, parent, info, *args, **kwargs):
        parent, info, args, kwargs = self.pre_resolve(parent, info, *args, **kwargs)
        try:
            resolved_value = self.resolve(parent, info, *args, **kwargs)
        except ValidationFailedError as validation_errors:
            return {"errors": list(validation_errors.args)}
        except PermissionError as authorize_error:
            return {"errors": list(authorize_error.args)}
        post_resolved_value = self.post_resolve(
            resolved_value, parent, info, *args, **kwargs
        )
        return post_resolved_value

    def pre_resolve(self, parent, info, *args, **kwargs):
        return parent, info, args, kwargs

    def post_resolve(self, resolved_value, parent, info, *args, **kwargs):
        return resolved_value

    # Authorize should raise an error if it encounters one
    # This error will then be caughnt and returned by resolve
    def authorize(self, instance, parent, info, *args, **kwargs):
        return None

    # Validate should return an error if it encounters one
    # This error will then be returned by resolve
    def validate(self, instance, parent, info, *args, **kwargs):
        return None

    # Queries will not mutate the value but mutations will override this
    # to mutate the value as needed
    def mutate(self, value, parent, info, *args, **kwargs):
        return value

    def retrieve_value(self, parent, info):
        return getattr(parent, underscore(info.field_name))

    def resolve(self, parent, info, *args, **kwargs):
        """
        Default resolve method, performs dot access
        :param parent: gql parent. is whatever was returned by the
        parent resolver
        :param info: gql info dictionary
        :return: getattr(parent, info.field_Name)
        """
        value = self.retrieve_value(parent, info, *args, **kwargs)

        self.authorize(value, parent, info, *args, **kwargs)

        self.validate(value, parent, info, *args, **kwargs)

        value = self.mutate(value, parent, info, *args, **kwargs)

        return value

    def override_resolve(self, resolve):
        self.overriden_resolve = self.resolve
        self.resolve = resolve
        return resolve


class CamelResolver(Resolver):
    def retrieve_value(self, parent, info, *args, **kwargs):
        source = parent
        # Identical to graphql's default_field_resolver
        # except the field_name is snake case
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


class CheckDeleteResolver(Resolver):
    """
    Resolver for the function that checks to see what will be deleted
    """

    def __init__(self, table_types):
        self.table_types = table_types
        super(CheckDeleteResolver, self).__init__()

    def retrieve_value(self, parent, info, *args, **kwargs):
        for table in self.table_types.keys():
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


class SQLAlchemyTableUnionResolver(Resolver):
    """
    Resolver that determines which type is being return from the delete check.
    This resolver is tied to the use of sqlalchemy
    """

    def __init__(self, magql_name_to_table):
        self.magql_name_to_table = magql_name_to_table
        super(SQLAlchemyTableUnionResolver, self).__init__()

    def retrieve_value(self, parent, info, *args, **kwargs):
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
        super(TableResolver, self).__init__()


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
        session = info.context
        session.add(resolved_value)
        session.commit()
        table_name = self.table.name
        return {table_name: resolved_value}

    # def resolve(self, parent, info):
    #     value = super().resolve()
    #     table_name = self.table.name
    #     return {table_name: value}


class ModelInputResolver(MutationResolver):
    def __init__(self, table):
        """
        MutationResolver can be overriden by
        :param table:
        :param schema: Optional, by default it is a generic Marshmallow
        schema that is automatically generated based on the table by
        Marshmallow-SQLAlchemy.
        """
        super(ModelInputResolver, self).__init__(table)

    def pre_resolve(self, parent, info, *args, **kwargs):
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
        mapper = get_mapper(self.table)

        # TODO: Replace with dictionary spread operator
        instance = mapper.class_()
        return instance

    def mutate(self, instance, parent, info, *args, **kwargs):
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
        # result = self.schema.load(kwargs["input"], session=info.context, partial=True)
        # session.rollback()
        # data = result.data
        # Current enum implementation is very closely tied to using choice type

    def mutate(self, instance, parent, info, *args, **kwargs):
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
        Deletes the instance of the associated table with the id passed.
        :param parent: parent object required by GraphQL, always None because
        mutations are always top level.
        :param info: GraphQL info dictionary
        :param args: Not used in automatic generation but left in in case
        overriding the validate or call methods.
        :param kwargs: Holds user inputs.
        :return: The deleted instance
        """
        session = info.context
        mapper = get_mapper(self.table)
        id_ = kwargs["id"]
        return session.query(mapper.class_).filter_by(id=id_).one()

    def mutate(self, instance, parent, info, *args, **kwargs):
        session = info.context
        session.delete(instance)
        return instance

    def post_resolve(self, resolved_value, parent, info, *args, **kwargs):
        session = info.context
        session.delete(resolved_value)
        session.commit()
        table_name = self.table.name
        return {table_name: resolved_value}


class QueryResolver(TableResolver):
    """
    A subclass of :class:`TableResolver`.
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

    def retrieve_value(self, parent, info, *args, **kwargs):
        """

        :param parent:
        :param info: GraphQL info dictionary, holds the SQLA session
        :param args:
        :param kwargs: Has the id of the instance of the desired model
        :return: The instance of the model with the given id
        """
        query = self.generate_query(info)
        return query.filter_by(id=kwargs["id"]).one_or_none()


class ManyResolver(QueryResolver):
    """
    A subclass of :class:`QueryResolver`. By default queries for all
    instances of the table that it is associated with. Can be filtered and
    sorted with keyword args.
    """

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
        field_node = list(
            filter(
                lambda selection: selection.name.value == field_name,
                info.operation.selection_set.selections,
            )
        )
        if len(field_node) != 1:
            magql_logger.error("Duplicate queries not allowed")
        options = self.generate_subqueryloads(field_node[0])
        query = QueryResolver.generate_query(self, info)
        for option in options:
            query = query.options(option)
        return query

    def retrieve_value(self, parent, info, *args, **kwargs):
        """
        Returns all objects associated with a table and builds out
        a SQLAlchemy query that corresponds to the GQL query so
        that the only one query is performed with multiple subquery
        loads
        :param parent: parent object required by GraphQL, always None because
        mutations are always top level.
        :param info:
        :param args: Not used but left in so that it can be used if a
        method is overriden
        :param kwargs: Holds the filters and sorts that can be used
        :return: A list of all instances of the model that match the
        filter, sorted by the given sort parameter.
        """
        query = self.generate_query(info)
        filters = generate_filters(self.table, info, **kwargs)
        for filter_ in filters:
            query = query.filter(filter_)
        sorts = generate_sorts(self.table, info, **kwargs)
        for sort in sorts:
            query = query.order_by(sort)
        return query.all()
