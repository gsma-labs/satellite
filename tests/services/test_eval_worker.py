"""Tests for eval worker task loading behavior."""

from types import SimpleNamespace

import pytest

from satellite.services.evals import worker


class _FakeTask:
    """Minimal task type for runtime type-check tests."""


def _configure_task(monkeypatch: pytest.MonkeyPatch, task_fn) -> None:
    """Point worker registry/imports at a local fake task factory."""
    module = SimpleNamespace(task_factory=task_fn)
    benchmark = SimpleNamespace(
        module_path="evals.fake.fake",
        function_name="task_factory",
    )
    monkeypatch.setattr(worker, "BENCHMARKS_BY_ID", {"fake": benchmark})
    monkeypatch.setattr(worker, "import_module", lambda _: module)


def test_load_task_passes_full_keyword_when_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """load_task(full=True) forwards full=True to compatible factories."""
    monkeypatch.setattr(worker, "Task", _FakeTask)
    calls: list[bool] = []

    def task_factory(*, full: bool = False):
        calls.append(full)
        return _FakeTask()

    _configure_task(monkeypatch, task_factory)

    assert worker.load_task("fake", full=True) is not None
    assert calls == [True]


def test_load_task_omits_full_keyword_when_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Factories without a full argument are called without keyword args."""
    monkeypatch.setattr(worker, "Task", _FakeTask)
    calls: list[None] = []

    def task_factory():
        calls.append(None)
        return _FakeTask()

    _configure_task(monkeypatch, task_factory)

    assert worker.load_task("fake", full=True) is not None
    assert calls == [None]


def test_load_task_does_not_swallow_type_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TypeErrors raised by compatible task factories propagate to caller."""

    def task_factory(*, full: bool = False):
        raise TypeError("task internals failed")

    _configure_task(monkeypatch, task_factory)

    with pytest.raises(TypeError, match="task internals failed"):
        worker.load_task("fake", full=True)


def test_load_task_raises_on_non_task_return(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factories must return Task instances."""
    monkeypatch.setattr(worker, "Task", _FakeTask)

    def task_factory():
        return object()

    _configure_task(monkeypatch, task_factory)

    with pytest.raises(TypeError, match="expected inspect_ai.Task"):
        worker.load_task("fake")


def test_load_task_propagates_non_type_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Factory exceptions other than TypeError should propagate."""

    def task_factory(*, full: bool = False):
        raise RuntimeError("task execution failed")

    _configure_task(monkeypatch, task_factory)

    with pytest.raises(RuntimeError, match="task execution failed"):
        worker.load_task("fake", full=True)


def test_load_task_passes_full_keyword_to_var_keyword_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Factories with **kwargs accept the full parameter."""
    monkeypatch.setattr(worker, "Task", _FakeTask)
    calls: list[dict[str, bool]] = []

    def task_factory(**kwargs):
        calls.append(kwargs)
        return _FakeTask()

    _configure_task(monkeypatch, task_factory)

    assert worker.load_task("fake", full=True) is not None
    assert calls == [{"full": True}]
