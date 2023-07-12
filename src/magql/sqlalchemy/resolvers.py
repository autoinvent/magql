from __future__ import annotations

import dataclasses
import typing as t

import graphql
import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy import sql
from sqlalchemy.engine import Result

from . import filters


class ModelResolver:
    """Base class for the SQLAlchemy model API resolvers used by :class:`.ModelManager`.
    Subclasses must implement ``__call__``.

    A resolver is for a specific model, and does some introspection on the model to
    know what the mapper and primary key are.

    In order to execute the SQL expression, ``info.context`` must be set to the
    SQLAlchemy session.
    """

    def __init__(self, model: type[t.Any]) -> None:
        self.model = model
        self.mapper: orm.Mapper[t.Any] = t.cast(orm.Mapper[t.Any], sa.inspect(model))
        self.pk_name: str
        self.pk_col: sa.Column[t.Any]
        self.pk_name, self.pk_col = next(
            x for x in self.mapper.columns.items() if x[1].primary_key
        )

    def _load_relationships(
        self,
        node: graphql.FieldNode,
        model: t.Any,
        load_path: orm.Load | None = None,
    ) -> list[orm.Load]:
        """Given the AST node representing the GraphQL operation, find all the
        SQLAlchemy relationships that should be eagerly loaded, recursively, and
        generate load expressions for them. This makes resolving the graph very
        efficient by letting SQLAlchemy preload related data rather than issuing
        individual queries for every attribute access.

        :param node: The AST node representing the GraphQL operation.
        :param model: The model containing the relationships. Starts as the model for
            this resolver, then the relationship's target model during recursion.
        :param load_path: During recursion, the SQLAlchemy load that has been performed
            to get to this relationship and should be extended.
        """
        out = []
        assert node.selection_set is not None

        for selection in node.selection_set.selections:
            inner_node = t.cast(graphql.FieldNode, selection)

            # Only consider AST nodes for relationships, which are ones with further
            # selections for the object's fields.
            if inner_node.selection_set is None:
                continue

            field_name = inner_node.name.value
            mapper = sa.inspect(model)
            rel_prop = mapper.relationships.get(field_name)

            if rel_prop is None:
                # This somehow isn't a relationship even though it's an object type.
                # Could happen if a custom extra field+resolver was added.
                continue

            rel_attr = rel_prop.class_attribute

            if load_path is None:
                # At the base level, start a new load expression.
                extended_path = t.cast(orm.Load, orm.selectinload(rel_attr))
            else:
                # Recursion, extend the existing load expression.
                extended_path = load_path.selectinload(rel_attr)

            # Recurse to find any relationship fields selected in the child object.
            out.extend(
                self._load_relationships(
                    inner_node, rel_prop.entity.class_, extended_path
                )
            )

        if not out:
            if load_path is not None:
                # This was a relationship, and there were no child relationships.
                return [load_path]

            # There were no relationships selected at all.
            return []

        # There were child relationships, and this is the full collection.
        return out

    def __call__(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        raise NotImplementedError


class QueryResolver(ModelResolver):
    """Base class for SQLAlchemy model API queries used by :class:`.ModelManager`.
    Subclasses must implement :meth:`build_query` and :meth:`transform_result`, and can
    override ``__call__``.
    """

    def build_query(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> sql.Select[t.Any]:
        """Build the query to execute."""
        raise NotImplementedError

    def transform_result(self, result: Result[t.Any]) -> t.Any:
        """Get the model instance or list of instances from a SQLAlchemy result."""
        raise NotImplementedError

    def __call__(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        """Build and execute the query, then return the result."""
        query = self.build_query(parent, info, **kwargs)
        result = info.context.execute(query)
        return self.transform_result(result)


class ItemResolver(QueryResolver):
    """Get a single row from the database by id. Used by
    :attr:`.ModelManager.item_field`. ``id`` is the only GraphQL argument. Returns a
    single model instance, or ``None`` if the id wasn't found.

    :param model: The SQLAlchemy model.
    """

    def build_query(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> sql.Select[t.Any]:
        load = self._load_relationships(_get_field_node(info), self.model)
        return (
            sa.select(self.model)
            .options(*load)
            .where(self.pk_col == kwargs[self.pk_name])
        )

    def transform_result(self, result: Result[t.Any]) -> t.Any:
        return result.scalar_one_or_none()


class ListResolver(QueryResolver):
    """Get a list of rows from the database, with support for filtering, sorting, and
    pagination. If any relationships, arbitrarily nested, are selected, they are
    eagerly loaded to Used by :attr:`.ModelManager.list_field`. Returns a
    :class:`ListResult`, which has the list of model instances selected for this page,
    as well as the total available rows.

    Pagination is always applied to the query to avoid returning thousands of results at
    once for large data sets. The default ``page`` is 1. The default ``per_page`` is
    10, with a max of 100.

    The ``sort`` argument is a list of ``(name: str, desc: bool)`` items from the
    :attr:`.ModelManager.sort` enum. By default the rows are sorted by their primary key
    column, otherwise the order wouldn't be guaranteed consistent across pages.

    Filtering applies one or more filter rules to the query. The ``filter`` argument is
    a list of lists of rules. Each rule is a ``{path, op, not, value}`` dict. The rules
    in a list will be combined with ``AND``, and the lists will be combined with ``OR``.
    The ``path`` in a rule is the name of a column attribute on the model like ``name``,
    or a dotted path to an arbitrarily nested relationship's column like
    ``user.friend.color.name``. Different ``op`` names are available based on the
    column's type. The ``value`` can be any JSON data that the op understands. Most ops
    support a list of values in addition to a single value. See
    :func:`apply_filter_item` and :data:`.type_ops`.

    If any relationships are selected anywhere in the GraphQL query, SQLAlchemy eager
    loads are generated them. This makes resolving the graph very efficient by letting
    SQLAlchemy preload related data rather than issuing individual queries for every
    attribute access.

    :param model: The SQLAlchemy model.
    """

    def apply_filter(
        self,
        query: sql.Select[t.Any],
        filter_arg: list[list[dict[str, t.Any]]] | None,
    ) -> sql.Select[t.Any]:
        if not filter_arg:
            return query

        # TODO use aliases to support filtering on different paths to the same model
        seen: set[str] = set()
        or_clauses = []

        for filter_group in filter_arg:
            and_clauses = []

            for filter_item in filter_group:
                path, _, name = filter_item["path"].rpartition(".")
                mapper = self.mapper

                if path:
                    for path_part in path.split("."):
                        rel = mapper.relationships[path_part]
                        mapper = rel.mapper

                        if path_part in seen:
                            continue

                        seen.add(path_part)
                        query = query.join(rel.class_attribute)

                col = mapper.columns[name]
                clause = filters.apply_filter_item(col, filter_item)
                and_clauses.append(clause)

            or_clauses.append(sa.and_(*and_clauses))

        return query.filter(sa.or_(*or_clauses))

    def apply_sort(
        self, query: sql.Select[t.Any], sort_arg: list[tuple[str, bool]] | None = None
    ) -> sql.Select[t.Any]:
        if not sort_arg:
            return query.order_by(self.pk_col)

        out = []

        for name, desc in sort_arg:
            value: sa.Column[t.Any] = getattr(self.model, name)

            if not desc:
                out.append(value.asc())
            else:
                out.append(value.desc())

        return query.order_by(*out)

    def apply_page(
        self,
        query: sql.Select[t.Any],
        page: t.Any | None,
        per_page: int | None,
    ) -> sql.Select[t.Any]:
        if page is None:
            return query

        if per_page is None:
            per_page = 10

        per_page = min(per_page, 100)
        return query.offset((page - 1) * per_page).limit(per_page)

    def build_query(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> sql.Select[t.Any]:
        field_node = _get_field_node(info, nested="items")
        load = self._load_relationships(field_node, self.model)
        query = sa.select(self.model).options(*load)
        query = self.apply_filter(query, kwargs.get("filter"))
        query = self.apply_sort(query, kwargs.get("sort"))
        query = self.apply_page(query, kwargs.get("page"), kwargs.get("per_page"))
        return query

    def get_items(self, session: orm.Session, query: sql.Select[t.Any]) -> list[t.Any]:
        result = session.execute(query)
        return result.scalars().all()  # type: ignore[return-value]

    def get_count(self, session: orm.Session, query: sql.Select[t.Any]) -> int:
        """After generating the query with any filters, get the total row count for
        pagination purposes. Remove any eager loads, sorts, and pagination, then execute
        a SQL ``count()`` query.

        :param session: The SQLAlchemy session.
        :param query: The fully constructed list query.
        """
        sub = (
            query.options(orm.lazyload("*"))
            .order_by(None)
            .limit(None)
            .offset(None)
            .subquery()
        )
        value = session.execute(sa.select(sa.func.count()).select_from(sub)).scalar()
        return value  # type: ignore[return-value]

    def __call__(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        query = self.build_query(parent, info, **kwargs)
        session: orm.Session = info.context
        items = self.get_items(session, query)
        total = self.get_count(session, query)
        return ListResult(items=items, total=total)


@dataclasses.dataclass()
class ListResult:
    """The return value for :class:`ListResolver` and :attr:`.ModelManager.list_field`.
    :attr:`.ModelManager.list_result` is the Magql type corresponding to this Python
    type.
    """

    items: list[t.Any]
    """The list of model instances for this page."""

    total: int
    """The total number of rows if pagination was not applied."""


def _get_field_node(
    info: graphql.GraphQLResolveInfo, nested: str | None = None
) -> graphql.FieldNode:
    """Get the node that describes the fields being selected by the current query. This
    is used to determine if any of the fields are relationships to load.

    :param info: The GrapQL info about the operation, which contains the AST.
    :param nested: For the list query, the name of the field containing the list of
        results. Should be ``"items"``.
    """
    node = info.field_nodes[0]

    # For a list query, the actual type is nested in the list result type.
    if nested is not None:
        assert node.selection_set is not None

        for selection in node.selection_set.selections:
            inner_node = t.cast(graphql.FieldNode, selection)

            if inner_node.name.value == nested:
                return inner_node

    return node


class MutationResolver(ModelResolver):
    """Base class for SQLAlchemy model API mutations used by :class:`.ModelManager`.
    Subclasses must implement ``__call__``.
    """

    def get_item(self, info: graphql.GraphQLResolveInfo, kwargs: t.Any) -> t.Any:
        """Get the model instance by primary key value."""
        return info.context.execute(
            sa.select(self.model)
            .options(*self._load_relationships(_get_field_node(info), self.model))
            .where(self.pk_col == kwargs[self.pk_name])
        ).scalar_one()

    def apply_related(self, session: orm.Session, kwargs: dict[str, t.Any]) -> None:
        """For all relationship arguments, replace the id values with their model
        instances.
        """
        for key, rel in self.mapper.relationships.items():
            value = kwargs.get(key)

            # skip missing, None, and empty list values
            if not value:
                continue

            target_model = rel.entity.class_
            target_pk_name, target_pk_col = next(
                x for x in rel.mapper.columns.items() if x[1].primary_key
            )

            if rel.direction == orm.MANYTOONE:
                kwargs[key] = session.execute(
                    sa.select(target_model).filter(target_pk_col == value)
                ).scalar_one()
            else:
                kwargs[key] = (
                    session.execute(
                        sa.select(target_model).filter(target_pk_col.in_(value))
                    )
                    .scalars()
                    .all()
                )


class CreateResolver(MutationResolver):
    """Create a new row in the database. Used by :attr:`.ModelManager.create_field`. The
    field has arguments for each of the model's column attributes. An argument is not
    required if its column is nullable or has a default. Unique constraints on will
    already be validated. Returns the new model instance.

    :param model: The SQLAlchemy model.
    """

    def __call__(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        session: orm.Session = info.context
        self.apply_related(session, kwargs)
        obj = self.model(**kwargs)
        session.add(obj)
        session.commit()
        return obj


class UpdateResolver(MutationResolver):
    """Updates a row in the database by id. Used by :attr:`.ModelManager.update_field`.
    The field has arguments for each of the model's column attributes. Only the primary
    key argument is required. Columns are only updated if a value is provided, which is
    distinct from setting the value to ``None``. Unique constraints will already be
    validated. Returns the updated model instance.

    :param model: The SQLAlchemy model.
    """

    def __call__(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        session: orm.Session = info.context
        self.apply_related(session, kwargs)
        item = self.get_item(info, kwargs.pop(self.pk_name))

        for key, value in kwargs.items():
            setattr(item, key, value)

        session.commit()
        return item


class DeleteResolver(MutationResolver):
    """Deletes a row in the database by id. Used by :attr:`.ModelManager.update_field`.
    Use the :class:`.CheckDelete` API first to check if the row can be safely deleted.
    Returns ``True``.

    :param model: The SQLAlchemy model.
    """

    def __call__(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        session: orm.Session = info.context
        item = self.get_item(info, kwargs)
        session.delete(item)
        session.commit()
        return True
