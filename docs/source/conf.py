import sys
from datetime import datetime
from pathlib import Path

# -- Path setup --------------------------------------------------------------
# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
if sys.platform == "win32":
    sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
else:
    sys.path.insert(0, Path(__file__).parent.parent.resolve().as_posix())

# -- Project information -----------------------------------------------------
project = "Janus"
copyright = f"{datetime.now().year}, AI Dev Team"
author = "AI Dev Team"
release = "0.2.0"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "myst_parser",
    "sphinx_autodoc_typehints",
]

# MyST settings
myst_enable_extensions = [
    "amsmath",
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "linkify",
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist",
]

myst_heading_anchors = 3

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns: list[str] = []

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_rtd_theme"

# Add any paths that contain static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# -- Extension configuration -------------------------------------------------
autodoc_member_order = "bysource"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
# -- Options for LaTeX output ------------------------------------------------
latex_engine = "xelatex"
latex_elements = {
    "papersize": "letterpaper",
    "pointsize": "10pt",
    "preamble": r"""
\usepackage{fontspec}
\defaultfontfeatures{Ligatures=TeX}
""",
}
