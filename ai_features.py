"""
ИИ-функции бота:
- Аналитика прогресса и советы
- Самочувствие перед тренировкой (адаптация плана)
- Еженедельный отчёт
"""

import json
from groq import Groq
from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)


def _ask_ai(prompt: str, max_tokens: int = 1000) -> str:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


# ── Аналитика прогресса ───────────────────────────────────────────────────────

def analyze_progress(sessions: list, weights_history: list) -> str:
    """
    Анализирует историю тренировок и весов, даёт персональные советы.
    """
    if not sessions:
        return "📊 Пока нет данных для анализа. Проведи несколько тренировок!"

    # Формируем данные для ИИ
    sessions_text = []
    for s in sessions[-10:]:  # Последние 10 тренировок
        plan = json.loads(s["plan_json"]) if s.get("plan_json") else {}
        exercises = plan.get("exercises", [])
        ex_names = [e["name"] for e in exercises]
        sessions_text.append(
            f"- {s['date']}: {s['muscle_group']} ({s['duration_minutes']} мин, "
            f"упражнения: {', '.join(ex_names)})"
        )

    weights_text = []
    for w in weights_history:
        weights_text.append(
            f"- {w['exercise_name']}: {w['weight']} кг (обновлено {w['updated_at']})"
        )

    prompt = f"""Ты персональный тренер. Проанализируй тренировочную историю спортсмена и дай конкретные советы.

ИСТОРИЯ ТРЕНИРОВОК (последние):
{chr(10).join(sessions_text) if sessions_text else 'Нет данных'}

ТЕКУЩИЕ РАБОЧИЕ ВЕСА:
{chr(10).join(weights_text) if weights_text else 'Нет данных'}

Дай анализ на русском языке. Будь конкретным и практичным. Структура ответа:
1. 💪 Что идёт хорошо (1-2 пункта)
2. ⚠️ Что стоит улучшить (1-2 пункта)  
3. 🎯 Конкретные рекомендации на следующую неделю (2-3 пункта)

Отвечай коротко и по делу, без лишней воды. Максимум 200 слов."""

    return _ask_ai(prompt, max_tokens=600)


# ── Самочувствие перед тренировкой ────────────────────────────────────────────

def adapt_plan_to_mood(plan: dict, mood_score: int, notes: str, muscle_group: str) -> dict:
    """
    Адаптирует план тренировки под самочувствие.
    mood_score: 1-5 (1 = очень плохо, 5 = отлично)
    Возвращает обновлённый план и комментарий ИИ.
    """
    if mood_score >= 4:
        # Хорошее самочувствие — план без изменений или чуть тяжелее
        comment = "🔥 Отличное самочувствие! Работаем по плану на максимум."
        return plan, comment

    exercises_text = json.dumps(plan.get("exercises", []), ensure_ascii=False, indent=2)

    mood_labels = {1: "очень плохое", 2: "плохое", 3: "среднее"}
    mood_label = mood_labels.get(mood_score, "среднее")

    prompt = f"""Ты опытный тренер. Спортсмен пришёл на тренировку ({muscle_group}) с самочувствием: {mood_label} ({mood_score}/5).
Его комментарий: "{notes if notes else 'без комментариев'}"

Текущий план тренировки:
{exercises_text}

Адаптируй план под самочувствие. Правила:
- При самочувствии 3/5: снизь рабочие веса на 10-15%, можно убрать 1 подход у базовых
- При самочувствии 2/5: снизь веса на 20-25%, замени тяжёлые базовые на более лёгкие варианты если возможно
- При самочувствии 1/5: лёгкая тренировка, веса -30%, только 2-3 подхода

Ответь СТРОГО в формате JSON:
{{
  "comment": "<совет тренера на русском, 1-2 предложения>",
  "exercises": <адаптированный массив упражнений в том же формате>
}}"""

    try:
        text = _ask_ai(prompt, max_tokens=1500)
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        result = json.loads(text)
        comment = result.get("comment", "")
        adapted_exercises = result.get("exercises", plan.get("exercises", []))
        adapted_plan = {**plan, "exercises": adapted_exercises}
        return adapted_plan, comment
    except Exception:
        comment = f"⚠️ Самочувствие {mood_score}/5. Слушай своё тело, снизь нагрузку если нужно."
        return plan, comment


# ── Еженедельный отчёт ────────────────────────────────────────────────────────

def generate_weekly_report(sessions: list, current_weights: dict, user_name: str = "") -> str:
    """
    Генерирует персональный еженедельный отчёт.
    """
    if not sessions:
        return "📋 На этой неделе тренировок не было. Время начать! 💪"

    # Собираем статистику недели
    total_workouts = len(sessions)
    muscle_groups = [s["muscle_group"] for s in sessions]
    total_minutes = sum(s.get("duration_minutes", 0) for s in sessions)

    # Подсчёт упражнений и подходов
    total_sets = 0
    all_exercises = []
    for s in sessions:
        plan = json.loads(s["plan_json"]) if s.get("plan_json") else {}
        for ex in plan.get("exercises", []):
            total_sets += ex.get("sets", 0)
            all_exercises.append(ex["name"])

    weights_text = "\n".join([f"- {name}: {w['weight']} кг" for name, w in current_weights.items()])

    sessions_text = "\n".join([
        f"- {s['date']}: {s['muscle_group']} ({s.get('duration_minutes', 0)} мин)"
        for s in sessions
    ])

    prompt = f"""Ты персональный тренер. Напиши мотивирующий еженедельный отчёт для спортсмена{' ' + user_name if user_name else ''}.

СТАТИСТИКА НЕДЕЛИ:
- Тренировок: {total_workouts}
- Общее время: {total_minutes} минут
- Группы мышц: {', '.join(set(muscle_groups))}
- Всего подходов: {total_sets}

ТРЕНИРОВКИ:
{sessions_text}

ТЕКУЩИЕ РАБОЧИЕ ВЕСА:
{weights_text if weights_text else 'Не указаны'}

Напиши отчёт на русском языке. Структура:
📊 *Итоги недели* — краткая статистика (2-3 предложения)
💪 *Достижения* — что было сделано хорошо
🎯 *На следующую неделю* — 2-3 конкретные цели
🔥 *Мотивация* — одна вдохновляющая фраза

Будь конкретным, используй цифры из статистики. Максимум 200 слов."""

    return _ask_ai(prompt, max_tokens=700)
