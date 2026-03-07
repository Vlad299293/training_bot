"""
Генерация тренировочного плана через Groq API (бесплатно)
"""

import json
from groq import Groq
from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)


def generate_workout_plan(
    muscle_group: str,
    available_minutes: int,
    exercises: list,
    working_weights: dict
) -> dict:
    """
    Генерирует структурированный план тренировки с пирамидой весов.
    Возвращает словарь с планом.
    """

    ex_list = []
    for ex in exercises:
        w_info = working_weights.get(ex["name"])
        weight_str = f", рабочий вес: {w_info['weight']} кг" if w_info else ", вес не указан"
        compound_str = "базовое (многосуставное)" if ex["is_compound"] else "изолирующее"
        ex_list.append(
            f"- {ex['name']} [{compound_str}]{weight_str}"
            + (f" — {ex['notes']}" if ex.get("notes") else "")
        )

    exercises_text = "\n".join(ex_list)

    prompt = f"""Ты опытный тренер по силовым тренировкам. Составь тренировочный план.

ПАРАМЕТРЫ ТРЕНИРОВКИ:
- Группа мышц: {muscle_group}
- Доступное время: {available_minutes} минут
- Цель: гипертрофия (набор мышечной массы)
- Отдых между подходами: минимум 2.5 минуты (для базовых — 3-3.5 мин, для изолирующих — 2-2.5 мин)

ДОСТУПНЫЕ УПРАЖНЕНИЯ (только из этого списка):
{exercises_text}

ПРАВИЛА СОСТАВЛЕНИЯ ПЛАНА:
1. Начинай с базовых (многосуставных) упражнений, заканчивай изолирующими
2. Количество подходов:
   - Базовые упражнения: 3-4 рабочих подхода (не всегда 4, варьируй в зависимости от сложности и времени)
   - Изолирующие упражнения: 3 подхода
3. ПИРАМИДА ВЕСОВ — для каждого упражнения указывай веса по подходам:
   - Подход 1 (разминочный): 50-60% от рабочего веса, повторений больше (12-15)
   - Подход 2: 70-80% от рабочего веса, повторений меньше (8-10)
   - Подход 3+: 100% рабочий вес, целевые повторения (6-8 для базовых, 10-12 для изолирующих)
   - Если рабочий вес не указан — напиши null для всех подходов
4. Учти реальное время: подход ~1-2 мин + отдых. Не перегружай план
5. Выбирай упражнения разумно — не бери все подряд, выбери лучшие под время
6. НЕ придумывай упражнений, которых нет в списке выше

Ответь СТРОГО в формате JSON (без markdown, без комментариев):
{{
  "total_time_estimate": <целое число минут>,
  "exercises": [
    {{
      "name": "<точное название из списка>",
      "type": "базовое" или "изолирующее",
      "sets": <число подходов>,
      "reps": "<целевые повторения для рабочих подходов, например: 6-8>",
      "rest_seconds": <число секунд>,
      "working_weight": <рабочий вес в кг или null>,
      "pyramid": [
        {{"set": 1, "weight": <вес или null>, "reps": "<повторения>"}},
        {{"set": 2, "weight": <вес или null>, "reps": "<повторения>"}},
        {{"set": 3, "weight": <вес или null>, "reps": "<повторения>"}}
      ],
      "tip": "<короткий совет по технике, 1 предложение>"
    }}
  ],
  "structure_note": "<1-2 предложения почему такой порядок>"
}}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.7
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    plan = json.loads(text)
    return plan


def format_plan_message(plan: dict, muscle_group: str, available_minutes: int,
                        weekly_count: int) -> str:
    """Форматирует план в красивое сообщение для Telegram."""

    lines = []
    lines.append(f"💪 *Тренировка: {muscle_group}*")
    lines.append(f"🕐 Доступно: {available_minutes} мин | Расчётное время: ~{plan['total_time_estimate']} мин")
    lines.append(f"📅 Тренировок на этой неделе: {weekly_count}")
    lines.append("")
    lines.append(f"_{plan.get('structure_note', '')}_")
    lines.append("")
    lines.append("─" * 30)

    for i, ex in enumerate(plan["exercises"], 1):
        rest_min = ex["rest_seconds"] // 60
        rest_sec = ex["rest_seconds"] % 60
        rest_str = f"{rest_min}:{rest_sec:02d}"

        lines.append(f"\n*{i}. {ex['name']}*")
        lines.append(f"   ⏸️ Отдых: {rest_str}")
        lines.append(f"   💡 _{ex.get('tip', '')}_")

        # Показываем пирамиду подходов
        pyramid = ex.get("pyramid", [])
        if pyramid:
            lines.append("   📊 *Подходы:*")
            for s in pyramid:
                set_num = s["set"]
                weight = s.get("weight")
                reps = s.get("reps", "")
                weight_str = f"{weight} кг" if weight else "❓"

                # Первый подход — разминочный
                if set_num == 1:
                    label = "🔸 разминка"
                elif weight and ex.get("working_weight") and weight >= ex["working_weight"]:
                    label = "🔴 рабочий"
                else:
                    label = "🔶"

                lines.append(f"   {set_num}. {weight_str} × {reps} {label}")
        else:
            # Fallback если пирамиды нет
            weight_str = f"{ex['working_weight']} кг" if ex.get("working_weight") else "❓ вес не задан"
            lines.append(f"   🏋️ {ex['sets']} подхода × {ex['reps']} повт. | {weight_str}")

    lines.append("\n" + "─" * 30)
    lines.append("✅ Удачной тренировки\\! После введи веса командой /weights")

    return "\n".join(lines)
