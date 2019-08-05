from inflection import underscore
from marshmallow import ValidationError
from sqlalchemy.orm import subqueryload
from sqlalchemy_utils import ChoiceType
from sqlalchemy_utils import get_mapper

from magql.filter import generate_filters
from magql.sort import generate_sorts


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
        resolved_value = self.resolve(parent, info, *args, **kwargs)
        post_resolved_value = self.post_resolve(
            resolved_value, parent, info, *args, **kwargs
        )
        return post_resolved_value

    def pre_resolve(self, parent, info, *args, **kwargs):
        return parent, info, args, kwargs

    def post_resolve(self, resolved_value, parent, info, *args, **kwargs):
        return resolved_value

    def resolve(self, parent, info):
        """
        Default resolve method, performs dot access
        :param parent: gql parent. is whatever was returned by the
        parent resolver
        :param info: gql info dictionary
        :return: getattr(parent, info.field_Name)
        """
        return getattr(parent, underscore(info.field_name))

    def override_resolver(self, resolve):
        self.overriden_resolve = self.resolve
        self.resolve = resolve
        return resolve


class CamelResolver(Resolver):
    def resolve(self, parent, info, *args, **kwargs):
        source = parent
        # Identical to graphql's default_field_resolver
        # except the field_name is snake case
        # TODO: Look into a way to generate info
        #  dictionary so the code does not need to be
        # copied or circumvent alltogether in a different way
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

    def resolve(self, parent, info, *args, **kwargs):
        for table in self.table_types.keys():
            class_ = get_mapper(table).class_
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

    def resolve(self, parent, info, *args, **kwargs):
        for magql_name, table in self.magql_name_to_table.items():
            if isinstance(parent, get_mapper(table).class_):
                for gql_type in info.return_type.of_type.types:
                    if gql_type.name == magql_name:
                        return gql_type
        raise Exception("Type not found")


class EnumResolver(Resolver):
    def resolve(self, parent, info):
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


class DECIMALResolver(Resolver):
    def resolve(self, parent, info):
        """
        Resolves decimals which need to get the real value
        :param parent: gql parent. is whatever was returned by
        the parent resolver
        :param info: gql info dictionary
        :return: decimal value
        """
        if not parent:
            return None
        field_name = underscore(info.field_name)
        return getattr(getattr(parent, field_name), "value", None)


class TableResolver(Resolver):  # noqa: B903
    """
    A subclass of :class:`Resolver` that adds a table so that it can be
    reused in :class:`QueryResolver` and :class:`MutationResolver`.
    """

    def __init__(self, table, schema=None, partial=True):
        """
        MutationResolver can be overriden by
        :param table:
        :param schema: Optional, by default it is a generic Marshmallow
        schema that is automatically generated based on the table by
        Marshmallow-SQLAlchemy.
        """
        self.table = table
        self.table_class = get_mapper(table).class_
        self.schema = schema
        self.partial = partial

    def __call__(self, parent, info, *args, **kwargs):
        if self.schema is not None:
            error = self.validate(parent, info, *args, **kwargs)
            if error:
                return {"errors": error}
        return super(TableResolver, self).__call__(parent, info, *args, **kwargs)

    def override_validate(self, validate):
        self.validate = validate
        return validate

    def validate(self):
        pass


class MutationResolver(TableResolver):
    """
    Subclass of :class:`TableResolver`. Initialized with a schema for
    validating the inputs. Its resolve method will call its validate
    method and return either the requested data of the changed object
    or an error dict filled with errors.
    """

    def __call__(self, parent, info, *args, **kwargs):
        """
        Checks if a schema has been set and if so validates the mutation.
        Otherwise it just resolves the mutation.
        :param parent: parent object required by GraphQL, always None because
        mutations are always top level.
        :param info: GraphQL info dictionary
        :param args: Not used in automatic generation but left in in case
        overriding the validate or call methods.
        :param kwargs: Holds user inputs.
        :return:
        """
        super_ = super(MutationResolver, self)
        return super_.__call__(parent, info, *args, **kwargs)

    def validate(self, parent, info, **kwargs):
        """
        Validates that all fields that are in the input are valid
        according to the Marshmallow schema. The default Marshmallow
        schema can be overriden or the entire validate method can be
        overriden to allow for non-standard validations.
        :param parent: parent object required by GraphQL, always
        None because mutations are always top level.
        :param info: GraphQL info dictionary
        :param kwargs: Holds user inputs. If the input dict is passed,
        this function will validate each of the fields it contains.
        :return: A list of validation errors, if they occurred else None
        """
        if "input" in kwargs:
            try:
                schema = self.schema()
                input_ = kwargs["input"]
                camel_input = {}
                for key, value in input_.items():
                    camel_input[underscore(key)] = value
                validate = schema.load(
                    camel_input, session=info.context, partial=self.partial
                )
            except ValidationError as err:
                return [value for key, value in err.messages.items()]
            if validate.errors:
                return [value[0] for key, value in validate.errors.items()]
            info.context.rollback()

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

    def post_resolve(self, resolved_value, parent, info, *args, **kwargs):
        info.context.commit()
        return resolved_value


class ModelInputResolver(MutationResolver):
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

    def resolve(self, parent, info, *args, **kwargs):
        session = info.context
        mapper = get_mapper(self.table)
        table_name = self.table.name

        instance = mapper.class_()
        for key, value in kwargs["input"].items():
            setattr(instance, key, value)
        session.add(instance)
        return {table_name: instance}


class UpdateResolver(ModelInputResolver):
    """
    A subclass of :class:`MutationResolver`. Takes a dict of field values
    and an id as input and updates the instance specified by id with
    fields specified by fields.
    """

    def resolve(self, parent, info, *args, **kwargs):
        """
        Updates the instance of the associated table with the id passed.
        Performs setattr on the key/value pairs.
        :param parent: parent object required by GraphQL, always None because
        mutations are always top level.
        :param info: GraphQL info dictionary
        :param args: Not used in automatic generation but left in in case
        overriding the validate or call methods.
        :param kwargs: Holds user inputs.
        :return: The instance with newly modified values
        """
        session = info.context
        mapper = get_mapper(self.table)
        table_name = self.table.name

        id_ = kwargs["id"]
        instance = session.query(mapper.class_).filter_by(id=id_).one()

        # Current enum implementation is very closely tied to using choice type
        for key, value in kwargs["input"].items():
            setattr(instance, key, value)
        session.add(instance)

        return {table_name: instance}


class DeleteResolver(MutationResolver):
    """
    A subclass of :class:`MutationResolver`. Takes an id and deletes
    the instance specified by id.
    """

    def resolve(self, parent, info, *args, **kwargs):
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
        table_name = self.table.name
        id_ = kwargs["id"]
        instance = session.query(mapper.class_).filter_by(id=id_).one()
        session.delete(instance)

        return {table_name: instance}


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

    def validate(self, parent, info, *args, **kwargs):
        pass


class SingleResolver(QueryResolver):
    """
    A subclass of :class:`QueryResolver`. Takes an id and queries for
    the instance specified by id.
    """

    def resolve(self, parent, info, *args, **kwargs):
        """

        :param parent:
        :param info: GraphQL info dictionary, holds the SQLA session
        :param args:
        :param kwargs: Has the id of the instance of the desired model
        :return: The instance of the model with the given id
        """
        query = self.generate_query(info)
        return query.filter_by(id=kwargs["id"]).one_or_none()

    def validate(self, parent, info, *args, **kwargs):
        pass


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
            print("Duplicate queries not allowed")
        options = self.generate_subqueryloads(field_node[0])
        query = QueryResolver.generate_query(self, info)
        for option in options:
            query = query.options(option)
        return query

    def resolve(self, parent, info, *args, **kwargs):
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
