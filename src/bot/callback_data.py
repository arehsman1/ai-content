"""Typed callback data factories for inline buttons."""

from aiogram.filters.callback_data import CallbackData


class OpportunityCallback(CallbackData, prefix="opp"):
    action: str  # approve | skip | rewrite_angle | restore | delete | mark_posted | view
    opp_id: str


class MenuCallback(CallbackData, prefix="menu"):
    action: str


class AccountCallback(CallbackData, prefix="acct"):
    account_type: str
    opp_id: str


class AngleCallback(CallbackData, prefix="angle"):
    angle: str
    opp_id: str


class ToneCallback(CallbackData, prefix="tone"):
    tone: str
    opp_id: str


class FormatCallback(CallbackData, prefix="fmt"):
    format: str
    opp_id: str


class ImageStyleCallback(CallbackData, prefix="img"):
    style: str
    opp_id: str


class ReviewCallback(CallbackData, prefix="rev"):
    action: str  # rewrite | change_angle | change_tone | mark_posted | regen_image
    opp_id: str


class SuggestCallback(CallbackData, prefix="sug"):
    action: str
    opp_id: str


class PrefsCallback(CallbackData, prefix="prefs"):
    action: str
