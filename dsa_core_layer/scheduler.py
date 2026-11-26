# scheduler.py — choose exercises that fit the daily time budget.
# Idea: use 0/1 knapsack DP with a bitmask to track trained muscle groups.
# Time: O(items x time_units x 512). Space: O(time_units x 512).

NUM_GROUPS = 9
POOL_CAP = 30
MIN_GROUPS = 3
MAX_DAILY_MIN = 120
# Below this daily time, plan main exercises by exact minutes.
SHORT_DAY_MIN = 20


def daily_budget_minutes(profile):
    """Return the minutes the user has in one day, capped at MAX_DAILY_MIN."""
    return min(profile["session_min"] * profile["sessions_per_day"], MAX_DAILY_MIN)


def fit_to_time(ranked, minutes, count):
    """Take up to `count` exercises in rank order whose total time fits `minutes`."""
    picked = []
    remaining = minutes
    for score, exercise in ranked:
        if len(picked) == count:
            break
        if exercise["duration_min"] <= remaining:
            picked.append((score, exercise))
            remaining -= exercise["duration_min"]
    return picked


def count_bits(mask):
    count = 0
    # Count the groups represented by 1-bits in this mask.
    while mask > 0:
        count += mask & 1
        mask = mask >> 1
    return count


def create_dp(budget_units, num_masks):
    dp = []
    # Create one row for every possible amount of time.
    for time_used in range(budget_units + 1):
        dp.append([None] * num_masks)
    dp[0][0] = (0, [])
    return dp


def update_dp_for_exercise(dp, exercise, index, budget_units, num_masks):
    time_used = budget_units - exercise["units"]
    # Go downwards so this exercise cannot be selected more than once.
    while time_used >= 0:
        # Try adding this exercise to every state already reached.
        for mask in range(num_masks):
            current = dp[time_used][mask]
            if current is None:
                continue
            new_time = time_used + exercise["units"]
            new_mask = mask | exercise["bit"]
            new_score = current[0] + exercise["score"]
            old = dp[new_time][new_mask]
            if old is None or new_score > old[0]:
                dp[new_time][new_mask] = (new_score, current[1] + [index])
        time_used -= 1


def find_best_states(dp, budget_units, num_masks, min_groups):
    best = None
    fallback = None
    # Look at every possible time and muscle-group combination.
    for time_used in range(budget_units + 1):
        for mask in range(num_masks):
            state = dp[time_used][mask]
            if state is None:
                continue
            if fallback is None or state[0] > fallback[0]:
                fallback = state
            if count_bits(mask) >= min_groups:
                if best is None or state[0] > best[0]:
                    best = state
    return best, fallback


def solve_daily_knapsack(pool, budget_units, min_groups, num_groups=NUM_GROUPS):
    num_masks = 1 << num_groups
    dp = create_dp(budget_units, num_masks)
    # Add each candidate to the DP table once.
    for index in range(len(pool)):
        update_dp_for_exercise(dp, pool[index], index, budget_units, num_masks)
    best, fallback = find_best_states(dp, budget_units, num_masks, min_groups)
    if best is not None:
        return best[1], best[0], True
    if fallback is None:
        return [], 0, False
    return fallback[1], fallback[0], False


def to_dp_items(exercises, scores, group_bits, exact_minutes=False):
    items = []
    # Keep only the score, time and group bit needed by the DP.
    for index in range(len(exercises)):
        items.append({
            "score": scores[index],
            "units": exercises[index]["duration_min" if exact_minutes else "units"],
            "bit": group_bits[exercises[index]["group"]]
        })
    return items


def pick_support_move(groups_today, exercise_pool, used_names):
    picked = []
    # Prefer a warm-up or cool-down that matches one of today's trained groups.
    for group in groups_today:
        for exercise in exercise_pool:
            if exercise["group"] == group and exercise["name"] not in used_names:
                picked.append(exercise)
                used_names.add(exercise["name"])
                return picked

    # If no matching group is available, choose the first unused general movement.
    for exercise in exercise_pool:
        if exercise["name"] not in used_names:
            picked.append(exercise)
            used_names.add(exercise["name"])
            return picked

    # Reuse the first movement only after every movement in this pool has appeared.
    if len(exercise_pool) > 0:
        used_names.clear()
        picked.append(exercise_pool[0])
        used_names.add(exercise_pool[0]["name"])
    return picked


def pick_hip_mobility(hip_pool, used_names, max_count):
    picked = []
    # Pick new hip-mobility exercises before repeating an earlier one.
    for exercise in hip_pool:
        if exercise["name"] not in used_names:
            picked.append(exercise)
            used_names.add(exercise["name"])
        if len(picked) == max_count:
            break

    # Start again only if the available hip-mobility pool has been used up.
    if len(picked) < max_count and len(hip_pool) > 0:
        used_names.clear()
        for exercise in hip_pool:
            if exercise not in picked:
                picked.append(exercise)
            if len(picked) == max_count:
                break
        for exercise in picked:
            used_names.add(exercise["name"])
    return picked


def get_available_candidates(ranked, used):
    available = []
    # Keep exercises that have not been assigned to an earlier day.
    for score, exercise in ranked:
        if exercise["name"] not in used:
            available.append((score, exercise))
    if len(available) < 10:
        return ranked, True
    return available, False


def select_daily_exercises(candidates, budget_units, group_bits, exact_minutes=False):
    exercises = []
    scores = []
    # Split ranked records into the data needed by the knapsack.
    for score, exercise in candidates:
        exercises.append(exercise)
        scores.append(score)
    items = to_dp_items(exercises, scores, group_bits, exact_minutes)
    chosen, total_score, groups_ok = solve_daily_knapsack(
        items, budget_units, MIN_GROUPS, len(group_bits)
    )

    todays = []
    groups_today = []
    minutes = 0
    # Convert the selected indexes back into exercise records.
    for index in chosen:
        exercise = exercises[index]
        todays.append(exercise)
        minutes += exercise["duration_min"]
        if exercise["group"] not in groups_today and exercise["group"] != "Cardio":
            groups_today.append(exercise["group"])
    return todays, groups_today, minutes, total_score, groups_ok


def sum_minutes(exercises):
    total = 0
    # Add the supplied duration of each optional movement.
    for exercise in exercises:
        total += exercise["duration_min"]
    return total


def build_day_entry(day_index, selected, include_support, warm_up_pool, cool_down_pool,
                    hip_mobility, used_warm_up_names, used_cool_down_names):
    todays, groups_today, main_minutes, total_score, groups_ok = selected
    warm_up = []
    cool_down = []

    if include_support:
        warm_up = pick_support_move(groups_today, warm_up_pool, used_warm_up_names)
        cool_down = pick_support_move(groups_today, cool_down_pool, used_cool_down_names)

    # Hip Mobility is part of the session time; warm-up and cool-down are not.
    total_minutes = main_minutes + sum_minutes(hip_mobility)
    return {
        "day": "Day " + str(day_index + 1),
        "exercises": todays,
        "warm_up": warm_up,
        "cool_down": cool_down,
        "hip_mobility": hip_mobility,
        "total_minutes": total_minutes,
        "main_minutes": main_minutes,
        "score": total_score,
        "min_groups_met": groups_ok
    }


def generate_weekly_schedule(ranked, profile, include_support, warm_up_pool,
                             cool_down_pool, include_hip_mobility, hip_mobility_pool,
                             group_bits, unit_min):
    daily_minutes = daily_budget_minutes(profile)
    used = set()
    used_warm_up_names = set()
    used_cool_down_names = set()
    used_hip_names = set()
    week = []
    # Build the requested number of training days without repeating main exercises early.
    for day_index in range(profile["days_per_week"]):
        hip_mobility = []
        if include_hip_mobility:
            hip_mobility = pick_hip_mobility(hip_mobility_pool, used_hip_names, 2)
        # Main exercises share whatever time Hip Mobility leaves.
        main_budget = daily_minutes - sum_minutes(hip_mobility)
        short_day = main_budget < SHORT_DAY_MIN
        if short_day:
            # Rounding to 2-minute units would drop 5-minute moves from a 5-minute day.
            budget_units = main_budget
        else:
            budget_units = main_budget // unit_min
        # Drop exercises that are too long before the candidate pool is capped.
        fitting = [pair for pair in ranked if pair[1]["duration_min"] <= main_budget]

        available, reset_used = get_available_candidates(fitting, used)
        if reset_used:
            used = set()
        candidates = available[:POOL_CAP]
        selected = select_daily_exercises(candidates, budget_units, group_bits, short_day)
        day_entry = build_day_entry(
            day_index, selected, include_support, warm_up_pool, cool_down_pool,
            hip_mobility, used_warm_up_names, used_cool_down_names
        )

        # Remember the main exercises already used this week.
        for exercise in day_entry["exercises"]:
            used.add(exercise["name"])
        week.append(day_entry)
    return week
