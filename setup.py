from setuptools import setup

# Metadata goes in setup.cfg. These are here for GitHub's dependency graph.
setup(
    name="magql",
    install_requires=[
        "GraphQL-core-next",
        "inflection",
        "marshmallow<3",
        "marshmallow-sqlalchemy",
        "SQLAlchemy",
        "SQLAlchemy-Utils",
    ],
)
