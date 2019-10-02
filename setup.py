import io

from setuptools import find_packages
from setuptools import setup

with io.open("README.md", "rt", encoding="utf8") as f:
    readme = f.read()


setup(
    name="magql",
    version="0.1.1",
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[
        "sqlalchemy",
        "sqlalchemy_utils",
        "marshmallow==2.20.0",
        "marshmallow_sqlalchemy",
        "inflection",
        "graphql-core-next",
    ],
    extras_require={
        "dev": [
            "pytest",
            "coverage",
            "tox",
            "sphinx",
            "Pallets-Sphinx-Themes",
            "pre-commit",
        ]
    },
)
