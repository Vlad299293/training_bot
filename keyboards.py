from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏋️ Начать тренировку"), KeyboardButton(text="📋 Мои упражнения")],
            [KeyboardButton(text="➕ Добавить упражнение"), KeyboardButton(text="⚖️ Рабочие веса")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📈 Прогресс")],
            [KeyboardButton(text="📋 Еженедельный отчёт"), KeyboardButton(text="🍽️ Питание")],
        ],
        resize_keyboard=True
    )


def nutrition_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🍽️ План питания на сегодня"), KeyboardButton(text="📊 Мой КБЖУ")],
            [KeyboardButton(text="🛒 Список покупок"), KeyboardButton(text="🔄 Обновить меню")],
            [KeyboardButton(text="⚖️ Внести вес тела"), KeyboardButton(text="📈 История веса")],
            [KeyboardButton(text="⚙️ Настройки питания"), KeyboardButton(text="🔙 Главное меню")],
        ],
        resize_keyboard=True
    )


def gender_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👨 Мужчина", callback_data="gender:male"),
        InlineKeyboardButton(text="👩 Женщина", callback_data="gender:female"),
    ]])


def activity_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪑 Низкая (сидячий образ жизни)", callback_data="activity:low")],
        [InlineKeyboardButton(text="🚶 Умеренная (3-4 тренировки в неделю)", callback_data="activity:moderate")],
        [InlineKeyboardButton(text="🏃 Высокая (5+ тренировок в неделю)", callback_data="activity:high")],
    ])


def phase_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Набор массы", callback_data="phase:gain")],
        [InlineKeyboardButton(text="⚖️ Поддержание веса", callback_data="phase:maintain")],
        [InlineKeyboardButton(text="📉 Уменьшение веса", callback_data="phase:loss")],
    ])


def budget_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Низкий (простые продукты)", callback_data="budget:low")],
        [InlineKeyboardButton(text="💳 Средний", callback_data="budget:medium")],
        [InlineKeyboardButton(text="💎 Без ограничений", callback_data="budget:high")],
    ])


def training_day_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏋️ Тренировочный день", callback_data="daytype:training"),
        InlineKeyboardButton(text="😴 День отдыха", callback_data="daytype:rest"),
    ]])


def muscle_groups_kb(groups: list, selected: list = None) -> InlineKeyboardMarkup:
    """Мультиселект групп мышц. Выбранные отмечаются галочкой."""
    selected = selected or []
    buttons = []
    for g in groups:
        is_selected = g in selected
        text = f"✅ {g}" if is_selected else g
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"mg:{g}")])

    # Кнопка подтверждения появляется только когда что-то выбрано
    if selected:
        label = " + ".join(selected)
        buttons.append([InlineKeyboardButton(
            text=f"🏋️ Начать: {label}",
            callback_data="mg_confirm"
        )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def exercise_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏋️ Базовое (многосуставное)", callback_data="type:compound")],
        [InlineKeyboardButton(text="💪 Изолирующее", callback_data="type:isolation")],
    ])


def skip_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip")]
    ])


def exercises_list_kb(exercises: list, prefix: str = "del") -> InlineKeyboardMarkup:
    buttons = []
    for i, ex in enumerate(exercises):
        buttons.append([InlineKeyboardButton(
            text=f"❌ {ex['name']}",
            callback_data=f"{prefix}:{i}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def weights_exercises_kb(exercises: list) -> InlineKeyboardMarkup:
    buttons = []
    for i, ex in enumerate(exercises):
        buttons.append([InlineKeyboardButton(
            text=ex["name"],
            callback_data=f"wex:{i}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
