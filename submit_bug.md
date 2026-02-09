# Bug: `build_submit_preview` finds 0 log files

## Summary

`build_submit_preview()` always returns an empty `log_files` list, causing every submission to fail with "No trajectory files found to upload."

## Root Cause

`inspect_ai.log.list_eval_logs()` returns `EvalLogInfo` objects, not file paths. The `.name` attribute contains a `file:///` URI like:

```
file:///Users/.../job_20260206_171349/openrouter/anthropic/claude-opus-4.6/2026-02-06T17-13-53+00-00_telemath_gPHaoDf2tjWBL8ViRfF66R.json
```

The current code does `Path(str(log_ref))`, which stringifies the entire `EvalLogInfo` dataclass repr — not the file path. The resulting `Path` never exists, so every file is silently skipped.

## Location

`src/satellite/services/submit/__init__.py`, `build_submit_preview()`:

```python
# Bug — str(log_ref) is the dataclass repr, not a path
for log_ref in list_eval_logs(str(job_dir), recursive=True):
    log_path = Path(str(log_ref))       # <-- wrong
    if log_path.exists():
        log_files.append(log_path)
```

## Fix

Extract `.name` from the `EvalLogInfo` and convert the `file:///` URI to a filesystem path:

```python
from urllib.parse import unquote, urlparse

for log_ref in list_eval_logs(str(job_dir), recursive=True):
    log_path = Path(unquote(urlparse(log_ref.name).path))
    if log_path.exists():
        log_files.append(log_path)
```

Or the simpler variant (safe when paths contain no percent-encoded characters):

```python
for log_ref in list_eval_logs(str(job_dir), recursive=True):
    log_path = Path(log_ref.name.removeprefix("file://"))
    if log_path.exists():
        log_files.append(log_path)
```

## Impact

- Submissions always fail with "No trajectory files found to upload"
- The eligibility check passes fine (it reads scores from logs via a different code path in `job_manager.py`)
- No data loss — the logs exist on disk, they're just never collected

## Reproduction

```python
from satellite.services.evals.job_manager import JobManager
from satellite.services.submit import get_eligible_models, build_submit_preview

jm = JobManager()
eligible = get_eligible_models(jm)
job, model, scores = eligible[0]
preview = build_submit_preview(job, model, scores, jm.jobs_dir)
print(len(preview.log_files))  # 0 — should be 5
```
