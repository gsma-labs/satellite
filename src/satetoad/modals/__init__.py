"""Modal dialogs for the Satetoad TUI.

This module contains modal screens that overlay the main interface
for focused user interactions like configuration and selection.

All modals follow Toad's ModalScreen pattern:
- Inherit from ModalScreen[ReturnType] for typed return values
- Use push_screen() to display with automatic backdrop overlay
- Dismiss with dismiss(value) to return data to caller
"""

from .set_model_modal import ModelConfig, SetModelModal
from .run_evals_modal import RunEvalsModal
from .leaderboard_modal import LeaderboardModal
from .submit_modal import SubmitData, SubmitModal
from .evals_modal import EvalsModal, EvalsOptionItem
from .job_list_modal import JobListModal, JobListItem
from .job_detail_modal import JobDetailModal
from .tabbed_evals_modal import TabbedEvalsModal

__all__ = [
    "ModelConfig",
    "SetModelModal",
    "RunEvalsModal",
    "LeaderboardModal",
    "SubmitData",
    "SubmitModal",
    "EvalsModal",
    "EvalsOptionItem",
    "JobListModal",
    "JobListItem",
    "JobDetailModal",
    "TabbedEvalsModal",
]
