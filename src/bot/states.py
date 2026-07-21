"""
FSM states for the V1.2 guided writing workflow.
"""

from aiogram.fsm.state import State, StatesGroup


class WritingWorkflow(StatesGroup):
    """Multi-step post generation after the user presses Make Post."""

    choose_account = State()
    choose_angle = State()
    choose_tone = State()
    choose_format = State()  # single vs thread (when AI recommends thread)
    choose_image_style = State()
    review = State()  # post generated, waiting for Use / Rewrite / etc.
