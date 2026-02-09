# ProgressBar Animation Reset Bug

## Symptom

The progress bar in `JobListModal` constantly restarts its animation — sliding from left to right every 2 seconds instead of holding steady.

## Root Causes

### 1. `_sync_progress_bar` calls `bar.update()` every poll even when nothing changed

Every 2s the poll timer fires `_refresh_jobs` → `_update_existing_items` → `item.update_job(job)` → `_sync_progress_bar()`.

`_sync_progress_bar` unconditionally calls `bar.update(total=X, progress=Y)`. Even if X and Y are identical to last time, Textual's `ProgressBar.update()` triggers a re-render that **resets the CSS animation**. The bar snaps back to position 0 and slides right again.

**Before (broken):**
```python
def _sync_progress_bar(self) -> None:
    bar = self.query_one(ProgressBar)
    if self._job.status == "success":
        bar.update(total=100, progress=100)  # called every 2s even if already 100/100
        return
    if self._job.total_samples > 0:
        bar.update(total=self._job.total_samples, progress=self._job.completed_samples)
```

**After (fixed):**
```python
def _sync_progress_bar(self) -> None:
    total, progress = self._desired_bar_values()
    if total == self._last_bar_total and progress == self._last_bar_progress:
        return  # nothing changed, don't touch the bar
    self._last_bar_total = total
    self._last_bar_progress = progress
    bar = self.query_one(ProgressBar)
    if total is None:
        return
    bar.update(total=total, progress=progress)
```

Track `_last_bar_total` and `_last_bar_progress` on `JobListItem.__init__`. Only call `bar.update()` when the values actually differ.

### 2. `_job_ids_changed` uses ordered list comparison — reordering triggers full rebuild

`JobManager.list_jobs()` sorts running jobs first. When a job finishes (running → success), it moves down in the sort. The ordered ID comparison sees a different list → triggers `_rebuild_job_list` → all widgets torn down and remounted → all ProgressBars restart from scratch.

```
Poll 1: [jobs_1(running), jobs_2(success)]   # running first
Poll 2: [jobs_2(running), jobs_1(success)]   # jobs_1 finished, moved down
# [jobs_1, jobs_2] != [jobs_2, jobs_1] → True → full rebuild
```

**Before (broken):**
```python
def _job_ids_changed(self, new_jobs: list[Job]) -> bool:
    old_ids = [j.id for j in self._jobs]   # ordered list
    new_ids = [j.id for j in new_jobs]
    return old_ids != new_ids
```

**After (fixed):**
```python
def _job_ids_changed(self, new_jobs: list[Job]) -> bool:
    old_ids = {j.id for j in self._jobs}   # set — order doesn't matter
    new_ids = {j.id for j in new_jobs}
    return old_ids != new_ids
```

Now only actual additions/removals trigger a rebuild.

### 3. `_update_existing_items` zips by position — wrong pairing when order shifts

Even with the set fix above, the in-place update path paired items by list position. If sort order changed between polls, job A's data would be pushed into job B's widget.

**Before (broken):**
```python
def _update_existing_items(self, new_jobs: list[Job]) -> None:
    items = list(self.query(JobListItem))
    for item, job in zip(items, new_jobs):  # paired by position
        item.update_job(job)
```

**After (fixed):**
```python
def _update_existing_items(self, new_jobs: list[Job]) -> None:
    items_by_id = {item.job_id: item for item in self.query(JobListItem)}
    for job in new_jobs:
        item = items_by_id.get(job.id)  # matched by ID
        if item is not None:
            item.update_job(job)
```

## Files Changed

- `src/satetoad/modals/scripts/job_list_modal.py`
- `src/satetoad/modals/scripts/tabbed_evals_modal.py` (same pattern)

## Verification

1. `uv run make lint` — passes
2. Open View Progress with a running job — bar should animate smoothly without resetting every 2s
3. Let a job finish — bar should freeze at final position, no rebuild flicker
