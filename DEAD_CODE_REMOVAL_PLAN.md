# Dead Code Removal — Agent Team Plan

## Objective

Remove all dead code identified by the analysis, using a 3-teammate agent team with plan approval gating. Final result: a single commit on a new branch (not `main`).

---

## Team Structure

| Role | Name | Model | Responsibility |
|---|---|---|---|
| **Lead** | `lead` | Opus | Orchestrates tasks, reviews teammate plans, synthesizes results, creates final commit |
| **Teammate 1** | `widgets-cleaner` | Sonnet | Removes unused widget files, modal files, and cleans up `__init__.py` re-exports |
| **Teammate 2** | `services-cleaner` | Sonnet | Removes unused functions in `job_manager.py`, unused constants in `eval_data.py`, deduplicates code in `set_model_modal.py` |
| **Teammate 3** | `verifier` | Sonnet | Verifies no references remain to removed code, checks imports resolve, runs the app's import chain |

All teammates require **plan approval** before making changes.

---

## Branch Strategy

1. Lead creates branch `chore/remove-dead-code` from `ui/features` (the current branch)
2. All work happens on that branch
3. Lead creates a single commit when all removals are verified

---

## Dead Code Inventory

### A. Unused Files (7 files) — `widgets-cleaner`

| File | Why it's dead |
|---|---|
| `widgets/throbber.py` | Never instantiated in the app |
| `widgets/flash.py` | Never instantiated in the app |
| `widgets/checklist_item.py` | Never instantiated in the app |
| `widgets/evals_container.py` | Superseded by `TabbedEvalsModal` |
| `widgets/eval_sub_option.py` | Only used by the unused `EvalsContainer` |
| `widgets/badge_label.py` | Only used by other dead widgets |
| `modals/scripts/evals_modal.py` | Superseded by `TabbedEvalsModal`, never imported |

### B. Unused Functions (3 functions) — `services-cleaner`

| Function | File | Line |
|---|---|---|
| `_has_eval_metadata` | `services/evals/job_manager.py` | 33 |
| `_task_name` | `services/evals/job_manager.py` | 38 |
| `aggregate_status` | `services/evals/job_manager.py` | 107 |

### C. Unused Constants (2 variables) — `services-cleaner`

| Variable | File | Line |
|---|---|---|
| `AGENTS` | `examples/eval_data.py` | 271 |
| `AGENTS_BY_SHORTCUT` | `examples/eval_data.py` | 330 |

### D. Duplicated Code — `services-cleaner`

| Location | Description |
|---|---|
| `modals/scripts/set_model_modal.py` lines 346-377 | Model name validation + `ModelConfig` creation duplicated between `cred_type != "base_url"` and `base_url` branches |

---

## Task Breakdown

### Phase 1: Planning (plan approval required)

| ID | Task | Owner | Blocked by |
|---|---|---|---|
| 1 | Plan removal of 7 unused widget/modal files + cleanup of `__init__.py` exports and `__all__` lists | `widgets-cleaner` | — |
| 2 | Plan removal of 3 unused functions, 2 unused constants, and deduplication of `set_model_modal.py` | `services-cleaner` | — |
| 3 | Plan verification strategy: list every symbol to check, grep patterns, and import-chain test | `verifier` | — |

> Lead reviews and approves/rejects each plan before implementation proceeds.

### Phase 2: Implementation (after plan approval)

| ID | Task | Owner | Blocked by |
|---|---|---|---|
| 4 | Delete 7 files, remove their entries from `widgets/__init__.py`, `modals/__init__.py`, and any `__all__` lists | `widgets-cleaner` | 1 |
| 5 | Remove 3 functions from `job_manager.py`, remove `AGENTS`/`AGENTS_BY_SHORTCUT` from `eval_data.py` + their `__all__` entries, refactor duplicated validation in `set_model_modal.py` | `services-cleaner` | 2 |
| 6 | Remove any TCSS rules that only target deleted widgets (e.g., `Throbber`, `Flash`, `ChecklistItem`, `EvalsContainer`, `EvalSubOption`, `BadgeLabel`, `EvalsModal`) | `widgets-cleaner` | 4 |

### Phase 3: Verification

| ID | Task | Owner | Blocked by |
|---|---|---|---|
| 7 | Grep entire codebase for all removed symbols — confirm zero references remain | `verifier` | 4, 5, 6 |
| 8 | Run `python -c "import satellite"` to verify the import chain doesn't break | `verifier` | 7 |

### Phase 4: Commit (lead only)

| ID | Task | Owner | Blocked by |
|---|---|---|---|
| 9 | Create branch `chore/remove-dead-code`, stage all changes, commit with descriptive message | `lead` | 8 |

---

## Approval Criteria for Lead

When reviewing teammate plans, the lead should:

- **Approve** if the plan lists every file/function/symbol to remove and accounts for all references (imports, `__all__`, TCSS selectors)
- **Reject** if the plan misses cleanup of `__init__.py` re-exports, `__all__` entries, or TCSS rules targeting deleted widgets
- **Reject** if the `set_model_modal.py` refactor changes behavior (it should be extraction only)

---

## Risk Mitigation

- **Plan approval gating** ensures no teammate edits files without lead review
- **Verifier teammate** independently confirms zero dangling references after all removals
- **Import chain test** catches any broken imports before committing
- **Separate branch** keeps `main` and `ui/features` untouched

---

## Expected Outcome

- 7 files deleted (~500-700 lines removed)
- 3 unused functions removed
- 2 unused constants removed
- 1 duplicated code block refactored
- Clean import chain verified
- Single commit on `chore/remove-dead-code` branch
