import importlib.metadata

# Project --------------------------------------------------------------

project = "magql"
version = release = importlib.metadata.version("magql").partition(".dev")[0]

# General --------------------------------------------------------------

extensions = [
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "myst_parser",
    "autodoc2",
]
extlinks = {
    "issue": ("https://github.com/autoinvent/magql/issues/%s", "#%s"),
    "pr": ("https://github.com/autoinvent/magql/pull/%s", "#%s"),
}
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "graphql": ("https://graphql-core-3.readthedocs.io/en/latest/", None),
    "sqlalchemy": ("https://docs.sqlalchemy.org", None),
}
myst_enable_extensions = [
    "fieldlist",
]
myst_heading_anchors = 2
autodoc2_packages = [{"path": "../src/magql", "auto_mode": False}]

# HTML -----------------------------------------------------------------

html_theme = "furo"
html_theme_options = {
    "source_repository": "https://github.com/autoinvent/magql/",
    "source_branch": "main",
    "source_directory": "docs/",
}
html_show_copyright = False
