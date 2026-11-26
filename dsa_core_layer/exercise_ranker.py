# exercise_ranker.py — remove unsuitable exercises and rank the remaining ones.
# Idea: apply transparent hard filters, then use a weighted score and a max-heap.
# Time: O(N + K log N). Space: O(N) for scored records and the heap.

from dsa_core_layer.structures.max_heap import get_top_k

LEVEL_RANK = {"beginner": 1, "intermediate": 2, "expert": 3}

def passes_filters(exercise, profile):
    if exercise["equipment"] != "body only" and exercise["equipment"] not in profile["equipment"]:
        return False
    if exercise["needs_bar"] and not profile["has_pullup_bar"]:
        return False
    if LEVEL_RANK[exercise["level"]] > LEVEL_RANK[profile["level"]]:
        return False
    if exercise["impact"] == "high" and profile["bmi_class"] == "Obese":
        return False
    return True

def goal_matches(exercise, goal):
    if goal == "build_muscle":
        return exercise["category"] == "strength"
    if goal == "get_stronger":
        if exercise["category"] in ("powerlifting", "olympic weightlifting", "strongman"):
            return True
        return exercise["mechanic"] == "compound"
    if goal == "lose_weight":
        if exercise["group"] == "Cardio" or exercise["category"] == "plyometrics":
            return True
        return exercise["mechanic"] == "compound"
    if goal == "endurance":
        return exercise["group"] == "Cardio" or exercise["category"] == "plyometrics"
    return False

def score_exercise(exercise, profile, beginner_bonus_names=None):
    score = 0
    # Add five points for each selected goal that this exercise supports.
    for goal in profile["goals"]:
        if goal_matches(exercise, goal):
            score += 5
    if exercise["group"] in profile["focus_muscles"]:
        score += 3
    if exercise["level"] == profile["level"]:
        score += 2
    if exercise["mechanic"] == "compound":
        score += 1
    if profile["level"] == "beginner" and beginner_bonus_names is not None:
        if exercise["name"] in beginner_bonus_names:
            score += 1
    return score

def rank_exercises(pool, profile, count, beginner_bonus_names=None):
    items = []
    # Score only exercises that pass every hard constraint.
    for exercise in pool:
        if passes_filters(exercise, profile):
            score = score_exercise(exercise, profile, beginner_bonus_names)
            key = (score, exercise["n_groups"], exercise["id"])
            items.append((key, exercise))
    best_items = get_top_k(items, count)
    result = []
    # Convert heap records into the score-and-exercise format used by the application.
    for item in best_items:
        result.append((item[0][0], item[1]))
    return result

def rank_by_muscle_group(muscle_index, profile, count, beginner_bonus_names=None):
    result = {}
    # Rank each indexed bucket independently for the group breakdown.
    for group in muscle_index:
        result[group] = rank_exercises(muscle_index[group], profile, count, beginner_bonus_names)
    return result
