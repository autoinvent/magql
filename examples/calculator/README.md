Magql Example - Calculator
==========================

This example creates a calculator API using Magql and Flask-Magql. The `start`
field starts a calculation from 0, and the `Result` object it returns has a `v`
field to see the current value, and various operator fields to apply another
operation. Results and operations can be nested arbitrarily deep.

```text
$ python -m venv .venv
$ . .venv/bin/activate
$ pip install -e .
$ flask run
```

Now open <http://127.0.0.1/graphiql> to view the schema and make queries.
