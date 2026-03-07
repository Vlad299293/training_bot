from aiogram.fsm.state import State, StatesGroup


class AddExerciseStates(StatesGroup):
    waiting_name = State()
    waiting_muscle_group = State()
    waiting_type = State()       # базовое / изолирующее
    waiting_notes = State()


class WorkoutStates(StatesGroup):
    waiting_muscle_group = State()
    waiting_time = State()


class WeightStates(StatesGroup):
    waiting_exercise_name = State()
    waiting_weight = State()


class DeleteExerciseStates(StatesGroup):
    waiting_name = State()


class MoodStates(StatesGroup):
    waiting_score = State()
    waiting_notes = State()


class NutritionSetupStates(StatesGroup):
    waiting_gender = State()
    waiting_age = State()
    waiting_weight = State()
    waiting_height = State()
    waiting_activity = State()
    waiting_phase = State()
    waiting_allergies = State()
    waiting_preferences = State()
    waiting_budget = State()


class BodyWeightStates(StatesGroup):
    waiting_weight = State()
