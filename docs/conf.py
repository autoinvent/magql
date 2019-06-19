# Project --------------------------------------------------------------

project = "GQLMagic"
copyright = "2019 Moebius Solutions, Inc."
author = "Moebius Solutions, Inc."
release, version = ("1", "1")  # get_version("GQLMagic")

# General --------------------------------------------------------------

master_doc = "index"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "pallets_sphinx_themes",
]  # noqa: E501
intersphinx_mapping = {"python": ("https://docs.python.org/3/", None)}

# HTML -----------------------------------------------------------------

html_theme = "flask"
html_sidebars = {
    "index": ["searchbox.html"],
    "**": ["localtoc.html", "relations.html", "searchbox.html"],
}
singlehtml_sidebars = {"index": ["localtoc.html"]}
html_title = "{} Documentation ({})".format(project, version)
html_show_sourcelink = False
html_domain_indices = False
html_experimental_html5_writer = True

# LaTeX ----------------------------------------------------------------

latex_documents = [
    (master_doc, "{}.tex".format(project), html_title, author, "manual")
]  # noqa: E501
