"""
Модуль питания:
- Расчёт КБЖУ по формуле Миффлина-Сан Жеора
- Генерация недельного меню (из него берётся план на день и список покупок)
- Таблица КБЖУ продуктов на 100г в сухом/сыром виде
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

# Таблица КБЖУ на 100г продукта в сухом/сыром виде
NUTRITION_TABLE = """
ТАБЛИЦА КБЖУ ПРОДУКТОВ (на 100г в сухом или сыром виде):

КРУПЫ И ЗЛАКИ (сухой вид):
- Овсянка: 352 ккал | Б:12г | Ж:6г | У:60г
- Гречка: 313 ккал | Б:13г | Ж:3г | У:62г
- Рис белый: 344 ккал | Б:7г | Ж:1г | У:77г
- Рис бурый: 337 ккал | Б:7г | Ж:3г | У:72г
- Макароны: 338 ккал | Б:11г | Ж:2г | У:70г
- Перловка: 320 ккал | Б:9г | Ж:1г | У:67г
- Пшено: 348 ккал | Б:11г | Ж:4г | У:69г

БЕЛКОВЫЕ ПРОДУКТЫ (сырой вид):
- Куриная грудка: 113 ккал | Б:24г | Ж:2г | У:0г
- Куриное бедро без кожи: 161 ккал | Б:20г | Ж:9г | У:0г
- Говядина (вырезка): 158 ккал | Б:22г | Ж:7г | У:0г
- Индейка филе: 84 ккал | Б:19г | Ж:1г | У:0г
- Яйцо куриное (1шт=60г): 74 ккал | Б:6г | Ж:5г | У:0г
- Творог 5%: 121 ккал | Б:17г | Ж:5г | У:2г
- Творог 0%: 71 ккал | Б:16г | Ж:0г | У:2г
- Тунец консервированный: 96 ккал | Б:22г | Ж:1г | У:0г
- Лосось: 206 ккал | Б:20г | Ж:13г | У:0г
- Минтай: 72 ккал | Б:16г | Ж:1г | У:0г
- Греческий йогурт 2%: 73 ккал | Б:10г | Ж:2г | У:4г

МОЛОЧНЫЕ ПРОДУКТЫ:
- Молоко 2.5%: 52 ккал | Б:3г | Ж:3г | У:5г
- Кефир 1%: 40 ккал | Б:3г | Ж:1г | У:4г
- Сыр твёрдый: 360 ккал | Б:26г | Ж:28г | У:0г

ЖИРЫ:
- Масло оливковое: 884 ккал | Б:0г | Ж:100г | У:0г
- Масло подсолнечное: 884 ккал | Б:0г | Ж:100г | У:0г
- Арахисовая паста: 588 ккал | Б:25г | Ж:50г | У:20г
- Грецкий орех: 654 ккал | Б:15г | Ж:65г | У:7г
- Миндаль: 575 ккал | Б:21г | Ж:50г | У:13г
- Авокадо: 160 ккал | Б:2г | Ж:15г | У:9г

ОВОЩИ (сырой вид):
- Брокколи: 34 ккал | Б:3г | Ж:0г | У:7г
- Огурец: 15 ккал | Б:1г | Ж:0г | У:3г
- Помидор: 20 ккал | Б:1г | Ж:0г | У:4г
- Болгарский перец: 27 ккал | Б:1г | Ж:0г | У:6г
- Морковь: 41 ккал | Б:1г | Ж:0г | У:10г
- Капуста белокочанная: 28 ккал | Б:2г | Ж:0г | У:6г
- Шпинат: 23 ккал | Б:3г | Ж:0г | У:4г
- Кабачок: 24 ккал | Б:1г | Ж:0г | У:5г

ФРУКТЫ:
- Банан: 89 ккал | Б:1г | Ж:0г | У:23г
- Яблоко: 52 ккал | Б:0г | Ж:0г | У:14г
- Апельсин: 47 ккал | Б:1г | Ж:0г | У:12г

ХЛЕБ:
- Хлеб цельнозерновой: 247 ккал | Б:9г | Ж:3г | У:46г
- Хлебцы рисовые: 360 ккал | Б:8г | Ж:2г | У:78г

ПРИМЕЧАНИЕ: все крупы указаны в сухом виде. При варке вес увеличивается в 2.5-3 раза.
Мясо и рыба — в сыром виде. При готовке вес уменьшается на 20-30%.
"""


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


def _ask_ai(prompt: str, max_tokens: int = 3000) -> str:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens, temperature=0.7
    )
    return response.choices[0].message.content.strip()


def generate_weekly_menu(profile: dict, kbju: dict) -> dict:
    """
    Генерирует меню на 7 дней. Возвращает словарь с планом по дням.
    Из него берётся и план на день и список покупок.
    """
    allergies = ", ".join(profile.get("allergies", [])) or "нет"
    prefs = ", ".join(profile.get("preferences", [])) or "нет"
    budgets = {"low": "низкий (простые продукты)", "medium": "средний", "high": "без ограничений"}
    budget = budgets.get(profile.get("budget", "medium"), "средний")
    gender = "мужчина" if profile["gender"] == "male" else "женщина"
    phase = PHASE_LABELS[profile["phase"]]

    prompt = f"""Ты одновременно опытный диетолог, нутрициолог и персональный тренер.
Составь меню питания на 7 дней (пн-вс).

ПАРАМЕТРЫ СПОРТСМЕНА:
- Пол: {gender}, Возраст: {profile["age"]} лет
- Вес: {profile["weight"]} кг, Рост: {profile["height"]} см
- Фаза: {phase}

ЦЕЛИ КБЖУ НА ДЕНЬ:
- Обычный день: {kbju["target_calories"]} ккал | Б:{kbju["protein"]}г | Ж:{kbju["fat"]}г | У:{kbju["carbs"]}г
- Тренировочный день: {kbju["target_calories_training"]} ккал | У:{kbju["carbs_training"]}г

ОГРАНИЧЕНИЯ:
- Аллергены (исключить): {allergies}
- Предпочтения: {prefs}
- Бюджет: {budget}

{NUTRITION_TABLE}

ПРАВИЛА:
1. Используй ТОЛЬКО продукты из таблицы выше для расчёта КБЖУ
2. Все граммовки крупы и злаков — в СУХОМ виде
3. Мясо и рыба — в СЫРОМ виде
4. 4-5 приёмов пищи в день: завтрак, перекус, обед, полдник, ужин
5. Чередуй продукты по дням — не повторяй одно и то же каждый день
6. Считай КБЖУ строго по таблице выше
7. Пн, Ср, Пт — тренировочные дни (больше углеводов)
8. Вт, Чт, Сб, Вс — дни отдыха

Ответь СТРОГО в формате JSON без markdown:
{{
  "days": [
    {{
      "day": "Понедельник",  // затем Вторник, Среда, Четверг, Пятница, Суббота, Воскресенье
      "type": "тренировочный",
      "meals": [
        {{
          "name": "Завтрак",
          "items": [
            {{"product": "Овсянка", "amount": 80, "unit": "г сухой"}},
            {{"product": "Яйцо куриное", "amount": 2, "unit": "шт"}}
          ],
          "calories": 450,
          "protein": 22,
          "fat": 12,
          "carbs": 58
        }}
      ],
      "total_calories": 2800,
      "total_protein": 160,
      "total_fat": 80,
      "total_carbs": 320
    }}
  ]
}}"""

    text = _ask_ai(prompt, max_tokens=4000)
    # Чистим markdown если есть
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    # Обрезаем до последней валидной закрывающей скобки
    last_brace = text.rfind('}')
    last_bracket = text.rfind(']')
    # Находим правильный конец JSON
    for end in range(len(text), 0, -1):
        try:
            return json.loads(text[:end])
        except json.JSONDecodeError:
            continue
    raise ValueError("Не удалось распарсить JSON от ИИ")


def format_day_plan(weekly_menu: dict, day_index: int = 0) -> str:
    """Форматирует план питания на конкретный день из недельного меню."""
    days = weekly_menu.get("days", [])
    if not days or day_index >= len(days):
        return "❌ День не найден в меню"

    day = days[day_index]
    lines = [
        f"🍽️ *{day['day']}* — {day.get('type', '')}",
        f"🎯 Итого: {day['total_calories']} ккал | "
        f"Б:{day['total_protein']}г | Ж:{day['total_fat']}г | У:{day['total_carbs']}г",
        ""
    ]

    for meal in day.get("meals", []):
        lines.append(f"*{meal['name']}* — {meal['calories']} ккал")
        for item in meal.get("items", []):
            lines.append(f"  • {item['product']}: {item['amount']} {item['unit']}")
        lines.append(
            f"  _Б:{meal['protein']}г | Ж:{meal['fat']}г | У:{meal['carbs']}г_"
        )
        lines.append("")

    return "\n".join(lines)


def generate_shopping_list_from_menu(weekly_menu: dict) -> str:
    """Генерирует список покупок на основе недельного меню."""
    # Собираем все продукты из меню
    products = {}
    for day in weekly_menu.get("days", []):
        for meal in day.get("meals", []):
            for item in meal.get("items", []):
                key = item["product"]
                amount = item["amount"]
                unit = item["unit"]
                if key in products:
                    products[key]["amount"] += amount
                else:
                    products[key] = {"amount": amount, "unit": unit}

    # Форматируем список
    lines = ["🛒 *Список покупок на неделю*\n"]
    lines.append("_Рассчитано точно по меню на 7 дней:_\n")

    # Категории
    categories = {
        "🥩 Белки": ["Куриная грудка", "Куриное бедро", "Говядина", "Индейка", "Яйцо",
                      "Творог", "Тунец", "Лосось", "Минтай", "Греческий йогурт"],
        "🍚 Крупы": ["Овсянка", "Гречка", "Рис белый", "Рис бурый", "Макароны",
                      "Перловка", "Пшено", "Хлеб", "Хлебцы"],
        "🥦 Овощи": ["Брокколи", "Огурец", "Помидор", "Болгарский перец", "Морковь",
                      "Капуста", "Шпинат", "Кабачок"],
        "🍎 Фрукты": ["Банан", "Яблоко", "Апельсин"],
        "🥑 Жиры": ["Масло оливковое", "Масло подсолнечное", "Арахисовая паста",
                     "Грецкий орех", "Миндаль", "Авокадо"],
        "🥛 Молочное": ["Молоко", "Кефир", "Сыр", "Йогурт"],
    }

    categorized = set()
    for cat_name, cat_products in categories.items():
        cat_items = []
        for prod_name, data in products.items():
            for cat_prod in cat_products:
                if cat_prod.lower() in prod_name.lower():
                    cat_items.append(f"• {prod_name}: {round(data['amount'])} {data['unit']}")
                    categorized.add(prod_name)
                    break
        if cat_items:
            lines.append(f"*{cat_name}:*")
            lines.extend(cat_items)
            lines.append("")

    # Остальные продукты
    other = [f"• {k}: {round(v['amount'])} {v['unit']}"
             for k, v in products.items() if k not in categorized]
    if other:
        lines.append("*🧂 Прочее:*")
        lines.extend(other)

    return "\n".join(lines)
