import io

from setuptools import find_packages
from setuptools import setup

with io.open("README.md", "rt", encoding="utf8") as f:
    readme = f.read()


setup(
    name="magql",
    version="0.0.1",
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[
        "graphql-core-next",
        "sqlalchemy",
        "sqlalchemy_utils",
        "marshmallow",
        "marshmallow_sqlalchemy",
        "inflection",
    ],
    extras_require={
        "dev": ["pytest", "coverage", "tox", "sphinx", "Pallets-Sphinx-Themes"]
    },
)
