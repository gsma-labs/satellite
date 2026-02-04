"""Widgets package - all custom widgets for satetoad.

Evaluation interface widgets:
- julia_set.py: Interactive Julia set fractal (mouse controls c parameter!)
- grid_select.py: Navigable grid selection container
- eval_box.py: Evaluation action boxes with selection highlighting
- eval_list.py: To-do style list with arrow key navigation

Trajectory section widgets:
- trajectory_sections.py: Widgets for displaying evaluation data
  - PromptSection: Truncated prompt with expand capability
  - ReasoningSection: Agent reasoning (hidden if encrypted)
  - AnswerSection: Agent's final answer
  - ComparisonSection: Side-by-side Target vs LLM comparison

Utility widgets:
- throbber.py: Custom Visual render, animation
- flash.py: Timer-based visibility toggle
"""

# Evaluation interface widgets
from satetoad.widgets.julia_set import JuliaSet
from satetoad.widgets.grid_select import GridSelect
from satetoad.widgets.eval_box import EvalBox
from satetoad.widgets.eval_list import EvalList, EvalListItem

# Trajectory section widgets
from satetoad.widgets.trajectory_sections import (
    PromptSection,
    ReasoningSection,
    AnswerSection,
    ComparisonSection,
)

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

__all__ = [
    # Evaluation interface
    "JuliaSet",
    "GridSelect",
    "EvalBox",
    "EvalList",
    "EvalListItem",
    # Trajectory sections
    "PromptSection",
    "ReasoningSection",
    "AnswerSection",
    "ComparisonSection",
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
]
