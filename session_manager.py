"""
Менеджер активной тренировки.
Ведёт пользователя через тренировку в реальном времени:
- Показывает текущее упражнение, подход, вес
- Запускает автоматический таймер отдыха с обратным отсчётом
- Присылает уведомления каждые 30 сек во время отдыха
- Пользователь подтверждает выполнение подхода кнопкой
"""

import asyncio
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

# user_id -> WorkoutSession
active_sessions: dict = {}


class WorkoutSession:
    def __init__(self, user_id: int, plan: dict, bot: Bot):
        self.user_id = user_id
        self.plan = plan
        self.bot = bot
        self.exercises = plan["exercises"]

        self.ex_index = 0       # текущее упражнение
        self.set_index = 0      # текущий подход
        self.resting = False
        self.rest_task: asyncio.Task | None = None
        self.cancelled = False

    @property
    def current_exercise(self) -> dict:
        return self.exercises[self.ex_index]

    @property
    def total_sets(self) -> int:
        return self.current_exercise["sets"]

    @property
    def is_finished(self) -> bool:
        return self.ex_index >= len(self.exercises)

    def set_label(self) -> str:
        return f"{self.set_index + 1}/{self.total_sets}"

    def cancel(self):
        self.cancelled = True
        if self.rest_task and not self.rest_task.done():
            self.rest_task.cancel()


def set_prompt_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подход выполнен!", callback_data="set_done"),
        InlineKeyboardButton(text="⏹ Завершить", callback_data="workout_stop"),
    ]])


def rest_kb(seconds_left: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"⚡ Пропустить отдых ({seconds_left}с)", callback_data="skip_rest"),
        InlineKeyboardButton(text="⏹ Завершить", callback_data="workout_stop"),
    ]])


async def send_set_prompt(session: WorkoutSession, message_id: int | None = None) -> int:
    """Отправляет или редактирует сообщение с заданием на подход."""
    ex = session.current_exercise
    total_ex = len(session.exercises)
    ex_num = session.ex_index + 1
    set_num = session.set_index + 1

    # Берём вес и повторения из пирамиды если есть
    pyramid = ex.get("pyramid", [])
    if pyramid and session.set_index < len(pyramid):
        p = pyramid[session.set_index]
        weight = p.get("weight")
        reps = p.get("reps", ex.get("reps", ""))
        weight_str = f"{weight} кг" if weight else "❓ вес не задан"
        if set_num == 1:
            set_label = "🔸 Разминочный подход"
        elif weight and ex.get("working_weight") and weight >= ex["working_weight"]:
            set_label = "🔴 Рабочий подход"
        else:
            set_label = "🔶 Подход"
    else:
        weight_str = f"{ex['working_weight']} кг" if ex.get("working_weight") else "❓ вес не задан"
        reps = ex.get("reps", "")
        set_label = "📍 Подход"

    text = (
        f"🏋️ *{ex['name']}*  _{ex_num}/{total_ex} упр._\n\n"
        f"{set_label}: *{session.set_label()}*\n"
        f"🔁 Повторений: *{reps}*\n"
        f"⚖️ Вес: *{weight_str}*\n\n"
        f"💡 _{ex.get('tip', '')}_\n\n"
        f"Выполни подход и нажми кнопку:"
    )

    msg = await session.bot.send_message(
        session.user_id, text,
        parse_mode="Markdown",
        reply_markup=set_prompt_kb()
    )
    return msg.message_id


async def run_rest_timer(session: WorkoutSession, rest_seconds: int):
    """Запускает таймер отдыха с уведомлениями каждые 30 сек."""
    try:
        session.resting = True
        remaining = rest_seconds

        # Первое сообщение — старт отдыха
        rest_msg = await session.bot.send_message(
            session.user_id,
            f"⏸ *Отдых: {remaining // 60}:{remaining % 60:02d}*\n"
            f"Следующий подход начнётся автоматически.",
            parse_mode="Markdown",
            reply_markup=rest_kb(remaining)
        )

        # Каждые 30 секунд — обновляем сообщение
        while remaining > 0 and not session.cancelled:
            await asyncio.sleep(min(30, remaining))
            remaining -= 30

            if session.cancelled:
                break

            if remaining <= 0:
                break

            try:
                await session.bot.edit_message_text(
                    chat_id=session.user_id,
                    message_id=rest_msg.message_id,
                    text=f"⏸ *Отдых: {remaining // 60}:{remaining % 60:02d}*\n"
                         f"Ещё немного...",
                    parse_mode="Markdown",
                    reply_markup=rest_kb(remaining)
                )
            except Exception:
                pass

        if not session.cancelled:
            # Отдых завершён — зовём на следующий подход
            try:
                await session.bot.edit_message_text(
                    chat_id=session.user_id,
                    message_id=rest_msg.message_id,
                    text="✅ *Отдых завершён!*",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            await advance_and_prompt(session)

    except asyncio.CancelledError:
        pass
    finally:
        session.resting = False


async def advance_and_prompt(session: WorkoutSession):
    """Переходит к следующему подходу или упражнению и показывает задание."""
    if session.cancelled:
        return

    session.set_index += 1

    # Все подходы текущего упражнения выполнены?
    if session.set_index >= session.total_sets:
        session.ex_index += 1
        session.set_index = 0

    # Тренировка завершена?
    if session.is_finished:
        await finish_workout(session)
        return

    # Сообщаем о смене упражнения
    if session.set_index == 0:
        ex = session.current_exercise
        await session.bot.send_message(
            session.user_id,
            f"🔄 *Следующее упражнение: {ex['name']}*",
            parse_mode="Markdown"
        )

    await send_set_prompt(session)


async def finish_workout(session: WorkoutSession):
    """Завершает тренировку."""
    active_sessions.pop(session.user_id, None)
    total_sets = sum(ex["sets"] for ex in session.exercises)
    await session.bot.send_message(
        session.user_id,
        f"🎉 *Тренировка завершена!*\n\n"
        f"✅ Упражнений: {len(session.exercises)}\n"
        f"✅ Подходов всего: {total_sets}\n\n"
        f"Не забудь обновить рабочие веса: /weights",
        parse_mode="Markdown"
    )


async def start_workout_session(user_id: int, plan: dict, bot: Bot):
    """Запускает активную тренировку."""
    # Отменяем предыдущую если есть
    if user_id in active_sessions:
        active_sessions[user_id].cancel()

    session = WorkoutSession(user_id, plan, bot)
    active_sessions[user_id] = session

    ex = session.current_exercise
    await bot.send_message(
        user_id,
        f"🚀 *Тренировка началась!*\n\n"
        f"Упражнений: {len(session.exercises)}\n"
        f"Расчётное время: ~{plan['total_time_estimate']} мин\n\n"
        f"Первое упражнение: *{ex['name']}*",
        parse_mode="Markdown"
    )

    await send_set_prompt(session)


async def handle_set_done(user_id: int) -> bool:
    """Вызывается когда пользователь нажал 'Подход выполнен'."""
    session = active_sessions.get(user_id)
    if not session or session.resting:
        return False

    ex = session.current_exercise
    rest_sec = ex["rest_seconds"]

    # Последний подход последнего упражнения — не отдыхаем
    is_last_set = session.set_index + 1 >= session.total_sets
    is_last_ex = session.ex_index + 1 >= len(session.exercises)

    if is_last_set and is_last_ex:
        await advance_and_prompt(session)
    else:
        # Запускаем таймер отдыха
        session.rest_task = asyncio.create_task(
            run_rest_timer(session, rest_sec)
        )

    return True


async def handle_skip_rest(user_id: int) -> bool:
    """Пользователь пропустил отдых."""
    session = active_sessions.get(user_id)
    if not session or not session.resting:
        return False

    session.rest_task.cancel()
    session.resting = False
    await advance_and_prompt(session)
    return True


async def handle_stop_workout(user_id: int) -> bool:
    """Пользователь остановил тренировку."""
    session = active_sessions.pop(user_id, None)
    if not session:
        return False
    session.cancel()
    return True
