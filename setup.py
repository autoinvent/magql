from setuptools import setup

# Metadata goes in setup.cfg. These are here for GitHub's dependency graph.
setup(
    name="magql",
    install_requires=[
        "graphql-core>=3",
        "inflection>=0.3",
        "SQLAlchemy>=1.3",
        "SQLAlchemy-Utils>=0.35",
    ],
)
