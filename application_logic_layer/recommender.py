"""Connect profile validation, exercise ranking, progression and scheduling."""

from dsa_core_layer.exercise_ranker import rank_exercises, rank_by_muscle_group
from dsa_core_layer.scheduler import (
    generate_weekly_schedule, daily_budget_minutes, fit_to_time, session_minutes,
    REST_BETWEEN_EXERCISES_MIN
)
from application_logic_layer.profile_parser import parse_profile


def public_exercise(exercise):
    """Return the exercise fields used by the browser."""
    result = {}
    fields = [
        "id", "name", "level", "mechanic", "equipment", "category",
        "primary_muscle", "steps", "group", "secondary_muscles",
        "duration_min", "activity_type", "needs_bar", "role"
    ]
    for field in fields:
        result[field] = exercise[field]

    result["step_list"] = []
    for step in exercise["steps"].split("||"):
        clean_step = step.strip()
        if clean_step:
            result["step_list"].append(clean_step)
    return result


def public_ranked(ranked, profile, beginner_bonus_names):
    result = []
    for score, exercise in ranked:
        item = public_exercise(exercise)
        item["score"] = score
        item["beginner_bonus"] = profile["level"] == "beginner" and exercise["name"] in beginner_bonus_names
        result.append(item)
    return result


def recommend(payload, dataset):
    profile = parse_profile(payload)

    beginner_bonus_names = dataset["beginner_bonus_names"]
    all_ranked = rank_exercises(dataset["main_pool"], profile, len(dataset["main_pool"]), beginner_bonus_names)

    # Today Plan: same ranking, limited to the time the user has today.
    today_minutes = daily_budget_minutes(profile)
    hip_pairs = rank_exercises(
        dataset["hip_mobility_pool"], profile, len(dataset["hip_mobility_pool"]), beginner_bonus_names
    )
    # Chosen Hip Mobility moves count as normal exercises, so they take their time first.
    today_hip = []
    if profile["include_hip_mobility"]:
        today_hip = fit_to_time(hip_pairs, today_minutes, 2)
    main_minutes = today_minutes
    if today_hip:
        # Leave room for Hip Mobility and for the rest before it.
        hip_exercises = [exercise for score, exercise in today_hip]
        main_minutes -= session_minutes(hip_exercises) + REST_BETWEEN_EXERCISES_MIN
    top_ranked = fit_to_time(all_ranked, main_minutes, 5) + today_hip
    group_ranked = rank_by_muscle_group(
        dataset["muscle_index"], profile, len(dataset["main_pool"]), beginner_bonus_names
    )
    for group in group_ranked:
        group_ranked[group] = fit_to_time(group_ranked[group], today_minutes, 3)

    warm_up_pairs = rank_exercises(
        dataset["warm_up_pool"], profile, len(dataset["warm_up_pool"]), beginner_bonus_names
    )
    warm_up_ranked = []
    for score, exercise in warm_up_pairs:
        warm_up_ranked.append(exercise)

    cool_down_pairs = rank_exercises(
        dataset["cool_down_pool"], profile, len(dataset["cool_down_pool"]), beginner_bonus_names
    )
    cool_down_ranked = []
    for score, exercise in cool_down_pairs:
        cool_down_ranked.append(exercise)

    hip_ranked = []
    for score, exercise in hip_pairs:
        hip_ranked.append(exercise)

    schedule = generate_weekly_schedule(
        all_ranked,
        profile,
        profile["include_stretch"],
        warm_up_ranked,
        cool_down_ranked,
        profile["include_hip_mobility"],
        hip_ranked,
        dataset["group_bit"]
    )

    public_schedule = []
    for day in schedule:
        public_day = {
            "day": day["day"],
            "total_minutes": day["total_minutes"],
            "main_minutes": day["main_minutes"],
            "rest_minutes": day["rest_minutes"],
            "score": day["score"],
            "min_groups_met": day["min_groups_met"],
            "exercises": [],
            "warm_up": [],
            "cool_down": [],
            "hip_mobility": []
        }
        for exercise in day["exercises"]:
            public_day["exercises"].append(public_exercise(exercise))
        for exercise in day["warm_up"]:
            public_day["warm_up"].append(public_exercise(exercise))
        for exercise in day["cool_down"]:
            public_day["cool_down"].append(public_exercise(exercise))
        for exercise in day["hip_mobility"]:
            public_day["hip_mobility"].append(public_exercise(exercise))
        public_schedule.append(public_day)

    public_groups = {}
    for group in group_ranked:
        public_groups[group] = public_ranked(group_ranked[group], profile, beginner_bonus_names)

    return {
        "profile": {
            "height_cm": profile["height_cm"],
            "weight_kg": profile["weight_kg"],
            "age": profile["age"],
            "level": profile["level"],
            "goals": profile["goals"],
            "bmi": profile["bmi"],
            "bmi_class": profile["bmi_class"],
            "bmi_standard": profile["bmi_standard"]
        },
        "today_minutes": today_minutes,
        "rest_between_exercises_min": REST_BETWEEN_EXERCISES_MIN,
        "top_k": public_ranked(top_ranked, profile, beginner_bonus_names),
        "by_group": public_groups,
        "schedule": public_schedule
    }
