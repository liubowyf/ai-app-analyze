"""Import-safety tests for workers package."""

import importlib
import sys


def _drop_workers_modules() -> None:
    for name in list(sys.modules):
        if name == "workers" or name.startswith("workers."):
            sys.modules.pop(name, None)


def test_import_report_generator_does_not_eager_import_dynamic_analyzer():
    _drop_workers_modules()

    importlib.import_module("workers.report_generator")

    assert "workers.dynamic_analyzer" not in sys.modules
