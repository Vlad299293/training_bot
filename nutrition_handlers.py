"""Обработчики модуля питания."""

import json
import logging
from datetime import datetime
from aiogram import Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database import Database
from states import NutritionSetupStates, BodyWeightStates
from keyboards import (
    main_menu_kb, nutrition_menu_kb, gender_kb, activity_kb,
    phase_kb, budget_kb, training_day_kb, skip_kb
)
from nutrition import (
    calculate_kbju, format_kbju_message,
    generate_weekly_menu, format_day_plan, generate_shopping_list_from_menu
)

logger = logging.getLogger(__name__)

# Кэш недельного меню в памяти: user_id -> {"menu": dict, "date": str}
weekly_menu_cache = {}


def _get_today_index() -> int:
    """0=пн, 6=вс"""
    return datetime.now().weekday()


def _get_week_key() -> str:
    """Ключ текущей недели для кэша."""
    now = datetime.now()
    return f"{now.year}-W{now.isocalendar()[1]}"


async def _get_or_generate_menu(user_id: int, db: Database) -> dict | None:
    """Возвращает меню из кэша или генерирует новое."""
    week_key = _get_week_key()
    cached = weekly_menu_cache.get(user_id)

    if cached and cached.get("week") == week_key:
        return cached["menu"]

    # Генерируем новое меню
    profile = await db.get_nutrition_profile(user_id)
    if not profile:
        return None

    kbju = calculate_kbju(profile)
    menu = generate_weekly_menu(profile, kbju)

    weekly_menu_cache[user_id] = {"menu": menu, "week": week_key}
    return menu


def register_nutrition_handlers(dp: Dispatcher, db: Database):

    @dp.message(F.text == "🍽️ Питание")
    async def nutrition_menu(msg: Message):
        profile = await db.get_nutrition_profile(msg.from_user.id)
        if not profile:
            await msg.answer(
                "🍽️ *Модуль питания*\n\n"
                "Настрой профиль — займёт 1 минуту.\n"
                "ИИ рассчитает КБЖУ по формуле Миффлина-Сан Жеора и составит "
                "персональный план питания под твои цели.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⚙️ Настроить профиль", callback_data="nutrition_setup")
                ]])
            )
        else:
            await msg.answer("🍽️ *Меню питания*", parse_mode="Markdown",
                             reply_markup=nutrition_menu_kb())

    @dp.message(F.text == "🔙 Главное меню")
    async def back_to_main(msg: Message):
        await msg.answer("Главное меню:", reply_markup=main_menu_kb())

    # ── Настройка профиля ─────────────────────────────────────────────────────

    @dp.callback_query(F.data == "nutrition_setup")
    async def nutrition_setup_start(call: CallbackQuery, state: FSMContext):
        await state.set_state(NutritionSetupStates.waiting_gender)
        await call.message.answer("⚙️ *Настройка профиля питания*\n\nШаг 1/8 — Укажи пол:",
                                  parse_mode="Markdown", reply_markup=gender_kb())

    @dp.message(F.text == "⚙️ Настройки питания")
    async def nutrition_settings(msg: Message, state: FSMContext):
        await state.set_state(NutritionSetupStates.waiting_gender)
        await msg.answer("⚙️ *Обновление профиля*\n\nШаг 1/8 — Укажи пол:",
                         parse_mode="Markdown", reply_markup=gender_kb())

    @dp.callback_query(NutritionSetupStates.waiting_gender, F.data.startswith("gender:"))
    async def setup_gender(call: CallbackQuery, state: FSMContext):
        await state.update_data(gender=call.data.split(":")[1])
        await state.set_state(NutritionSetupStates.waiting_age)
        await call.message.answer("Шаг 2/8 — Введи возраст (лет):")

    @dp.message(NutritionSetupStates.waiting_age)
    async def setup_age(msg: Message, state: FSMContext):
        try:
            age = int(msg.text.strip())
            if not (10 <= age <= 100): raise ValueError
        except ValueError:
            await msg.answer("Введи корректный возраст (от 10 до 100)")
            return
        await state.update_data(age=age)
        await state.set_state(NutritionSetupStates.waiting_weight)
        await msg.answer("Шаг 3/8 — Введи текущий вес (кг):\n_(например: 82 или 82.5)_",
                         parse_mode="Markdown")

    @dp.message(NutritionSetupStates.waiting_weight)
    async def setup_weight(msg: Message, state: FSMContext):
        try:
            weight = float(msg.text.strip().replace(",", "."))
            if not (30 <= weight <= 300): raise ValueError
        except ValueError:
            await msg.answer("Введи корректный вес (от 30 до 300)")
            return
        await state.update_data(weight=weight)
        await db.save_body_weight(msg.from_user.id, weight)
        await state.set_state(NutritionSetupStates.waiting_height)
        await msg.answer("Шаг 4/8 — Введи рост (см):\n_(например: 180)_",
                         parse_mode="Markdown")

    @dp.message(NutritionSetupStates.waiting_height)
    async def setup_height(msg: Message, state: FSMContext):
        try:
            height = int(msg.text.strip())
            if not (100 <= height <= 250): raise ValueError
        except ValueError:
            await msg.answer("Введи корректный рост (от 100 до 250)")
            return
        await state.update_data(height=height)
        await state.set_state(NutritionSetupStates.waiting_activity)
        await msg.answer("Шаг 5/8 — Уровень физической активности:",
                         reply_markup=activity_kb())

    @dp.callback_query(NutritionSetupStates.waiting_activity, F.data.startswith("activity:"))
    async def setup_activity(call: CallbackQuery, state: FSMContext):
        await state.update_data(activity=call.data.split(":")[1])
        await state.set_state(NutritionSetupStates.waiting_phase)
        await call.message.answer("Шаг 6/8 — Выбери цель:", reply_markup=phase_kb())

    @dp.callback_query(NutritionSetupStates.waiting_phase, F.data.startswith("phase:"))
    async def setup_phase(call: CallbackQuery, state: FSMContext):
        await state.update_data(phase=call.data.split(":")[1])
        await state.set_state(NutritionSetupStates.waiting_allergies)
        await call.message.answer(
            "Шаг 7/8 — Укажи аллергены или продукты которые не ешь:\n"
            "_(например: глютен, лактоза, орехи)_\n\nИли пропусти:",
            parse_mode="Markdown", reply_markup=skip_kb()
        )

    @dp.message(NutritionSetupStates.waiting_allergies)
    async def setup_allergies(msg: Message, state: FSMContext):
        await state.update_data(allergies=[a.strip() for a in msg.text.split(",") if a.strip()])
        await state.set_state(NutritionSetupStates.waiting_preferences)
        await msg.answer("Шаг 8/8 — Пищевые предпочтения?\n"
                         "_(например: не ем рыбу, люблю курицу)_\n\nИли пропусти:",
                         parse_mode="Markdown", reply_markup=skip_kb())

    @dp.callback_query(NutritionSetupStates.waiting_allergies, F.data == "skip")
    async def skip_allergies(call: CallbackQuery, state: FSMContext):
        await state.update_data(allergies=[])
        await state.set_state(NutritionSetupStates.waiting_preferences)
        await call.message.answer("Шаг 8/8 — Пищевые предпочтения?\n"
                                  "_(например: не ем рыбу, люблю курицу)_\n\nИли пропусти:",
                                  parse_mode="Markdown", reply_markup=skip_kb())

    @dp.message(NutritionSetupStates.waiting_preferences)
    async def setup_preferences(msg: Message, state: FSMContext):
        await state.update_data(preferences=[p.strip() for p in msg.text.split(",") if p.strip()])
        await state.set_state(NutritionSetupStates.waiting_budget)
        await msg.answer("Последний шаг — бюджет на питание:", reply_markup=budget_kb())

    @dp.callback_query(NutritionSetupStates.waiting_preferences, F.data == "skip")
    async def skip_preferences(call: CallbackQuery, state: FSMContext):
        await state.update_data(preferences=[])
        await state.set_state(NutritionSetupStates.waiting_budget)
        await call.message.answer("Последний шаг — бюджет на питание:", reply_markup=budget_kb())

    @dp.callback_query(NutritionSetupStates.waiting_budget, F.data.startswith("budget:"))
    async def setup_budget(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        await state.clear()
        profile = {
            "gender": data["gender"], "age": data["age"],
            "weight": data["weight"], "height": data["height"],
            "activity": data["activity"], "phase": data["phase"],
            "allergies": data.get("allergies", []),
            "preferences": data.get("preferences", []),
            "budget": call.data.split(":")[1],
        }
        await db.save_nutrition_profile(call.from_user.id, profile)
        # Сбрасываем кэш меню при обновлении профиля
        weekly_menu_cache.pop(call.from_user.id, None)
        kbju = calculate_kbju(profile)
        await call.message.answer(
            "✅ *Профиль сохранён!*\n\n" + format_kbju_message(profile, kbju),
            parse_mode="Markdown", reply_markup=nutrition_menu_kb()
        )

    # ── КБЖУ ─────────────────────────────────────────────────────────────────

    @dp.message(F.text == "📊 Мой КБЖУ")
    async def show_kbju(msg: Message):
        profile = await db.get_nutrition_profile(msg.from_user.id)
        if not profile:
            await msg.answer("Сначала настрой профиль.",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                 InlineKeyboardButton(text="⚙️ Настроить", callback_data="nutrition_setup")
                             ]]))
            return
        kbju = calculate_kbju(profile)
        await msg.answer(format_kbju_message(profile, kbju), parse_mode="Markdown")

    # ── План питания на сегодня ───────────────────────────────────────────────

    @dp.message(F.text == "🍽️ План питания на сегодня")
    async def meal_plan_today(msg: Message):
        profile = await db.get_nutrition_profile(msg.from_user.id)
        if not profile:
            await msg.answer("Сначала настрой профиль.",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                 InlineKeyboardButton(text="⚙️ Настроить", callback_data="nutrition_setup")
                             ]]))
            return

        await msg.answer("🤖 Составляю план питания на неделю, это займёт ~30 секунд...")
        try:
            menu = await _get_or_generate_menu(msg.from_user.id, db)
            if not menu:
                await msg.answer("❌ Ошибка. Попробуй снова.")
                return
            day_index = _get_today_index()
            plan_text = format_day_plan(menu, day_index)
            await msg.answer(plan_text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Ошибка генерации плана питания: {e}")
            await msg.answer("❌ Ошибка при генерации. Попробуй снова.")

    # ── Список покупок ────────────────────────────────────────────────────────

    @dp.message(F.text == "🛒 Список покупок")
    async def shopping_list(msg: Message):
        profile = await db.get_nutrition_profile(msg.from_user.id)
        if not profile:
            await msg.answer("Сначала настрой профиль.",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                 InlineKeyboardButton(text="⚙️ Настроить", callback_data="nutrition_setup")
                             ]]))
            return

        await msg.answer("🤖 Составляю список покупок на основе меню недели...")
        try:
            menu = await _get_or_generate_menu(msg.from_user.id, db)
            if not menu:
                await msg.answer("❌ Ошибка. Попробуй снова.")
                return
            shopping = generate_shopping_list_from_menu(menu)
            await msg.answer(shopping, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await msg.answer("❌ Ошибка при генерации. Попробуй снова.")

    # ── Обновить меню вручную ─────────────────────────────────────────────────

    @dp.message(F.text == "🔄 Обновить меню")
    async def refresh_menu(msg: Message):
        weekly_menu_cache.pop(msg.from_user.id, None)
        await msg.answer("🤖 Генерирую новое меню на неделю...")
        try:
            menu = await _get_or_generate_menu(msg.from_user.id, db)
            if not menu:
                await msg.answer("❌ Ошибка. Попробуй снова.")
                return
            day_index = _get_today_index()
            plan_text = format_day_plan(menu, day_index)
            await msg.answer("✅ Меню обновлено!\n\n" + plan_text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await msg.answer("❌ Ошибка при генерации. Попробуй снова.")

    # ── Вес тела ──────────────────────────────────────────────────────────────

    @dp.message(F.text == "⚖️ Внести вес тела")
    async def body_weight_input(msg: Message, state: FSMContext):
        await state.set_state(BodyWeightStates.waiting_weight)
        latest = await db.get_latest_body_weight(msg.from_user.id)
        hint = f"\nПоследний вес: *{latest} кг*" if latest else ""
        await msg.answer(f"Введи текущий вес (кг):{hint}\n_(например: 82.5)_",
                         parse_mode="Markdown")

    @dp.callback_query(F.data == "quick_weight_input")
    async def quick_weight_input(call: CallbackQuery, state: FSMContext):
        await state.set_state(BodyWeightStates.waiting_weight)
        latest = await db.get_latest_body_weight(call.from_user.id)
        hint = f"\nПоследний вес: *{latest} кг*" if latest else ""
        await call.message.answer(f"Введи текущий вес (кг):{hint}\n_(например: 82.5)_",
                                  parse_mode="Markdown")

    @dp.message(BodyWeightStates.waiting_weight)
    async def body_weight_save(msg: Message, state: FSMContext):
        try:
            weight = float(msg.text.strip().replace(",", "."))
            if not (30 <= weight <= 300): raise ValueError
        except ValueError:
            await msg.answer("Введи корректный вес (от 30 до 300)")
            return
        await state.clear()
        await db.save_body_weight(msg.from_user.id, weight)

        history = await db.get_body_weight_history(msg.from_user.id, limit=2)
        comment = ""
        if len(history) >= 2:
            diff = round(weight - history[1]["weight"], 1)
            if diff > 0:   comment = f"\n📈 +{diff} кг с прошлого раза"
            elif diff < 0: comment = f"\n📉 {diff} кг с прошлого раза"
            else:          comment = "\n➡️ Вес не изменился"

        await msg.answer(f"✅ Вес *{weight} кг* записан!{comment}",
                         parse_mode="Markdown", reply_markup=nutrition_menu_kb())

        profile = await db.get_nutrition_profile(msg.from_user.id)
        if profile:
            profile["weight"] = weight
            await db.save_nutrition_profile(msg.from_user.id, profile)
            weekly_menu_cache.pop(msg.from_user.id, None)

    # ── История веса ──────────────────────────────────────────────────────────

    @dp.message(F.text == "📈 История веса")
    async def body_weight_history(msg: Message):
        history = await db.get_body_weight_history(msg.from_user.id, limit=10)
        if not history:
            await msg.answer("Пока нет записей. Внеси вес через '⚖️ Внести вес тела'.")
            return
        lines = ["📈 *История веса:*\n"]
        for i, entry in enumerate(history):
            if i < len(history) - 1:
                diff = round(entry["weight"] - history[i + 1]["weight"], 1)
                arrow = f"📈 +{diff}" if diff > 0 else (f"📉 {diff}" if diff < 0 else "➡️ 0")
                lines.append(f"• {entry['date']}: *{entry['weight']} кг* {arrow}")
            else:
                lines.append(f"• {entry['date']}: *{entry['weight']} кг*")
        if len(history) >= 2:
            total = round(history[0]["weight"] - history[-1]["weight"], 1)
            sign = "+" if total > 0 else ""
            lines.append(f"\n_{history[-1]['date']} → {history[0]['date']}: {sign}{total} кг_")
        await msg.answer("\n".join(lines), parse_mode="Markdown")
