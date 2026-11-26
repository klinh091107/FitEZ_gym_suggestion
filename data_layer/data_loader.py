"""Load the exercise CSV and build simple in-memory indexes."""

import csv
import json

GROUP_NAMES = [
    "Chest", "Back", "Shoulders", "Arms", "LegsFront",
    "Posterior", "Core", "Cardio", "hip_mobility"
]
MAIN_GROUP_NAMES = [
    "Chest", "Back", "Shoulders", "Arms", "LegsFront",
    "Posterior", "Core", "Cardio"
]
GROUP_BIT = {}
for index in range(len(GROUP_NAMES)):
    GROUP_BIT[GROUP_NAMES[index]] = 1 << index

UNIT_MIN = 2

# The new CSV contains a few extra labels. Map them to the project's
# eight training groups so the scheduler keeps one consistent group system.
PRIMARY_MUSCLE_GROUP = {
    "chest": "Chest",
    "lats": "Back", "middle back": "Back", "upper back": "Back", "traps": "Back",
    "shoulders": "Shoulders",
    "biceps": "Arms", "triceps": "Arms", "forearms": "Arms",
    "quadriceps": "LegsFront", "calves": "LegsFront", "adductors": "LegsFront",
    "abductors": "Posterior", "hamstrings": "Posterior", "glutes": "Posterior",
    "lower back": "Posterior", "hip flexors": "Posterior",
    "abdominals": "Core", "obliques": "Core", "serratus": "Core", "neck": "Core"
}

GROUP_ALIASES = {
    "Glutes": "Posterior",
    "Legs": "LegsFront"
}


def as_bool(value):
    """Read a True/False text value from the CSV."""
    return str(value).strip().lower() in ("true", "1", "yes")


def normalize_group(row):
    source_group = row["group"]
    if source_group in GROUP_ALIASES:
        return GROUP_ALIASES[source_group]
    if source_group in GROUP_NAMES:
        return source_group
    # 'Upper' and 'Stretching' are broad source labels. Use the primary
    # muscle to place them into the same groups used by the weekly planner.
    muscle = row.get("primary_muscle", "").strip().lower()
    if muscle in PRIMARY_MUSCLE_GROUP:
        return PRIMARY_MUSCLE_GROUP[muscle]
    raise ValueError("Cannot map exercise group: " + source_group + " (" + row["name"] + ")")


def add_derived_fields(row):
    """Convert CSV fields and add values used by the algorithms."""
    row["id"] = int(row["id"])
    row["duration_min"] = int(row["duration_min"])
    row["units"] = (row["duration_min"] + UNIT_MIN - 1) // UNIT_MIN
    row["source_group"] = row["group"]
    row["group"] = normalize_group(row)
    row["source_level"] = row["level"]
    if row["level"] == "advanced":
        row["level"] = "expert"
    row["source_equipment"] = row["equipment"]
    if row["equipment"] == "kettlebell":
        row["equipment"] = "kettlebells"
    row["bit"] = GROUP_BIT[row["group"]]
    row["impact"] = "high" if row["category"] == "plyometrics" else "low"
    row["needs_bar"] = as_bool(row["needs_bar"])
    row["is_stretching"] = as_bool(row["is_stretching"])
    secondary = row["secondary_muscles"]
    if not secondary:
        row["n_groups"] = 1
    else:
        row["n_groups"] = 1 + len(secondary.split("|"))
    return row


def load_muscle_images(table_path):
    """Map each primary muscle (lowercase) to its image file name."""
    images = {}
    with open(table_path, encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            images[row["Primary Muscle"].strip().lower()] = row["Image file"].strip()
    return images


def load_data(exercises_path, beginner_path):
    """Load all rows, separate exercise pools and validate Beginner bonuses."""
    with open(exercises_path, encoding="utf-8-sig", newline="") as file:
        source_rows = list(csv.DictReader(file))
    if len(source_rows) == 0:
        raise ValueError("The exercise CSV must contain at least one row.")

    with open(beginner_path, encoding="utf-8") as file:
        beginner_data = json.load(file)

    all_rows = []
    by_name = {}
    main_pool = []
    warm_up_pool = []
    cool_down_pool = []
    hip_mobility_pool = []
    muscle_index = {}

    for source_row in source_rows:
        row = add_derived_fields(dict(source_row))
        if row["name"] in by_name:
            raise ValueError("Duplicate exercise name in CSV: " + row["name"])
        all_rows.append(row)
        by_name[row["name"]] = row

        # Keep hip mobility separate even when its role says warm up/cool down.
        if row["source_group"] == "hip_mobility":
            hip_mobility_pool.append(row)
        elif row["role"] == "warm up":
            warm_up_pool.append(row)
        elif row["role"] == "cool down":
            cool_down_pool.append(row)
        else:
            main_pool.append(row)
            group = row["group"]
            if group not in muscle_index:
                muscle_index[group] = []
            muscle_index[group].append(row)

    beginner_bonus_names = set()
    for name in beginner_data["bonus_exercise_names"]:
        if name in by_name:
            beginner_bonus_names.add(name)
        # Names absent from this CSV are deliberately ignored. The unmatched
        # list remains in the JSON for transparency and does not break startup.

    return {
        "all_rows": all_rows,
        "by_name": by_name,
        "main_pool": main_pool,
        "warm_up_pool": warm_up_pool,
        "cool_down_pool": cool_down_pool,
        "hip_mobility_pool": hip_mobility_pool,
        "muscle_index": muscle_index,
        "group_names": GROUP_NAMES,
        "main_group_names": MAIN_GROUP_NAMES,
        "group_bit": GROUP_BIT,
        "beginner_bonus_names": beginner_bonus_names,
        "beginner_bonus_points": beginner_data["bonus_points"],
        "beginner_bonus_match_count": len(beginner_bonus_names),
        "beginner_bonus_unmatched_count": len(beginner_data.get("unmatched_items", []))
    }
