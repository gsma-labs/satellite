"""Widgets package - all custom widgets for satellite.

Evaluation interface widgets:
- julia_set.py: Interactive Julia set fractal (mouse controls c parameter!)
- grid_select.py: Navigable grid selection container
- eval_box.py: Evaluation action boxes with selection highlighting
- eval_list.py: To-do style list with arrow key navigation
"""

# Evaluation interface widgets
from satellite.widgets.julia_set import JuliaSet
from satellite.widgets.grid_select import GridSelect
from satellite.widgets.eval_box import EvalBox
from satellite.widgets.eval_list import EvalList, EvalListItem

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
