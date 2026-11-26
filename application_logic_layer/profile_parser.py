"""Validate the user's profile and calculate BMI with the selected standard."""

import math

LEVELS = ["beginner", "intermediate", "expert"]
ALLOWED_GOALS = ["build_muscle", "get_stronger", "lose_weight", "endurance"]
ALLOWED_EQUIPMENT = [
    "dumbbell", "barbell", "kettlebells", "cable", "machine", "bands",
    "medicine ball", "exercise ball", "e-z curl bar", "foam roll", "other"
]
BMI_STANDARDS = ["asian", "european"]
GROUPS = [
    "Chest", "Back", "Shoulders", "Arms", "LegsFront",
    "Posterior", "Core", "Cardio"
]


def _number(payload, field, minimum, maximum):
    if field not in payload:
        raise ValueError("Missing required field: " + field)
    value = payload[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(field + " must be a number.")
    if not math.isfinite(value):
        raise ValueError(field + " must be a finite number.")
    if value < minimum or value > maximum:
        raise ValueError(field + " must be between " + str(minimum) + " and " + str(maximum) + ".")
    return value


def _integer(payload, field, minimum, maximum):
    value = _number(payload, field, minimum, maximum)
    if int(value) != value:
        raise ValueError(field + " must be a whole number.")
    return int(value)


def compute_bmi(height_cm, weight_kg, standard="asian"):
    """Return BMI and its label using either Asian or European cutoffs."""
    if standard not in BMI_STANDARDS:
        raise ValueError("bmi_standard must be asian or european.")

    height_m = height_cm / 100
    bmi = round(weight_kg / (height_m * height_m), 1)

    if bmi < 18.5:
        label = "Underweight"
    elif standard == "asian" and bmi < 23:
        label = "Normal"
    elif standard == "european" and bmi < 25:
        label = "Normal"
    elif standard == "asian" and bmi < 25:
        label = "Overweight"
    elif standard == "european" and bmi < 30:
        label = "Overweight"
    else:
        label = "Obese"

    return bmi, label


def parse_profile(payload):
    """Check every profile field before it reaches the recommendation algorithms."""
    if not isinstance(payload, dict):
        raise ValueError("The request body must be a JSON object.")

    height_cm = _number(payload, "height_cm", 120, 230)
    weight_kg = _number(payload, "weight_kg", 30, 180)
    age = _integer(payload, "age", 16, 60)
    session_min = _integer(payload, "session_min", 5, 120)
    sessions_per_day = _integer(payload, "sessions_per_day", 1, 3)
    days_per_week = _integer(payload, "days_per_week", 1, 6)

    level = payload.get("level")
    if level not in LEVELS:
        raise ValueError("level must be beginner, intermediate, or expert.")

    goals = payload.get("goals")
    if not isinstance(goals, list) or len(goals) == 0:
        raise ValueError("Select at least one training goal.")
    for goal in goals:
        if goal not in ALLOWED_GOALS:
            raise ValueError("Unknown training goal: " + str(goal))

    equipment = payload.get("equipment", [])
    if not isinstance(equipment, list):
        raise ValueError("equipment must be a list.")
    for item in equipment:
        if item not in ALLOWED_EQUIPMENT:
            raise ValueError("Unknown equipment: " + str(item))

    focus_muscles = payload.get("focus_muscles", [])
    if not isinstance(focus_muscles, list):
        raise ValueError("focus_muscles must be a list.")
    for group in focus_muscles:
        if group not in GROUPS:
            raise ValueError("Unknown focus muscle group: " + str(group))

    bmi_standard = payload.get("bmi_standard", "asian")
    if bmi_standard not in BMI_STANDARDS:
        raise ValueError("bmi_standard must be asian or european.")

    has_pullup_bar = payload.get("has_pullup_bar", False)
    include_stretch = payload.get("include_stretch", True)
    include_hip_mobility = payload.get("include_hip_mobility", False)

    if not isinstance(has_pullup_bar, bool):
        raise ValueError("has_pullup_bar must be true or false.")
    if not isinstance(include_stretch, bool):
        raise ValueError("include_stretch must be true or false.")
    if not isinstance(include_hip_mobility, bool):
        raise ValueError("include_hip_mobility must be true or false.")
    if include_hip_mobility and session_min <= 10:
        raise ValueError("Hip mobility is available only when a session is longer than 10 minutes.")

    bmi, bmi_class = compute_bmi(height_cm, weight_kg, bmi_standard)

    return {
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "age": age,
        "level": level,
        "goals": goals,
        "equipment": equipment,
        "focus_muscles": focus_muscles,
        "session_min": session_min,
        "sessions_per_day": sessions_per_day,
        "days_per_week": days_per_week,
        "has_pullup_bar": has_pullup_bar,
        "include_stretch": include_stretch,
        "include_hip_mobility": include_hip_mobility,
        "bmi_standard": bmi_standard,
        "bmi": bmi,
        "bmi_class": bmi_class
    }
