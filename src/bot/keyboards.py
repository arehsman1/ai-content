"""Keyboard builders – single-card opportunity lifecycle."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from src.bot.callback_data import (
    AccountCallback,
    AngleCallback,
    FormatCallback,
    ImageStyleCallback,
    MenuCallback,
    OpportunityCallback,
    PrefsCallback,
    ReviewCallback,
    SuggestCallback,
    ToneCallback,
)
from src.config.constants import (
    ANGLE_LABELS,
    IMAGE_STYLE_LABELS,
    TONE_LABELS,
    AccountType,
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔄 Scan Now"), KeyboardButton(text="📊 Scanner Status")],
            [KeyboardButton(text="🎯 Niche"), KeyboardButton(text="🧪 Demo Opportunity")],
            [KeyboardButton(text="🧹 Reset Preferences"), KeyboardButton(text="❓ Help")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def opportunity_keyboard(opp_id: str) -> InlineKeyboardMarkup:
    """🆕 New opportunity."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Make Post",
                    callback_data=OpportunityCallback(action="approve", opp_id=opp_id).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Skip",
                    callback_data=OpportunityCallback(action="skip", opp_id=opp_id).pack(),
                ),
            ],
        ]
    )


def skipped_keyboard(opp_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Restore",
                    callback_data=OpportunityCallback(action="restore", opp_id=opp_id).pack(),
                ),
                InlineKeyboardButton(
                    text="Delete",
                    callback_data=OpportunityCallback(action="delete", opp_id=opp_id).pack(),
                ),
            ],
        ]
    )


def completed_keyboard(opp_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Rewrite",
                    callback_data=ReviewCallback(action="rewrite", opp_id=opp_id).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎭 Change Tone",
                    callback_data=ReviewCallback(action="change_tone", opp_id=opp_id).pack(),
                ),
                InlineKeyboardButton(
                    text="📚 Change Angle",
                    callback_data=ReviewCallback(action="change_angle", opp_id=opp_id).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✔ Mark as Posted",
                    callback_data=ReviewCallback(action="mark_posted", opp_id=opp_id).pack(),
                ),
            ],
        ]
    )


def posted_keyboard(opp_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👁 View Post",
                    callback_data=OpportunityCallback(action="view", opp_id=opp_id).pack(),
                ),
            ],
        ]
    )


def account_type_keyboard(opp_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆓 Free",
                    callback_data=AccountCallback(
                        account_type=AccountType.FREE, opp_id=opp_id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="⭐ Premium",
                    callback_data=AccountCallback(
                        account_type=AccountType.PREMIUM, opp_id=opp_id
                    ).pack(),
                ),
            ],
        ]
    )


def angle_keyboard(opp_id: str) -> InlineKeyboardMarkup:
    rows = []
    items = list(ANGLE_LABELS.items())
    for i in range(0, len(items), 2):
        row = []
        for key, label in items[i : i + 2]:
            row.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=AngleCallback(angle=key, opp_id=opp_id).pack(),
                )
            )
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tone_keyboard(opp_id: str) -> InlineKeyboardMarkup:
    rows = []
    items = list(TONE_LABELS.items())
    for i in range(0, len(items), 2):
        row = []
        for key, label in items[i : i + 2]:
            row.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=ToneCallback(tone=key, opp_id=opp_id).pack(),
                )
            )
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_keyboard(opp_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Single Post",
                    callback_data=FormatCallback(format="single", opp_id=opp_id).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧵 Thread",
                    callback_data=FormatCallback(format="thread", opp_id=opp_id).pack(),
                ),
            ],
        ]
    )


def image_style_keyboard(opp_id: str) -> InlineKeyboardMarkup:
    rows = []
    items = list(IMAGE_STYLE_LABELS.items())
    for i in range(0, len(items), 2):
        row = []
        for key, label in items[i : i + 2]:
            row.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=ImageStyleCallback(style=key, opp_id=opp_id).pack(),
                )
            )
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def suggest_keyboard(opp_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Use Suggested Settings",
                    callback_data=SuggestCallback(action="use", opp_id=opp_id).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Customize",
                    callback_data=SuggestCallback(action="customize", opp_id=opp_id).pack(),
                ),
            ],
        ]
    )


def reset_prefs_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Yes, reset",
                    callback_data=PrefsCallback(action="reset_confirm").pack(),
                ),
                InlineKeyboardButton(
                    text="❌ No",
                    callback_data=PrefsCallback(action="reset_cancel").pack(),
                ),
            ],
        ]
    )


def after_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Scanner Status",
                    callback_data=MenuCallback(action="status").pack(),
                ),
                InlineKeyboardButton(
                    text="🔄 Scan Now",
                    callback_data=MenuCallback(action="scan").pack(),
                ),
            ]
        ]
    )
