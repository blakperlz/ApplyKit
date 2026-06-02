"""ApplyKit — a scheduled job-search pipeline.

Scout -> Score -> Rank -> Craft -> Apply.

The Python package is the secondary (CLI / power-user) interface. The primary
runtime is the Cowork skill layer (see ``skill/``). Both share one data
contract: the SQLite schema in :mod:`applykit.db` and the YAML config in
:mod:`applykit.config`.
"""

__version__ = "0.1.0"
