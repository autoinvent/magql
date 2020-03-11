from pallets_sphinx_themes import get_version

# Project --------------------------------------------------------------

project = "magql"
copyright = "2019 Moebius Solutions"
release, version = get_version("magql")

# General --------------------------------------------------------------

master_doc = "index"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "pallets_sphinx_themes",
    "sphinxcontrib.log_cabinet",
    "sphinx_issues",
]
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
}
issues_github_path = "autoinvent/magql"

# HTML -----------------------------------------------------------------

html_theme = "flask"
html_sidebars = {
    "index": ["searchbox.html"],
    "**": ["localtoc.html", "relations.html", "searchbox.html"],
}
singlehtml_sidebars = {"index": ["localtoc.html"]}
html_title = f"{project} Documentation ({version})"
html_show_sourcelink = False
html_domain_indices = False
