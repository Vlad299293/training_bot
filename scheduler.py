"""
Планировщик напоминаний:
- Каждое воскресенье в 10:00 — напоминание внести вес тела
- Каждое воскресенье в 20:00 — автоматический еженедельный отчёт
"""

import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)


def _seconds_until(weekday: int, hour: int, minute: int = 0) -> float:
    """Секунды до следующего наступления дня недели и времени. 0=пн, 6=вс"""
    now = datetime.now()
    days_ahead = weekday - now.weekday()
    if days_ahead < 0:
        days_ahead += 7
    elif days_ahead == 0 and now.hour >= hour:
        days_ahead = 7
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    target += timedelta(days=days_ahead)
    return (target - now).total_seconds()


async def weight_reminder_loop(bot: Bot, db):
    """Каждое воскресенье в 10:00 — напоминание внести вес."""
    while True:
        wait = _seconds_until(weekday=6, hour=10)
        logger.info(f"Напоминание о весе через {wait/3600:.1f} ч")
        await asyncio.sleep(wait)
        try:
            user_ids = await db.get_all_user_ids()
            for user_id in user_ids:
                try:
                    await bot.send_message(
                        user_id,
                        "⚖️ *Воскресное взвешивание!*\n\n"
                        "Время зафиксировать свой вес — это помогает отслеживать "
                        "прогресс и корректировать питание и тренировки.\n\n"
                        "Нажми чтобы внести:",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="⚖️ Внести вес", callback_data="quick_weight_input")
                        ]])
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Ошибка рассылки напоминания о весе: {e}")


async def weekly_report_loop(bot: Bot, db):
    """Каждое воскресенье в 20:00 — еженедельный отчёт."""
    from ai_features import generate_weekly_report
    while True:
        wait = _seconds_until(weekday=6, hour=20)
        logger.info(f"Отчёт через {wait/3600:.1f} ч")
        await asyncio.sleep(wait)
        try:
            user_ids = await db.get_all_user_ids()
            for user_id in user_ids:
                try:
                    sessions = await db.get_weekly_sessions(user_id)
                    if not sessions:
                        await bot.send_message(
                            user_id,
                            "📋 *Итоги недели*\n\nНа этой неделе тренировок не было.\n"
                            "Новая неделя — новые возможности! 💪",
                            parse_mode="Markdown"
                        )
                        continue
                    weights = await db.get_weights(user_id)
                    report = generate_weekly_report(sessions, weights)
                    await bot.send_message(
                        user_id,
                        f"📋 *Отчёт за неделю*\n\n{report}",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Ошибка рассылки отчётов: {e}")


async def start_schedulers(bot: Bot, db):
    asyncio.create_task(weight_reminder_loop(bot, db))
    asyncio.create_task(weekly_report_loop(bot, db))
    logger.info("Планировщики запущены")
