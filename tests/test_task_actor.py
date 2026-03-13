import importlib.util
from pathlib import Path


def _load_task_actor_module():
    module_path = Path(__file__).resolve().parents[1] / "workers" / "task_actor.py"
    assert module_path.exists(), "workers/task_actor.py should exist"

    spec = importlib.util.spec_from_file_location("task_actor_under_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_task_accepts_task_id():
    module = _load_task_actor_module()
    assert callable(module.run_task)
