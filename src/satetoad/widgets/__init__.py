"""Widgets package - all custom widgets for satetoad.

Evaluation interface widgets:
- julia_set.py: Interactive Julia set fractal (mouse controls c parameter!)
- grid_select.py: Navigable grid selection container
- eval_box.py: Evaluation action boxes with selection highlighting
- eval_list.py: To-do style list with arrow key navigation

Utility widgets:
- throbber.py: Custom Visual render, animation
- flash.py: Timer-based visibility toggle
"""

# Evaluation interface widgets
from satetoad.widgets.julia_set import JuliaSet
from satetoad.widgets.grid_select import GridSelect
from satetoad.widgets.eval_box import EvalBox
from satetoad.widgets.eval_list import EvalList, EvalListItem

# Utility widgets
from satetoad.widgets.throbber import Throbber
from satetoad.widgets.flash import Flash
from satetoad.widgets.checklist_item import ChecklistItem

# Evals container widgets
from satetoad.widgets.badge_label import BadgeLabel
from satetoad.widgets.eval_sub_option import EvalSubOption
from satetoad.widgets.evals_container import EvalsContainer

# Tab widgets
from satetoad.widgets.tab_item import TabItem
from satetoad.widgets.tab_header import TabHeader

# Model configuration widgets
from satetoad.widgets.configured_models_list import (
    ConfiguredModelItem,
    ConfiguredModelsList,
)

# Environment variable widgets
from satetoad.widgets.env_var_item import EnvVarItem

# Agent widgets
from satetoad.widgets.agent_item import AgentItem, pill
from satetoad.widgets.agent_list import AgentList

# Dropdown widgets
from satetoad.widgets.dropdown_button import DropdownButton

__all__ = [
    # Evaluation interface
    "JuliaSet",
    "GridSelect",
    "EvalBox",
    "EvalList",
    "EvalListItem",
    # Utility
    "Throbber",
    "Flash",
    "ChecklistItem",
    # Evals container
    "BadgeLabel",
    "EvalSubOption",
    "EvalsContainer",
    # Tab widgets
    "TabItem",
    "TabHeader",
    # Model configuration
    "ConfiguredModelItem",
    "ConfiguredModelsList",
    # Environment variable
    "EnvVarItem",
    # Agent widgets
    "AgentItem",
    "AgentList",
    "pill",
    # Dropdown widgets
    "DropdownButton",
]
