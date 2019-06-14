from marshmallow import ValidationError
from sqlalchemy.orm import subqueryload
from sqlalchemy_utils import get_mapper
from magql.filter import generate_filters
from magql.sort import generate_sorts
from inflection import underscore


def js_underscore(word):
    # add config
    return underscore(word)


class Resolver:
    """
    Base Resolver that is a callable that acts as the default resolver
    performing dot operation on the parent object through the field
    info.field_name
    """
    def __call__(self, parent, info, *args, **kwargs):
        return self.resolve(parent, info, *args, **kwargs)

    def resolve(self, parent, info):
        """
        Default resolve method, performs dot access
        :param parent: gql parent. is whatever was returned by the parent resolver
        :param info: gql info dictionary
        :return: getattr(parent, info.field_Name)
        """
        return getattr(parent, underscore(info.field_name))


class CheckDeleteResolver(Resolver):
    """
    Resolver for the function that checks to see what will be deleted
    """
    def __init__(self, table_types):
        self.table_types = table_types

    def resolve(self, parent, info, *args, **kwargs):
        for table in self.table_types.keys():
            class_ = get_mapper(table).class_
            if class_.__name__ == kwargs["tableName"]:
                session = info.context
                instance = session.query(class_).filter_by(id=kwargs["id"]).one()
                session.delete(instance)
                cascades = []
                for obj in session.deleted:
                    cascades.append(obj)

                session.rollback()

                return cascades


class CheckDeleteUnionResolver(Resolver):
    """
    Resolver that determines which type is being return from the delete check
    """
    def __init__(self, table_types):
        self.table_types = table_types


    # This will fail if a type is added to the scheme during a merge because it will not know about the added type
    def resolve_type(self, instance):
        for table, gql_type in self.table_types.items():
            if isinstance(instance, get_mapper(table).class_):
                return gql_type.object
        raise Exception("Type not found")

    def resolve(self, parent, info, *args, **kwargs):
        return self.resolve_type(parent)


class EnumResolver(Resolver):
    def resolve(self, parent, info):
        """
        Resolve Enums which need to get the code from the value
        :param parent: gql parent. is whatever was returned by the parent resolver
        :param info: gql info dictionary
        :return: getattr(parent, info.field_Name)
        """
        return getattr(getattr(parent, underscore(info.field_name)), "value", None)


class TableResolver(Resolver):
    """
    A subclass of :class:`Resolver` that adds a table so that it can be
    reused in :class:`QueryResolver` and :class:`MutationResolver`.
    """
    def __init__(self, table):
        self.table = table


class MutationResolver(TableResolver):
    """
    Subclass of :class:`TableResolver`. Initialized with a schema for
    validating the inputs. Its resolve method will call its validate
    method and return either the requested data of the changed object
    or an error dict filled with errors.
    """
    def __init__(self, table, schema=None):
        """
        MutationResolver can be overriden by
        :param table:
        :param schema: Optional, by default it is a generic Marshmallow
        schema that is automatically generated based on the table by
        Marshmallow-SQLAlchemy.
        """
        super(MutationResolver, self).__init__(table)
        self.schema = schema

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
        if self.schema is not None:
            error = self.validate(parent, info, *args, **kwargs)
            if error:
                return {
                    "error": error
                }
        return super(MutationResolver, self).__call__(parent, info, *args, **kwargs)

    def validate(self, parent, info, **kwargs):
        """
        Validates that all fields that are in the input are valid
        according to the Marshmallow schema. The default Marshmallow
        schema can be overriden or the entire validate method can be
        overriden to allow for non-standard validations.
        :param parent: parent object required by GraphQL, always None because
        mutations are always top level.
        :param info: GraphQL info dictionary
        :param kwargs: Holds user inputs. If the input dict is passed,
        this function will validate each of the fields it contains.
        :return: A list of validation errors, if they occurred else None
        """
        if "input" in kwargs:
            try:
                schema = self.schema()
                validate = schema.load(kwargs["input"], session=info.context)
            except ValidationError as err:
                return [value for key, value in err.messages.items()]
            if validate.errors:
                return [value[0] for key, value in validate.errors.items()]

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
            if key in mapper.relationships:
                target = get_mapper(mapper.relationships[key].target).class_
                query = session.query(target)
                if isinstance(value, list):
                    value = query.filter(target.id.in_(value)).all()
                else:
                    value = query.filter(target.id == value).one()
            instance_values[key] = value
        return instance_values


class CreateResolver(MutationResolver):
    """
    A subclass of :class:`MutationResolver`. Takes a dict of field values
    as input and creates an instance of the associated table with those
    fields.
    """
    def resolve(self, parent, info, *args, **kwargs):
        session = info.context
        mapper = get_mapper(self.table)
        table_name = self.table.name

        instance_values = self.input_to_instance_values(kwargs["input"], mapper, session)

        instance = mapper.class_()
        for key, value in instance_values.items():
            setattr(instance, key, value)
        session.add(instance)
        session.commit()
        return {
            table_name: instance,
        }


class UpdateResolver(MutationResolver):
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

        instance_values = self.input_to_instance_values(kwargs["input"], mapper, session)

        instance = session.query(mapper.class_).filter_by(id=kwargs["id"]).one()
        for key, value in instance_values.items():
            setattr(instance, key, value)
        session.add(instance)
        session.commit()

        return {
            table_name: instance
        }


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

        instance = session.query(mapper.class_).filter_by(id=kwargs["id"]).one()
        session.delete(instance)
        session.commit()

        return {
            table_name: instance
        }


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
    def resolve(self, parent, info, *args, **kwargs):
        """

        :param parent:
        :param info: GraphQL info dictionary, holds the SQLA session
        :param args:
        :param kwargs: Has the id of the instance of the desired model
        :return: The instance of the model with the given id
        """
        return self.generate_query(info).filter_by(id=kwargs["id"]).one_or_none()


class ManyResolver(QueryResolver):
    """
    A subclass of :class:`QueryResolver`. By default queries for all
    instances of the table that it is associated with. Can be filtered and sorted
    with keyword args.
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
            if load_path is None:
                extended_load_path = subqueryload(field_name)
            else:
                extended_load_path = load_path.subqueryload(field_name)
            options = options + self.generate_subqueryloads(
                selection, extended_load_path)

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
            filter(lambda selection: selection.name.value == field_name, info.operation.selection_set.selections))
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
