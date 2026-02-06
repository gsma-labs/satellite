"""Modal dialogs for the Satetoad TUI.

This module contains modal screens that overlay the main interface
for focused user interactions like configuration and selection.

All modals follow Toad's ModalScreen pattern:
- Inherit from ModalScreen[ReturnType] for typed return values
- Use push_screen() to display with automatic backdrop overlay
- Dismiss with dismiss(value) to return data to caller
"""

from satetoad.services.config import ModelConfig
from .scripts.set_model_modal import SetModelModal
from .scripts.leaderboard_modal import LeaderboardModal
from .scripts.submit_modal import SubmitData, SubmitModal
from .scripts.evals_modal import EvalsModal, EvalsOptionItem
from .scripts.job_list_modal import JobListModal, JobListItem
from .scripts.job_detail_modal import JobDetailModal
from .scripts.tabbed_evals_modal import TabbedEvalsModal
from .scripts.env_vars_modal import EnvVarsModal

__all__ = [
    "ModelConfig",
    "SetModelModal",
    "LeaderboardModal",
    "SubmitData",
    "SubmitModal",
    "EvalsModal",
    "EvalsOptionItem",
    "JobListModal",
    "JobListItem",
    "JobDetailModal",
    "TabbedEvalsModal",
    "EnvVarsModal",
]
