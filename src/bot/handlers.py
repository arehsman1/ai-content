"""
Telegram handlers – single-message opportunity lifecycle.
Every opportunity is ONE message that is edited through its states.
"""

from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from src.ai.writing_engine import AIWritingEngine
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
from src.bot.keyboards import (
    account_type_keyboard,
    after_action_keyboard,
    angle_keyboard,
    completed_keyboard,
    format_keyboard,
    image_style_keyboard,
    main_menu_keyboard,
    opportunity_keyboard,
    posted_keyboard,
    reset_prefs_confirm_keyboard,
    skipped_keyboard,
    suggest_keyboard,
    tone_keyboard,
)
from src.bot.states import WritingWorkflow
from src.bot.store import store
from src.config.constants import (
    ANGLE_LABELS,
    IMAGE_STYLE_LABELS,
    TONE_LABELS,
    AccountType,
    ContentStatus,
    ImageStyle,
    SourceType,
    Tone,
    WritingAngle,
)
from src.config.settings import AppSettings
from src.utils.preferences import (
    get_suggestions,
    record_generation,
    reset_preferences,
)

router = Router(name="main")


# ---------------------------------------------------------------------------
# Helpers – always edit the opportunity card, never spawn new workflow msgs
# ---------------------------------------------------------------------------

async def _edit_card(
    message: Message,
    text: str,
    reply_markup=None,
) -> None:
    try:
        await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        # "message is not modified" is fine
        if "not modified" not in str(exc).lower():
            logger.debug("edit_card failed: {}", exc)


# ---------------------------------------------------------------------------
# Basic commands
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(message: Message, settings: AppSettings, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user
    text = (
        f"👋 <b>Welcome, {user.first_name or 'there'}!</b>\n\n"
        f"<b>{settings.app_name}</b> is ready.\n\n"
        "Each opportunity is a single task card that updates in place.\n"
        "Nothing is ever published automatically.\n\n"
        "Use the menu or type /help."
    )
    await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


@router.message(Command("help"))
@router.message(F.text == "❓ Help")
async def cmd_help(message: Message) -> None:
    text = (
        "<b>Commands</b>\n"
        "/start /status /niche /scan /demo /help\n\n"
        "<b>Opportunity cards</b>\n"
        "Each opportunity is ONE message that changes status:\n"
        "🆕 New → ✍ Writing → ✅ Post Ready → 📌 Posted\n\n"
        "Make Post, account, angle, tone, and generation all edit "
        "the same card — no message spam."
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("status"))
@router.message(F.text == "📊 Scanner Status")
async def cmd_status(message: Message, settings: AppSettings) -> None:
    last = (
        store.last_scan_at.strftime("%Y-%m-%d %H:%M UTC")
        if store.last_scan_at
        else "Never"
    )
    text = (
        f"<b>📊 Scanner Status</b>\n\n"
        f"<b>Auto Scan:</b> {'✅' if settings.enable_news_scanner else '❌'}\n"
        f"<b>Frequency:</b> {len(settings.scan_times_list)}×/day "
        f"({', '.join(settings.scan_times_list)} UTC)\n"
        f"<b>Last Scan:</b> {last}\n"
        f"<b>Window:</b> Last {settings.news.search_window_days} days\n"
        f"<b>Pending:</b> {store.pending_count()}"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("niche"))
@router.message(F.text == "🎯 Niche")
async def cmd_niche(message: Message, settings: AppSettings) -> None:
    kws = settings.niche_list
    text = (
        "No niche keywords."
        if not kws
        else "<b>🎯 Niche</b>\n\n" + "\n".join(f"• {k}" for k in kws)
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("scan"))
@router.message(F.text == "🔄 Scan Now")
async def cmd_scan(message: Message, settings: AppSettings) -> None:
    if not settings.enable_news_scanner:
        await message.answer("❌ News scanner is disabled.")
        return

    from src.ai.filter_engine import AIFilterEngine
    from src.ai.pipeline import hybrid_filter
    from src.scanners.news_scanner import NewsScanner
    from src.utils.progress import ScanProgress

    bot = message.bot
    progress = ScanProgress(bot, message.chat.id)
    await progress.start(keywords_total=len(settings.niche_list))
    scanner = NewsScanner(settings)
    filter_engine = AIFilterEngine(settings)

    try:
        async def on_collect(**kwargs):
            await progress.stage1_update(**kwargs)

        scan_result = await scanner.scan(progress=on_collect)

        async def on_filter(**kwargs):
            stage = kwargs.get("stage")
            if stage == "python":
                await progress.stage_python(
                    received=kwargs.get("received", 0),
                    passed=kwargs.get("passed", 0),
                    removed=kwargs.get("removed", 0),
                    percent=kwargs.get("percent", 100),
                )
            elif stage == "ai":
                await progress.stage_ai(
                    total=kwargs.get("total", 0),
                    analyzed=kwargs.get("analyzed", 0),
                    passed=kwargs.get("passed", 0),
                    rejected=kwargs.get("rejected", 0),
                    current_title=kwargs.get("current_title", ""),
                    eta_text=kwargs.get("eta_text", ""),
                    percent=kwargs.get("percent", 0),
                )

        passed = await hybrid_filter(
            scan_result.opportunities,
            settings,
            filter_engine,
            progress=on_filter,
        )
        await progress.stage_prepare(approved=len(passed), percent=100)

        for opp in passed:
            h = opp.raw_data.get("content_hash")
            if h:
                store.mark_notified(h)

        store.last_scan_at = datetime.now(timezone.utc)
        await progress.complete(
            articles_found=scan_result.raw_articles,
            unique_articles=scan_result.unique_articles,
            relevant=len(passed),
        )

        for opp in passed:
            msg = await bot.send_message(
                chat_id=message.chat.id,
                text=opp.render_new(),
                reply_markup=opportunity_keyboard(opp.id),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            store.bind_message(opp.id, message.chat.id, msg.message_id)
    except Exception as exc:
        logger.exception("Manual scan failed")
        await progress.fail(reason=str(exc)[:200])


@router.message(Command("demo"))
@router.message(F.text == "🧪 Demo Opportunity")
async def cmd_demo(message: Message) -> None:
    opp = store.add(
        source=SourceType.GOOGLE_NEWS,
        title="OpenAI releases new reasoning model that outperforms previous SOTA",
        summary=(
            "OpenAI announced a model focused on multi-step reasoning with "
            "strong gains on math and coding benchmarks."
        ),
        url="https://example.com/openai-reasoning-model",
        reason="Relevant for AI agents, developer tools, and practical AI builders.",
        suggested_angle="What this means for builders shipping AI features today.",
        matched_keyword="AI tools",
        score=0.92,
    )
    msg = await message.answer(
        opp.render_new(),
        reply_markup=opportunity_keyboard(opp.id),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    store.bind_message(opp.id, message.chat.id, msg.message_id)


@router.message(F.text == "🧹 Reset Preferences")
async def cmd_reset_prefs(message: Message) -> None:
    await message.answer(
        "Reset all learned preferences?",
        reply_markup=reset_prefs_confirm_keyboard(),
    )


# ---------------------------------------------------------------------------
# Skip / Restore / Delete / View
# ---------------------------------------------------------------------------

@router.callback_query(OpportunityCallback.filter(F.action == "skip"))
async def on_skip(callback: CallbackQuery, callback_data: OpportunityCallback) -> None:
    opp = store.get(callback_data.opp_id)
    if not opp:
        await callback.answer("No longer available.", show_alert=True)
        return
    if opp.status == ContentStatus.WRITING:
        await callback.answer("⚠ This opportunity is currently being processed.", show_alert=True)
        return
    store.update_status(opp.id, ContentStatus.SKIPPED)
    await _edit_card(callback.message, opp.render_skipped(), skipped_keyboard(opp.id))
    await callback.answer("Skipped")


@router.callback_query(OpportunityCallback.filter(F.action == "restore"))
async def on_restore(callback: CallbackQuery, callback_data: OpportunityCallback) -> None:
    opp = store.get(callback_data.opp_id)
    if not opp:
        await callback.answer("No longer available.", show_alert=True)
        return
    store.update_status(opp.id, ContentStatus.PENDING)
    opp.writing_step = ""
    await _edit_card(callback.message, opp.render_new(), opportunity_keyboard(opp.id))
    await callback.answer("Restored")


@router.callback_query(OpportunityCallback.filter(F.action == "delete"))
async def on_delete(callback: CallbackQuery, callback_data: OpportunityCallback) -> None:
    opp = store.get(callback_data.opp_id)
    if not opp:
        await callback.answer("Already gone.", show_alert=True)
        return
    store.delete(opp.id)
    await _edit_card(callback.message, f"<b>Status:</b>\n🗑 Deleted\n\n<b>Topic:</b> {opp.title}")
    await callback.answer("Deleted")


@router.callback_query(OpportunityCallback.filter(F.action == "view"))
async def on_view(callback: CallbackQuery, callback_data: OpportunityCallback) -> None:
    opp = store.get(callback_data.opp_id)
    if not opp:
        await callback.answer("No longer available.", show_alert=True)
        return
    await _edit_card(callback.message, opp.render_posted(), posted_keyboard(opp.id))
    await callback.answer()


# ---------------------------------------------------------------------------
# Make Post → start writing on the SAME message
# ---------------------------------------------------------------------------

@router.callback_query(OpportunityCallback.filter(F.action == "approve"))
async def on_make_post(
    callback: CallbackQuery,
    callback_data: OpportunityCallback,
    settings: AppSettings,
    state: FSMContext,
) -> None:
    opp = store.get(callback_data.opp_id)
    if not opp:
        await callback.answer("No longer available.", show_alert=True)
        return

    if opp.status == ContentStatus.WRITING:
        await callback.answer(
            "⚠ This opportunity is currently being processed.", show_alert=True
        )
        return
    if opp.status in {ContentStatus.COMPLETED, ContentStatus.POSTED}:
        await callback.answer(
            "Post already generated. Use Rewrite to make a new version.",
            show_alert=True,
        )
        return

    store.update_status(opp.id, ContentStatus.WRITING)
    opp.writing_step = "Choosing account type..."
    await state.update_data(opp_id=opp.id)
    store.bind_message(opp.id, callback.message.chat.id, callback.message.message_id)

    suggestions = get_suggestions(settings)
    if suggestions:
        angle_l = ANGLE_LABELS.get(suggestions["angle"], suggestions["angle"])
        tone_l = TONE_LABELS.get(suggestions["tone"], suggestions["tone"])
        style_l = IMAGE_STYLE_LABELS.get(
            suggestions.get("image_style", "realistic"), "Realistic"
        )
        acct = "🆓 Free" if suggestions["account_type"] == AccountType.FREE else "⭐ Premium"
        text = (
            f"<b>Status:</b>\n✍ Writing...\n\n"
            f"<b>Topic:</b> {opp.title}\n\n"
            f"<b>Current Step:</b>\n💡 Suggested Settings\n\n"
            f"{acct}\n{angle_l}\n🎭 {tone_l}\n{style_l}\n\n"
            f"<i>Based on your previous choices.</i>\n\n"
            f"<i>ID: {opp.id}</i>"
        )
        await _edit_card(callback.message, text, suggest_keyboard(opp.id))
        await state.set_state(WritingWorkflow.choose_account)
        await callback.answer()
        return

    text = opp.render_writing(step="Choosing account type...")
    await _edit_card(callback.message, text, account_type_keyboard(opp.id))
    await state.set_state(WritingWorkflow.choose_account)
    await callback.answer()


@router.callback_query(SuggestCallback.filter())
async def on_suggest(
    callback: CallbackQuery,
    callback_data: SuggestCallback,
    settings: AppSettings,
    state: FSMContext,
) -> None:
    await callback.answer()
    opp = store.get(callback_data.opp_id)
    if not opp:
        return

    if callback_data.action == "customize":
        await _edit_card(
            callback.message,
            opp.render_writing(step="Choosing account type..."),
            account_type_keyboard(opp.id),
        )
        await state.set_state(WritingWorkflow.choose_account)
        return

    suggestions = get_suggestions(settings)
    if not suggestions:
        await _edit_card(
            callback.message,
            opp.render_writing(step="Choosing account type..."),
            account_type_keyboard(opp.id),
        )
        await state.set_state(WritingWorkflow.choose_account)
        return

    await state.update_data(
        opp_id=opp.id,
        account_type=suggestions["account_type"],
        angle=suggestions["angle"],
        tone=suggestions["tone"],
        image_style=suggestions.get("image_style", ImageStyle.REALISTIC),
        as_thread=False,
    )
    opp.account_type = suggestions["account_type"]
    opp.angle = suggestions["angle"]
    opp.tone = suggestions["tone"]
    opp.image_style = suggestions.get("image_style", ImageStyle.REALISTIC)

    engine = AIWritingEngine(settings)
    recommend = await engine.should_recommend_thread(opp, suggestions["account_type"])
    if recommend:
        await _edit_card(
            callback.message,
            opp.render_writing(step="Thread recommended — choose format"),
            format_keyboard(opp.id),
        )
        await state.set_state(WritingWorkflow.choose_format)
    else:
        await _edit_card(
            callback.message,
            opp.render_writing(step="Choosing image style..."),
            image_style_keyboard(opp.id),
        )
        await state.set_state(WritingWorkflow.choose_image_style)


# ---------------------------------------------------------------------------
# Workflow steps – always edit the same card
# ---------------------------------------------------------------------------

@router.callback_query(AccountCallback.filter(), WritingWorkflow.choose_account)
async def on_account(
    callback: CallbackQuery,
    callback_data: AccountCallback,
    state: FSMContext,
) -> None:
    await callback.answer()
    opp = store.get(callback_data.opp_id)
    if not opp:
        return
    if opp.status != ContentStatus.WRITING:
        await callback.answer("This card is no longer in writing mode.", show_alert=True)
        return

    await state.update_data(account_type=callback_data.account_type, opp_id=callback_data.opp_id)
    opp.account_type = callback_data.account_type
    await _edit_card(
        callback.message,
        opp.render_writing(step="Choosing writing angle..."),
        angle_keyboard(callback_data.opp_id),
    )
    await state.set_state(WritingWorkflow.choose_angle)


@router.callback_query(AngleCallback.filter(), WritingWorkflow.choose_angle)
async def on_angle(
    callback: CallbackQuery,
    callback_data: AngleCallback,
    state: FSMContext,
) -> None:
    await callback.answer()
    opp = store.get(callback_data.opp_id)
    if not opp:
        return
    await state.update_data(angle=callback_data.angle)
    opp.angle = callback_data.angle
    await _edit_card(
        callback.message,
        opp.render_writing(step="Choosing tone..."),
        tone_keyboard(callback_data.opp_id),
    )
    await state.set_state(WritingWorkflow.choose_tone)


@router.callback_query(ToneCallback.filter(), WritingWorkflow.choose_tone)
async def on_tone(
    callback: CallbackQuery,
    callback_data: ToneCallback,
    settings: AppSettings,
    state: FSMContext,
) -> None:
    await callback.answer()
    opp = store.get(callback_data.opp_id)
    if not opp:
        return
    await state.update_data(tone=callback_data.tone)
    opp.tone = callback_data.tone
    data = await state.get_data()
    account_type = data.get("account_type", AccountType.FREE)

    engine = AIWritingEngine(settings)
    recommend = await engine.should_recommend_thread(opp, account_type)
    if recommend:
        await _edit_card(
            callback.message,
            opp.render_writing(step="Thread recommended — choose format"),
            format_keyboard(callback_data.opp_id),
        )
        await state.set_state(WritingWorkflow.choose_format)
    else:
        await state.update_data(as_thread=False)
        await _edit_card(
            callback.message,
            opp.render_writing(step="Choosing image style..."),
            image_style_keyboard(callback_data.opp_id),
        )
        await state.set_state(WritingWorkflow.choose_image_style)


@router.callback_query(FormatCallback.filter(), WritingWorkflow.choose_format)
async def on_format(
    callback: CallbackQuery,
    callback_data: FormatCallback,
    state: FSMContext,
) -> None:
    await callback.answer()
    opp = store.get(callback_data.opp_id)
    if not opp:
        return
    as_thread = callback_data.format == "thread"
    await state.update_data(as_thread=as_thread, thread_choice=as_thread)
    opp.as_thread = as_thread
    await _edit_card(
        callback.message,
        opp.render_writing(step="Choosing image style..."),
        image_style_keyboard(callback_data.opp_id),
    )
    await state.set_state(WritingWorkflow.choose_image_style)


@router.callback_query(ImageStyleCallback.filter(), WritingWorkflow.choose_image_style)
async def on_image_style(
    callback: CallbackQuery,
    callback_data: ImageStyleCallback,
    settings: AppSettings,
    state: FSMContext,
) -> None:
    await callback.answer()
    opp = store.get(callback_data.opp_id)
    if not opp:
        return
    await state.update_data(image_style=callback_data.style)
    opp.image_style = callback_data.style
    await _generate_on_card(callback.message, settings, state, opp)


async def _generate_on_card(
    message: Message,
    settings: AppSettings,
    state: FSMContext,
    opp,
) -> None:
    """Generate post and replace the same opportunity message."""
    data = await state.get_data()
    account_type = data.get("account_type", opp.account_type or AccountType.FREE)
    angle = data.get("angle", opp.angle or WritingAngle.EDUCATIONAL)
    tone = data.get("tone", opp.tone or Tone.PROFESSIONAL)
    as_thread = bool(data.get("as_thread", opp.as_thread))
    image_style = data.get("image_style", opp.image_style or ImageStyle.REALISTIC)

    await _edit_card(
        message,
        opp.render_writing(
            step="Generating X post...",
            percent=40,
            task="Building hook...",
        ),
        None,
    )

    engine = AIWritingEngine(settings)
    try:
        await _edit_card(
            message,
            opp.render_writing(
                step="Generating X post...",
                percent=70,
                task="Writing body...",
            ),
            None,
        )
        result = await engine.generate(
            opp,
            account_type=account_type,
            angle=angle,
            tone=tone,
            as_thread=as_thread,
            image_style=image_style,
        )
    except Exception as exc:
        logger.exception("Generation failed")
        store.update_status(opp.id, ContentStatus.PENDING)
        await _edit_card(
            message,
            opp.render_new() + f"\n\n❌ <b>Generation failed:</b> {exc}",
            opportunity_keyboard(opp.id),
        )
        await state.clear()
        return

    opp.generated_posts = result.posts
    opp.image_prompt = result.image_prompt or ""
    opp.char_counts = result.char_counts
    opp.account_type = account_type
    opp.angle = angle
    opp.tone = tone
    opp.as_thread = as_thread
    opp.image_style = image_style
    store.update_status(opp.id, ContentStatus.COMPLETED)

    await _edit_card(message, opp.render_completed(), completed_keyboard(opp.id))
    await state.set_state(WritingWorkflow.review)


# ---------------------------------------------------------------------------
# Review controls – still the same message
# ---------------------------------------------------------------------------

@router.callback_query(ReviewCallback.filter())
async def on_review(
    callback: CallbackQuery,
    callback_data: ReviewCallback,
    settings: AppSettings,
    state: FSMContext,
) -> None:
    await callback.answer()
    opp = store.get(callback_data.opp_id)
    if not opp:
        return

    action = callback_data.action

    if action == "mark_posted":
        store.update_status(opp.id, ContentStatus.POSTED)
        opp.posted_at = datetime.now(timezone.utc)
        # record prefs once when user finishes
        if opp.account_type and opp.angle and opp.tone:
            record_generation(
                settings,
                account_type=opp.account_type,
                angle=opp.angle,
                tone=opp.tone,
                image_style=opp.image_style or None,
                thread_accepted=opp.as_thread if opp.as_thread else None,
            )
        await _edit_card(callback.message, opp.render_posted(), posted_keyboard(opp.id))
        await state.clear()
        return

    if action == "change_angle":
        if opp.status not in {ContentStatus.COMPLETED, ContentStatus.WRITING}:
            return
        store.update_status(opp.id, ContentStatus.WRITING)
        await state.update_data(
            opp_id=opp.id,
            account_type=opp.account_type or AccountType.FREE,
            tone=opp.tone or Tone.PROFESSIONAL,
            image_style=opp.image_style or ImageStyle.REALISTIC,
            as_thread=opp.as_thread,
        )
        await _edit_card(
            callback.message,
            opp.render_writing(step="Choosing writing angle..."),
            angle_keyboard(opp.id),
        )
        await state.set_state(WritingWorkflow.choose_angle)
        return

    if action == "change_tone":
        if opp.status not in {ContentStatus.COMPLETED, ContentStatus.WRITING}:
            return
        store.update_status(opp.id, ContentStatus.WRITING)
        await state.update_data(
            opp_id=opp.id,
            account_type=opp.account_type or AccountType.FREE,
            angle=opp.angle or WritingAngle.EDUCATIONAL,
            image_style=opp.image_style or ImageStyle.REALISTIC,
            as_thread=opp.as_thread,
        )
        await _edit_card(
            callback.message,
            opp.render_writing(step="Choosing tone..."),
            tone_keyboard(opp.id),
        )
        await state.set_state(WritingWorkflow.choose_tone)
        return

    if action == "rewrite":
        if opp.status not in {ContentStatus.COMPLETED, ContentStatus.WRITING}:
            return
        store.update_status(opp.id, ContentStatus.WRITING)
        await state.update_data(
            opp_id=opp.id,
            account_type=opp.account_type or AccountType.FREE,
            angle=opp.angle or WritingAngle.EDUCATIONAL,
            tone=opp.tone or Tone.PROFESSIONAL,
            image_style=opp.image_style or ImageStyle.REALISTIC,
            as_thread=opp.as_thread,
        )
        await _edit_card(
            callback.message,
            opp.render_writing(step="Rewriting...", percent=30, task="Fresh version..."),
            None,
        )
        await _generate_on_card(callback.message, settings, state, opp)
        return


# ---------------------------------------------------------------------------
# Prefs + menu
# ---------------------------------------------------------------------------

@router.callback_query(PrefsCallback.filter())
async def on_prefs(
    callback: CallbackQuery,
    callback_data: PrefsCallback,
    settings: AppSettings,
) -> None:
    await callback.answer()
    if callback_data.action == "reset_confirm":
        reset_preferences(settings)
        await callback.message.answer("✅ Preferences reset.")
    else:
        await callback.message.answer("Reset cancelled.")


@router.callback_query(MenuCallback.filter(F.action == "status"))
async def on_menu_status(callback: CallbackQuery, settings: AppSettings) -> None:
    await cmd_status(callback.message, settings)
    await callback.answer()


@router.callback_query(MenuCallback.filter(F.action == "scan"))
async def on_menu_scan(callback: CallbackQuery, settings: AppSettings) -> None:
    await cmd_scan(callback.message, settings)
    await callback.answer()


@router.message()
async def fallback_message(message: Message) -> None:
    await message.answer("Use the menu buttons or type /help.")
