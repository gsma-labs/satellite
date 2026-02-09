"""Widgets package - all custom widgets for satellite.

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
from satellite.widgets.julia_set import JuliaSet
from satellite.widgets.grid_select import GridSelect
from satellite.widgets.eval_box import EvalBox
from satellite.widgets.eval_list import EvalList, EvalListItem

# Utility widgets
from satellite.widgets.throbber import Throbber
from satellite.widgets.flash import Flash
from satellite.widgets.checklist_item import ChecklistItem

# Evals container widgets
from satellite.widgets.badge_label import BadgeLabel
from satellite.widgets.eval_sub_option import EvalSubOption
from satellite.widgets.evals_container import EvalsContainer

# Tab widgets
from satellite.widgets.tab_item import TabItem
from satellite.widgets.tab_header import TabHeader

# Model configuration widgets
from satellite.widgets.configured_models_list import (
    ConfiguredModelItem,
    ConfiguredModelsList,
)

# Environment variable widgets
from satellite.widgets.env_var_item import EnvVarItem

# Dropdown widgets
from satellite.widgets.dropdown_button import DropdownButton

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
    # Dropdown widgets
    "DropdownButton",
]
