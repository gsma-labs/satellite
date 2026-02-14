import json
from pathlib import Path
from types import SimpleNamespace

from satellite.services.evals.job_manager import _aggregate_progress


class _FakeLogRef:
    def __init__(self, path: Path) -> None:
        self.name = path.as_uri()

    def __repr__(self) -> str:
        return self.name


def test_aggregate_progress_reads_sidecar_from_log_dir(monkeypatch, tmp_path: Path) -> None:
    provider_dir = tmp_path / "openrouter"
    log_dir = provider_dir / "anthropic" / "claude"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / "2026-02-14T00-00-00+00-00_task_abc.json"
    log_path.write_text("{}\n")

    # Sidecar written by Satellite Inspect hooks (one eval_id).
    (log_dir / ".satellite-progress.json").write_text(
        json.dumps(
            {
                "version": 1,
                "eval_set_id": "set-1",
                "log_dir": str(log_dir),
                "updated_at": "2026-02-14T00:00:00+00:00",
                "evals": {
                    "eval-123": {
                        "planned_units": 10,
                        "completed_units": 3,
                        "status": "running",
                    }
                },
            }
        )
        + "\n"
    )

    fake_ref = _FakeLogRef(log_path)

    monkeypatch.setattr(
        "satellite.services.evals.job_manager.list_eval_logs",
        lambda *_args, **_kwargs: [fake_ref],
    )

    log = SimpleNamespace(
        status="started",
        eval=SimpleNamespace(
            eval_id="eval-123",
            dataset=SimpleNamespace(sample_ids=[f"s{i}" for i in range(10)], samples=10),
            config=SimpleNamespace(epochs=1),
        ),
        results=None,
        stats=None,
    )
    monkeypatch.setattr(
        "satellite.services.evals.job_manager.read_eval_log",
        lambda *_args, **_kwargs: log,
    )

    # If we don't find the sidecar and fall back to counting sample summaries, fail fast.
    def _unexpected(*_args, **_kwargs) -> int:
        raise AssertionError("expected sidecar progress; fallback should not be used")

    monkeypatch.setattr(
        "satellite.services.evals.job_manager._count_completed_samples",
        _unexpected,
    )

    status, completed_evals, total_evals, eval_progress, completed_samples, total_samples = (
        _aggregate_progress([provider_dir])
    )

    assert status == "running"
    assert completed_evals == 0
    assert total_evals == 1
    assert eval_progress == 0.3
    assert completed_samples == 3
    assert total_samples == 10

