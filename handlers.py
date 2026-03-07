"""
Все обработчики команд и сообщений бота
"""

import json
import logging
from aiogram import Dispatcher, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database import Database
from states import AddExerciseStates, WorkoutStates, WeightStates, DeleteExerciseStates, MoodStates
from keyboards import (
    main_menu_kb, muscle_groups_kb, exercise_type_kb,
    skip_kb, exercises_list_kb, weights_exercises_kb
)
from workout_generator import generate_workout_plan, format_plan_message
from ai_features import analyze_progress, adapt_plan_to_mood, generate_weekly_report
from session_manager import (
    active_sessions, start_workout_session,
    handle_set_done, handle_skip_rest, handle_stop_workout
)

logger = logging.getLogger(__name__)


def plan_confirmation_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Начать тренировку!", callback_data="confirm_plan"),
            InlineKeyboardButton(text="🔄 Перегенерировать", callback_data="regen_plan"),
        ]
    ])




def register_handlers(dp: Dispatcher, db: Database):

    # ── /start ────────────────────────────────────────────────────────────────

    @dp.message(CommandStart())
    async def cmd_start(msg: Message, state: FSMContext):
        await state.clear()
        await msg.answer(
            "👋 Привет! Я твой тренировочный бот.\n\n"
            "Что умею:\n"
            "🏋️ Составлять план тренировки под твоё время\n"
            "⏱ Вести твою тренировку в реальном времени\n"
            "📋 Работать только с твоими упражнениями\n"
            "⚖️ Хранить рабочие веса\n"
            "📊 Считать тренировки в неделю\n\n"
            "Начни с добавления упражнений → *Мои упражнения*",
            reply_markup=main_menu_kb(),
            parse_mode="Markdown"
        )

    # ── Добавить упражнение ───────────────────────────────────────────────────

    @dp.message(F.text == "➕ Добавить упражнение")
    async def add_exercise_start(msg: Message, state: FSMContext):
        await state.set_state(AddExerciseStates.waiting_name)
        await msg.answer(
            "Введи название упражнения:\n_(например: Жим штанги лёжа)_",
            parse_mode="Markdown"
        )

    @dp.message(AddExerciseStates.waiting_name)
    async def add_exercise_name(msg: Message, state: FSMContext):
        await state.update_data(name=msg.text.strip())
        await state.set_state(AddExerciseStates.waiting_muscle_group)
        await msg.answer(
            "Введи группу мышц:\n_(например: Грудь, Спина, Ноги, Бицепс, Трицепс, Плечи)_",
            parse_mode="Markdown"
        )

    @dp.message(AddExerciseStates.waiting_muscle_group)
    async def add_exercise_group(msg: Message, state: FSMContext):
        await state.update_data(muscle_group=msg.text.strip())
        await state.set_state(AddExerciseStates.waiting_type)
        await msg.answer("Тип упражнения:", reply_markup=exercise_type_kb())

    @dp.callback_query(AddExerciseStates.waiting_type, F.data.startswith("type:"))
    async def add_exercise_type(call: CallbackQuery, state: FSMContext):
        is_compound = call.data == "type:compound"
        await state.update_data(is_compound=is_compound)
        await state.set_state(AddExerciseStates.waiting_notes)
        await call.message.edit_text(
            "Добавь заметку к упражнению (необязательно):\n_(например: делаю с паузой внизу)_",
            reply_markup=skip_kb(),
            parse_mode="Markdown"
        )

    @dp.callback_query(AddExerciseStates.waiting_notes, F.data == "skip")
    async def add_exercise_notes_skip(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        await state.clear()
        ok = await db.add_exercise(
            user_id=call.from_user.id,
            name=data["name"],
            muscle_group=data["muscle_group"],
            is_compound=data["is_compound"],
            notes=""
        )
        status = "✅ Добавлено" if ok else "⚠️ Уже существует"
        await call.message.edit_text(f"{status}: *{data['name']}*", parse_mode="Markdown")

    @dp.message(AddExerciseStates.waiting_notes)
    async def add_exercise_notes(msg: Message, state: FSMContext):
        data = await state.get_data()
        await state.clear()
        ok = await db.add_exercise(
            user_id=msg.from_user.id,
            name=data["name"],
            muscle_group=data["muscle_group"],
            is_compound=data["is_compound"],
            notes=msg.text.strip()
        )
        status = "✅ Добавлено" if ok else "⚠️ Уже существует"
        await msg.answer(f"{status}: *{data['name']}*",
                         reply_markup=main_menu_kb(), parse_mode="Markdown")

    # ── Список упражнений ─────────────────────────────────────────────────────

    @dp.message(F.text == "📋 Мои упражнения")
    async def list_exercises(msg: Message):
        exercises = await db.get_exercises(msg.from_user.id)
        if not exercises:
            await msg.answer(
                "У тебя пока нет упражнений.\nДобавь через *➕ Добавить упражнение*",
                parse_mode="Markdown"
            )
            return

        groups = {}
        for ex in exercises:
            groups.setdefault(ex["muscle_group"], []).append(ex)

        lines = ["📋 *Твои упражнения:*\n"]
        for group, exs in groups.items():
            lines.append(f"*{group}:*")
            for ex in exs:
                t = "🏋️" if ex["is_compound"] else "💪"
                notes = f" _{ex['notes']}_" if ex.get("notes") else ""
                lines.append(f"  {t} {ex['name']}{notes}")
            lines.append("")
        lines.append("Чтобы удалить упражнение — /delete")

        await msg.answer("\n".join(lines), parse_mode="Markdown")

    # ── Удалить упражнение ────────────────────────────────────────────────────

    @dp.message(Command("delete"))
    async def delete_exercise_start(msg: Message, state: FSMContext):
        exercises = await db.get_exercises(msg.from_user.id)
        if not exercises:
            await msg.answer("Нет упражнений для удаления.")
            return
        await state.set_state(DeleteExerciseStates.waiting_name)
        await msg.answer("Выбери упражнение для удаления:",
                         reply_markup=exercises_list_kb(exercises, prefix="del"))

    @dp.callback_query(DeleteExerciseStates.waiting_name, F.data.startswith("del:"))
    async def delete_exercise_confirm(call: CallbackQuery, state: FSMContext):
        idx = int(call.data[4:])
        exercises = await db.get_exercises(call.from_user.id)
        if idx >= len(exercises):
            await call.answer("Упражнение не найдено.", show_alert=True)
            return
        name = exercises[idx]["name"]
        await state.clear()
        await db.delete_exercise(call.from_user.id, name)
        await call.message.edit_text(f"🗑️ *{name}* удалено.", parse_mode="Markdown")

    # ── Начать тренировку ─────────────────────────────────────────────────────

    def mood_kb() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="😫 1", callback_data="mood:1"),
                InlineKeyboardButton(text="😔 2", callback_data="mood:2"),
                InlineKeyboardButton(text="😐 3", callback_data="mood:3"),
                InlineKeyboardButton(text="😊 4", callback_data="mood:4"),
                InlineKeyboardButton(text="💪 5", callback_data="mood:5"),
            ]
        ])

    def skip_mood_kb() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="mood:skip")]
        ])

    @dp.message(F.text == "🏋️ Начать тренировку")
    async def workout_start(msg: Message, state: FSMContext):
        if msg.from_user.id in active_sessions:
            await msg.answer(
                "⚠️ У тебя уже идёт тренировка!\n"
                "Заверши её или нажми /stop чтобы остановить."
            )
            return

        groups = await db.get_muscle_groups(msg.from_user.id)
        if not groups:
            await msg.answer(
                "Сначала добавь упражнения через *➕ Добавить упражнение*",
                parse_mode="Markdown"
            )
            return

        # Сначала спрашиваем самочувствие
        await state.set_state(MoodStates.waiting_score)
        await state.update_data(groups=groups)
        await msg.answer(
            "Как твоё самочувствие сегодня? 😊\n\n"
            "_ИИ адаптирует тренировку под твоё состояние_",
            parse_mode="Markdown",
            reply_markup=mood_kb()
        )

    @dp.callback_query(MoodStates.waiting_score, F.data.startswith("mood:"))
    async def mood_score_handler(call: CallbackQuery, state: FSMContext):
        value = call.data[5:]
        if value == "skip":
            mood_score = None
            await state.update_data(mood_score=None, mood_notes="")
        else:
            mood_score = int(value)
            await state.update_data(mood_score=mood_score)

        if mood_score and mood_score <= 3:
            await state.set_state(MoodStates.waiting_notes)
            await call.message.edit_text(
                f"Самочувствие {mood_score}/5. Что беспокоит?\n"
                "_(например: болит спина, мало спал)_\n\n"
                "Или нажми пропустить:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Пропустить", callback_data="mood_notes:skip")]
                ])
            )
        else:
            await call.message.edit_text(
                f"{'Отличное самочувствие 💪' if mood_score == 5 else 'Хорошее самочувствие 😊' if mood_score else 'Окей, без оценки!'}"
            )
            await _proceed_to_muscle_group(call.from_user.id, call.bot, call.message, state)

    @dp.message(MoodStates.waiting_notes)
    async def mood_notes_handler(msg: Message, state: FSMContext):
        await state.update_data(mood_notes=msg.text.strip())
        await _proceed_to_muscle_group(msg.from_user.id, msg.bot, msg, state)

    @dp.callback_query(MoodStates.waiting_notes, F.data == "mood_notes:skip")
    async def mood_notes_skip(call: CallbackQuery, state: FSMContext):
        await state.update_data(mood_notes="")
        await call.message.edit_text("Понял, едем дальше!")
        await _proceed_to_muscle_group(call.from_user.id, call.bot, call.message, state)

    async def _proceed_to_muscle_group(user_id: int, bot: Bot, msg_or_call, state: FSMContext):
        data = await state.get_data()
        groups = data.get("groups", await db.get_muscle_groups(user_id))
        await state.set_state(WorkoutStates.waiting_muscle_group)
        await bot.send_message(
            user_id,
            "Какую группу мышц сегодня тренируешь?",
            reply_markup=muscle_groups_kb(groups)
        )

    @dp.callback_query(WorkoutStates.waiting_muscle_group, F.data.startswith("mg:"))
    async def workout_muscle_group(call: CallbackQuery, state: FSMContext):
        group = call.data[3:]
        data = await state.get_data()
        selected = data.get("selected_groups", [])

        # Тоггл: если уже выбрана — снимаем, если нет — добавляем
        if group in selected:
            selected.remove(group)
        else:
            selected.append(group)

        await state.update_data(selected_groups=selected)
        groups = await db.get_muscle_groups(call.from_user.id)
        await call.message.edit_reply_markup(
            reply_markup=muscle_groups_kb(groups, selected)
        )
        await call.answer()

    @dp.callback_query(WorkoutStates.waiting_muscle_group, F.data == "mg_confirm")
    async def workout_muscle_group_confirm(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        selected = data.get("selected_groups", [])
        if not selected:
            await call.answer("Выбери хотя бы одну группу!", show_alert=True)
            return

        muscle_group = " + ".join(selected)
        await state.update_data(muscle_group=muscle_group, selected_groups=[])
        await state.set_state(WorkoutStates.waiting_time)
        await call.message.edit_text(
            f"Выбрано: *{muscle_group}*\n\nСколько минут есть на тренировку?\n"
            "_(введи число, например: 80)_",
            parse_mode="Markdown"
        )

    @dp.message(WorkoutStates.waiting_time)
    async def workout_generate(msg: Message, state: FSMContext):
        try:
            minutes = int(msg.text.strip())
            if not (20 <= minutes <= 240):
                raise ValueError
        except ValueError:
            await msg.answer("Введи число минут от 20 до 240")
            return

        data = await state.get_data()
        await state.clear()
        muscle_group = data["muscle_group"]

        await msg.answer("⏳ Составляю план тренировки...")
        await _generate_and_show_plan(
            msg.from_user.id, msg.bot, db, muscle_group, minutes, state
        )

    async def _generate_and_show_plan(user_id: int, bot: Bot, db: Database,
                                       muscle_group: str, minutes: int, state: FSMContext):
        # Поддержка нескольких групп через " + "
        groups = [g.strip() for g in muscle_group.split("+")]
        exercises = []
        for g in groups:
            exercises += await db.get_exercises(user_id, g)
        # Убираем дубликаты если вдруг есть
        seen = set()
        exercises = [e for e in exercises if not (e["name"] in seen or seen.add(e["name"]))]

        if not exercises:
            await bot.send_message(user_id,
                f"У тебя нет упражнений для группы *{muscle_group}*",
                parse_mode="Markdown")
            return

        weights = await db.get_weights(user_id)
        weekly = await db.get_weekly_count(user_id)

        try:
            plan = generate_workout_plan(muscle_group, minutes, exercises, weights)
        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            await bot.send_message(user_id, "❌ Ошибка при генерации плана. Попробуй снова.")
            return

        # Временно сохраняем план в FSM state
        await state.update_data(
            pending_plan=plan,
            pending_muscle_group=muscle_group,
            pending_minutes=minutes
        )

        text = format_plan_message(plan, muscle_group, minutes, weekly)
        # Убираем последнюю строку — вместо неё кнопки
        text = text.rsplit("\n", 2)[0]

        await bot.send_message(
            user_id,
            text + "\n\n*Как тебе план?*",
            parse_mode="Markdown",
            reply_markup=plan_confirmation_kb()
        )

    # ── Подтверждение / перегенерация плана ──────────────────────────────────

    @dp.callback_query(F.data == "confirm_plan")
    async def confirm_plan(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        plan = data.get("pending_plan")
        if not plan:
            await call.answer("План устарел, начни заново.", show_alert=True)
            return

        muscle_group = data["pending_muscle_group"]
        minutes = data["pending_minutes"]
        mood_score = data.get("mood_score")
        mood_notes = data.get("mood_notes", "")

        # Адаптируем план под самочувствие если нужно
        if mood_score and mood_score <= 3:
            await call.message.answer("🤖 Адаптирую план под твоё самочувствие...")
            try:
                plan, mood_comment = adapt_plan_to_mood(plan, mood_score, mood_notes, muscle_group)
                await call.message.answer(f"💬 {mood_comment}")
            except Exception:
                pass

        weekly = await db.get_weekly_count(call.from_user.id)
        await db.save_session(call.from_user.id, muscle_group, minutes, plan, mood_score, mood_notes)

        await call.message.edit_reply_markup(reply_markup=None)
        await call.message.answer(
            f"🔥 Начинаем! Тренировок на этой неделе: *{weekly + 1}*",
            parse_mode="Markdown"
        )
        await state.clear()
        await start_workout_session(call.from_user.id, plan, call.bot)

    @dp.callback_query(F.data == "regen_plan")
    async def regen_plan(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        muscle_group = data.get("pending_muscle_group")
        minutes = data.get("pending_minutes")
        if not muscle_group or not minutes:
            await call.answer("Данные устарели, начни заново.", show_alert=True)
            return

        await call.message.edit_reply_markup(reply_markup=None)
        await call.message.answer("🔄 Генерирую новый вариант...")
        await _generate_and_show_plan(
            call.from_user.id, call.bot, db, muscle_group, minutes, state
        )

    # ── Live тренировка: кнопки ───────────────────────────────────────────────

    @dp.callback_query(F.data == "set_done")
    async def on_set_done(call: CallbackQuery):
        ok = await handle_set_done(call.from_user.id)
        if ok:
            await call.message.edit_reply_markup(reply_markup=None)
            await call.answer("💪 Записано!")
        else:
            await call.answer("Сейчас идёт отдых, подожди.", show_alert=True)

    @dp.callback_query(F.data == "skip_rest")
    async def on_skip_rest(call: CallbackQuery):
        ok = await handle_skip_rest(call.from_user.id)
        if ok:
            await call.message.edit_reply_markup(reply_markup=None)
            await call.answer("⚡ Пропускаем отдых!")
        else:
            await call.answer("Нет активного таймера.", show_alert=True)

    @dp.callback_query(F.data == "workout_stop")
    async def on_workout_stop(call: CallbackQuery, state: FSMContext):
        ok = await handle_stop_workout(call.from_user.id)
        await state.clear()
        if ok:
            await call.message.edit_reply_markup(reply_markup=None)
            await call.message.answer(
                "⏹ Тренировка остановлена.\nНе забудь обновить веса: /weights",
                reply_markup=main_menu_kb()
            )
        else:
            await call.answer("Нет активной тренировки.", show_alert=True)

    @dp.message(Command("stop"))
    async def cmd_stop(msg: Message, state: FSMContext):
        ok = await handle_stop_workout(msg.from_user.id)
        await state.clear()
        if ok:
            await msg.answer("⏹ Тренировка остановлена.", reply_markup=main_menu_kb())
        else:
            await msg.answer("Нет активной тренировки.")

    # ── Рабочие веса ─────────────────────────────────────────────────────────

    @dp.message(F.text == "⚖️ Рабочие веса")
    async def weights_menu(msg: Message, state: FSMContext):
        exercises = await db.get_exercises(msg.from_user.id)
        if not exercises:
            await msg.answer("Сначала добавь упражнения.")
            return
        weights = await db.get_weights(msg.from_user.id)

        lines = ["⚖️ *Рабочие веса:*\n"]
        for ex in exercises:
            w = weights.get(ex["name"])
            if w:
                lines.append(f"• {ex['name']}: *{w['weight']} кг*")
            else:
                lines.append(f"• {ex['name']}: _не задан_")
        lines.append("\nНажми на упражнение чтобы обновить вес:")

        await msg.answer(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=weights_exercises_kb(exercises)
        )

    @dp.callback_query(F.data.startswith("wex:"))
    async def weights_select_exercise(call: CallbackQuery, state: FSMContext):
        idx = int(call.data[4:])
        exercises = await db.get_exercises(call.from_user.id)
        if idx >= len(exercises):
            await call.answer("Упражнение не найдено.", show_alert=True)
            return
        name = exercises[idx]["name"]
        await state.set_state(WeightStates.waiting_weight)
        await state.update_data(exercise_name=name)
        await call.message.answer(
            f"Введи рабочий вес для *{name}* (кг):\n_(например: 80 или 82.5)_",
            parse_mode="Markdown"
        )

    @dp.message(WeightStates.waiting_weight)
    async def weights_set(msg: Message, state: FSMContext):
        try:
            weight = float(msg.text.strip().replace(",", "."))
        except ValueError:
            await msg.answer("Введи число (например: 80 или 82.5)")
            return
        data = await state.get_data()
        await state.clear()
        await db.set_weight(msg.from_user.id, data["exercise_name"], weight)
        await msg.answer(
            f"✅ *{data['exercise_name']}*: {weight} кг — сохранён!",
            parse_mode="Markdown",
            reply_markup=main_menu_kb()
        )

    @dp.message(Command("weights"))
    async def weights_cmd(msg: Message, state: FSMContext):
        await weights_menu(msg, state)

    # ── Аналитика прогресса ──────────────────────────────────────────────────

    @dp.message(F.text == "📈 Прогресс")
    async def progress_analysis(msg: Message):
        await msg.answer("🤖 Анализирую твой прогресс...")
        sessions = await db.get_sessions(msg.from_user.id, limit=10)
        weights_history = await db.get_weights_history(msg.from_user.id)
        try:
            analysis = analyze_progress(sessions, weights_history)
            await msg.answer(analysis)
        except Exception as e:
            await msg.answer("❌ Ошибка при анализе. Попробуй позже.")

    # ── Еженедельный отчёт ────────────────────────────────────────────────────

    @dp.message(F.text == "📋 Еженедельный отчёт")
    async def weekly_report(msg: Message):
        await msg.answer("🤖 Составляю отчёт за неделю...")
        sessions = await db.get_weekly_sessions(msg.from_user.id)
        weights = await db.get_weights(msg.from_user.id)
        user_name = msg.from_user.first_name or ""
        try:
            report = generate_weekly_report(sessions, weights, user_name)
            await msg.answer(report, parse_mode="Markdown")
        except Exception:
            await msg.answer("❌ Ошибка при генерации отчёта. Попробуй позже.")
    
    # ── Донат ──────────────────────────────────────────────────────────────────

    @dp.message(Command("donate"))
    async def donate_cmd(msg: Message):
        await msg.answer(
            "❤️ *Поддержать бота*\n\n"
            "Этот бот создан с любовью и работает благодаря поддержке таких людей как ты.\n\n"
            "Если бот помогает тебе тренироваться эффективнее — буду рад любой поддержке! "
            "Это помогает оплачивать хостинг и развивать проект дальше 🚀\n\n"
            "👇 Поддержать можно здесь:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="💰 Поддержать на Boosty",
                    url="https://boosty.to/training_bot"
                )],
            ])
        )

    # ── Статистика ────────────────────────────────────────────────────────────

    @dp.message(F.text == "📊 Статистика")
    async def stats(msg: Message):
        weekly = await db.get_weekly_count(msg.from_user.id)
        sessions = await db.get_sessions(msg.from_user.id, limit=5)

        lines = ["📊 *Твоя статистика*\n",
                 f"Тренировок за последние 7 дней: *{weekly}*\n",
                 "📅 *Последние тренировки:*"]

        if not sessions:
            lines.append("_Пока нет записей_")
        else:
            for s in sessions:
                plan = json.loads(s["plan_json"]) if s.get("plan_json") else {}
                ex_count = len(plan.get("exercises", []))
                lines.append(f"• {s['date']} — {s['muscle_group']} "
                             f"({s['duration_minutes']} мин, {ex_count} упр.)")

        await msg.answer("\n".join(lines), parse_mode="Markdown")
    # ── Админ ─────────────────────────────────────────────────────────────────

    ADMIN_ID = 1101461656

    @dp.message(Command("broadcast"))
    async def broadcast(msg: Message):
        if msg.from_user.id != ADMIN_ID:
            return
        text = msg.text.replace("/broadcast", "").strip()
        if not text:
            await msg.answer("Использование: /broadcast текст сообщения")
            return
        user_ids = await db.get_all_user_ids()
        sent = 0
        failed = 0
        for user_id in user_ids:
            try:
                await msg.bot.send_message(user_id, text, parse_mode="Markdown")
                sent += 1
            except Exception:
                failed += 1
        await msg.answer(f"✅ Отправлено: {sent}\n❌ Не доставлено: {failed}")

    @dp.message(Command("stats"))
    async def admin_stats(msg: Message):
        if msg.from_user.id != ADMIN_ID:
            return
        user_ids = await db.get_all_user_ids()
        async with __import__('aiosqlite').connect(db.db_path) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM workout_sessions")
            row = await cursor.fetchone()
            total_sessions = row[0]
        await msg.answer(
            f"📊 *Статистика бота*\n\n"
            f"👥 Пользователей: *{len(user_ids)}*\n"
            f"🏋️ Всего тренировок: *{total_sessions}*",
            parse_mode="Markdown"
        )
