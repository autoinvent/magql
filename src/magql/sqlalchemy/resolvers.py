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
    def __init__(self, model: type[t.Any]) -> None:
        self.model = model
        self.mapper = t.cast(orm.Mapper, sa.inspect(model))
        self.pk_name, self.pk_col = next(
            x for x in self.mapper.columns.items() if x[1].primary_key
        )

    def __call__(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        raise NotImplementedError


class QueryResolver(ModelResolver):
    def build_query(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs
    ) -> sql.Select:
        return sa.select(self.model).options(
            *self._load_relationships(_get_field_node(info), self.model)
        )

    def transform_result(self, result: Result) -> t.Any:
        return result.scalar()

    def __call__(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        query = self.build_query(parent, info, **kwargs)
        result = info.context.execute(query)
        return self.transform_result(result)

    def _load_relationships(
        self,
        node: graphql.FieldNode,
        model: t.Any,
        load_path: orm.Load | None = None,
    ) -> list[orm.Load]:
        out = []

        for selection in node.selection_set.selections:
            if selection.selection_set is None:
                continue

            field_name = selection.name.value
            mapper = sa.inspect(model)
            rel_prop = mapper.relationships.get(field_name)

            if rel_prop is None:
                continue

            rel_attr = rel_prop.class_attribute

            if load_path is None:
                extended_path = orm.selectinload(rel_attr)
            else:
                extended_path = load_path.selectinload(rel_attr)

            out.extend(
                self._load_relationships(
                    selection, rel_prop.entity.class_, extended_path
                )
            )

        if not out:
            if load_path is not None:
                return [load_path]

            return []

        return out


class ItemResolver(QueryResolver):
    def build_query(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs
    ) -> sql.Select:
        load = self._load_relationships(_get_field_node(info), self.model)
        return (
            sa.select(self.model)
            .options(*load)
            .where(self.pk_col == kwargs[self.pk_name])
        )

    def transform_result(self, result: Result) -> t.Any:
        return result.scalar_one_or_none()


class ListResolver(QueryResolver):
    def apply_filter(
        self,
        query: sql.Select,
        filter_arg: list[list[dict[str, t.Any]]] | None,
    ) -> sql.Select:
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
        self, query: sql.Select, sort_arg: list[tuple[str, bool]] | None = None
    ) -> sql.Select:
        if not sort_arg:
            return query.order_by(self.pk_col)

        out = []

        for name, desc in sort_arg:
            value: sa.Column = getattr(self.model, name)

            if not desc:
                out.append(value.asc())
            else:
                out.append(value.desc())

        return query.order_by(*out)

    def apply_page(
        self,
        query: sql.Select,
        page: t.Any | None,
        per_page: int | None,
    ) -> sql.Select:
        if page is None:
            return query

        if per_page is None:
            per_page = 10

        per_page = min(per_page, 100)
        return query.offset((page - 1) * per_page).limit(per_page)

    def build_query(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs
    ) -> sql.Select:
        field_node = _get_field_node(info, nested="items")
        load = self._load_relationships(field_node, self.model)
        query = sa.select(self.model).options(*load)
        query = self.apply_filter(query, kwargs.get("filter"))
        query = self.apply_sort(query, kwargs.get("sort"))
        query = self.apply_page(query, kwargs.get("page"), kwargs.get("per_page"))
        return query

    def get_items(self, session: sa.orm.Session, query: sa.sql.Select) -> list[t.Any]:
        result = session.execute(query)
        return result.scalars().all()

    def get_count(self, session: sa.orm.Session, query: sa.sql.Select) -> int:
        sub = (
            query.options(sa.orm.lazyload("*"))
            .order_by(None)
            .limit(None)
            .offset(None)
            .subquery()
        )
        value = session.execute(sa.select(sa.func.count()).select_from(sub)).scalar()
        return value

    def __call__(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        query = self.build_query(parent, info, **kwargs)
        session: sa.orm.Session = info.context
        items = self.get_items(session, query)
        total = self.get_count(session, query)
        return ListResult(items=items, total=total)


@dataclasses.dataclass()
class ListResult:
    items: t.Any
    total: int


def _get_field_node(
    info: graphql.GraphQLResolveInfo, nested: str | None = None
) -> graphql.FieldNode:
    """Get the node that describes the fields being selected by the current query. This
    is used to determine if any of the fields are relationships to load.
    """
    node = info.field_nodes[0]

    # For a list query, the actual type is nested in the list result type.
    if nested is not None:
        for selection in node.selection_set.selections:
            if selection.name.value == nested:
                return selection

    return node


class MutationResolver(ModelResolver):
    def get_item(self, session: sa.orm.Session, pk_value: t.Any) -> t.Any:
        return session.get(self.model, pk_value)

    def apply_related(self, session: sa.orm.Session, kwargs: dict[str, t.Any]) -> None:
        for key, rel in self.mapper.relationships.items():
            value = kwargs.get(key)

            # skip missing, None, and empty list values
            if not value:
                continue

            target_model = rel.entity.class_
            target_pk_name, target_pk_col = next(
                x for x in rel.mapper.columns.items() if x[1].primary_key
            )

            if rel.direction == sa.orm.MANYTOONE:
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
    def __call__(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        session: sa.orm.Session = info.context
        self.apply_related(session, kwargs)
        obj = self.model(**kwargs)
        session.add(obj)
        session.commit()
        return obj


class UpdateResolver(MutationResolver):
    def __call__(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        session: sa.orm.Session = info.context
        self.apply_related(session, kwargs)
        item = self.get_item(session, kwargs.pop(self.pk_name))

        for key, value in kwargs.items():
            setattr(item, key, value)

        session.commit()
        return item


class DeleteResolver(MutationResolver):
    def __call__(
        self, parent: t.Any, info: graphql.GraphQLResolveInfo, **kwargs: t.Any
    ) -> t.Any:
        session: sa.orm.Session = info.context
        item = self.get_item(session, kwargs[self.pk_name])
        session.delete(item)
        session.commit()
        return True
