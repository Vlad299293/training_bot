"""
Модуль питания:
- Расчёт КБЖУ по формуле Миффлина-Сан Жеора
- Три фазы: набор массы / поддержание веса / уменьшение веса
- Персональный план питания через ИИ
- Список покупок на неделю
"""

import json
from groq import Groq
from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)

ACTIVITY_LABELS = {
    "low":      "низкая (сидячий образ жизни)",
    "moderate": "умеренная (3-4 тренировки в неделю)",
    "high":     "высокая (5+ тренировок в неделю)",
}
ACTIVITY_COEFFICIENTS = {"low": 1.375, "moderate": 1.55, "high": 1.725}
PHASE_LABELS = {"gain": "Набор массы", "maintain": "Поддержание веса", "loss": "Уменьшение веса"}
PHASE_ADJUSTMENTS = {"gain": +250, "maintain": 0, "loss": -400}


def calculate_kbju(profile: dict) -> dict:
    w, h, a, g = profile["weight"], profile["height"], profile["age"], profile["gender"]
    if g == "male":
        bmr = 88.36 + (13.4 * w) + (4.8 * h) - (5.7 * a)
        formula = f"88.36 + (13.4 × {w}) + (4.8 × {h}) - (5.7 × {a})"
    else:
        bmr = 447.6 + (9.2 * w) + (3.1 * h) - (4.3 * a)
        formula = f"447.6 + (9.2 × {w}) + (3.1 × {h}) - (4.3 × {a})"
    bmr = round(bmr)
    coef = ACTIVITY_COEFFICIENTS[profile["activity"]]
    tdee = round(bmr * coef)
    adj = PHASE_ADJUSTMENTS[profile["phase"]]
    cal = tdee + adj
    protein = round(w * 2.0)
    fat = round(w * 1.0)
    carbs = max(round((cal - protein * 4 - fat * 9) / 4), 50)
    return {
        "bmr": bmr, "bmr_formula": formula, "tdee": tdee, "coef": coef,
        "activity_label": ACTIVITY_LABELS[profile["activity"]],
        "phase_label": PHASE_LABELS[profile["phase"]],
        "adjustment": adj, "target_calories": cal,
        "target_calories_training": cal + 100,
        "protein": protein, "fat": fat, "carbs": carbs, "carbs_training": carbs + 25,
    }


def format_kbju_message(profile: dict, kbju: dict) -> str:
    g = "мужчина" if profile["gender"] == "male" else "женщина"
    adj = kbju["adjustment"]
    adj_str = f"+{adj}" if adj > 0 else str(adj)
    lines = [
        "📊 *Твой расчёт КБЖУ*",
        f"_{g}, {profile['age']} лет, {profile['weight']} кг, {profile['height']} см_",
        "",
        "🔬 *Формула Миффлина-Сан Жеора* — один из наиболее точных методов расчёта для спортсменов:",
        f"`BMR = {kbju['bmr_formula']}`",
        f"Базовый обмен веществ: *{kbju['bmr']} ккал*",
        "",
        f"Коэффициент активности ({kbju['activity_label']}): × {kbju['coef']}",
        f"Суточная норма (TDEE): *{kbju['tdee']} ккал*",
        "",
        f"Фаза — *{kbju['phase_label']}*: {adj_str} ккал",
        f"🎯 Цель: *{kbju['target_calories']} ккал/день*",
        f"🏋️ В тренировочный день: *{kbju['target_calories_training']} ккал*",
        "", "─" * 30,
        "*Макронутриенты на обычный день:*",
        f"🥩 Белки: *{kbju['protein']}г* ({kbju['protein'] * 4} ккал)",
        f"🥑 Жиры: *{kbju['fat']}г* ({kbju['fat'] * 9} ккал)",
        f"🍚 Углеводы: *{kbju['carbs']}г* ({kbju['carbs'] * 4} ккал)",
        "",
        "*В тренировочный день (+100 ккал за счёт углеводов):*",
        f"🍚 Углеводы: *{kbju['carbs_training']}г*",
    ]
    return "\n".join(lines)


def _ask_ai(prompt: str, max_tokens: int = 2000) -> str:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens, temperature=0.7
    )
    return response.choices[0].message.content.strip()


def generate_meal_plan(profile: dict, kbju: dict, is_training_day: bool = False) -> str:
    cal = kbju["target_calories_training"] if is_training_day else kbju["target_calories"]
    carbs = kbju["carbs_training"] if is_training_day else kbju["carbs"]
    allergies = ", ".join(profile.get("allergies", [])) or "нет"
    prefs = ", ".join(profile.get("preferences", [])) or "нет"
    budgets = {"low": "низкий (простые продукты)", "medium": "средний", "high": "без ограничений"}
    budget = budgets.get(profile.get("budget", "medium"), "средний")
    day_type = "ТРЕНИРОВОЧНЫЙ ДЕНЬ" if is_training_day else "ДЕНЬ ОТДЫХА"
    gender = "мужчина" if profile["gender"] == "male" else "женщина"
    phase = PHASE_LABELS[profile["phase"]]

    prompt = f"""Ты одновременно опытный диетолог, нутрициолог и персональный тренер.
Составь подробный план питания на один день.

ПАРАМЕТРЫ СПОРТСМЕНА:
- Пол: {gender}, Возраст: {profile["age"]} лет
- Вес: {profile["weight"]} кг, Рост: {profile["height"]} см
- Фаза: {phase}
- Тип дня: {day_type}

ЦЕЛИ КБЖУ:
- Калории: {cal} ккал
- Белки: {kbju["protein"]}г | Жиры: {kbju["fat"]}г | Углеводы: {carbs}г

ОГРАНИЧЕНИЯ:
- Аллергены (исключить полностью): {allergies}
- Предпочтения: {prefs}
- Бюджет: {budget}

ПРАВИЛА:
1. 4-5 приёмов пищи: завтрак, перекус, обед, полдник, ужин
2. {"После тренировки — обязательный приём белка + быстрых углеводов в течение 30-60 минут" if is_training_day else "День отдыха — меньше углеводов вечером, акцент на белок и полезные жиры"}
3. Конкретные граммовки каждого продукта
4. КБЖУ каждого приёма пищи
5. Только российские продукты из обычного супермаркета
6. Итоговый КБЖУ в конце и насколько близко к цели
7. 1-2 практических совета для фазы "{phase}"

Пиши структурированно на русском языке."""

    return _ask_ai(prompt, max_tokens=2000)


def generate_shopping_list(profile: dict, kbju: dict, days: int = 7) -> str:
    allergies = ", ".join(profile.get("allergies", [])) or "нет"
    prefs = ", ".join(profile.get("preferences", [])) or "нет"
    budgets = {"low": "низкий", "medium": "средний", "high": "без ограничений"}
    budget = budgets.get(profile.get("budget", "medium"), "средний")

    prompt = f"""Ты опытный нутрициолог. Составь список покупок на {days} дней.

ПАРАМЕТРЫ:
- Фаза: {PHASE_LABELS[profile["phase"]]}
- Калории: ~{kbju["target_calories"]} ккал/день
- Б/Ж/У: {kbju["protein"]}г / {kbju["fat"]}г / {kbju["carbs"]}г
- Аллергены (исключить): {allergies}
- Предпочтения: {prefs}
- Бюджет: {budget}

Список по категориям с количеством на {days} дней.
Только продукты из российского супермаркета.

🥩 Белки (мясо, рыба, яйца, молочное)
🥦 Овощи и зелень
🍚 Крупы и углеводы
🥑 Жиры (масла, орехи)
🍎 Фрукты
🧂 Специи и добавки

В конце — примерная стоимость при бюджете "{budget}".
Отвечай на русском языке."""

    return _ask_ai(prompt, max_tokens=1500)
