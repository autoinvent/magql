from __future__ import annotations

from magql import nodes
from magql import scalars

filter_item: nodes.InputObject = nodes.InputObject(
    "FilterItem",
    fields={
        "path": scalars.String.non_null,
        "op": scalars.String.non_null,
        "not": nodes.InputField(scalars.Boolean.non_null, default=False),
        "value": scalars.JSON.list.non_null,
    },
)
"""The input type for the ``filter`` argument to data source list resolvers.

.. code-block:: text

    input FilterItem {
        path: String!
        op: String!
        not: Boolean! = false
        value: [JSON]!
    }
"""
