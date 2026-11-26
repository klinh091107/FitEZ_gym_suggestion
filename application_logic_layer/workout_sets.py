"""Small curated workout sets built only from exercises in the supplied CSV."""

WORKOUT_SET_DEFINITIONS = [
    {
        "id": "stretch-reset",
        "title": "10-Minute Stretch Reset",
        "tag": "FLEXIBILITY",
        "description": "A gentle seated and floor-based cool-down for your back and posterior chain.",
        "level": "Beginner",
        "equipment": "Body only",
        "exercise_names": ["Spinal Stretch", "Seated Forward Fold", "Slow Walk Recovery"]
    },
    {
        "id": "office-break",
        "title": "10-Minute Office Break",
        "tag": "DESK-FRIENDLY",
        "description": "A short movement break: activate your calves, then walk easily to reset after sitting.",
        "level": "Beginner",
        "equipment": "Body only · wall for balance",
        "exercise_names": ["Bodyweight Calf Raise", "Slow Walk Recovery"]
    },
    {
        "id": "home-cardio",
        "title": "10-Minute Home Cardio",
        "tag": "CARDIO",
        "description": "A short jump-rope interval session. Clear a safe space and alternate work with rest as described.",
        "level": "Intermediate",
        "equipment": "Jump rope",
        "exercise_names": ["Jump Rope Intervals"]
    }
]


def build_workout_sets(dataset, public_exercise):
    """Look up every curated movement in the dataset and calculate its duration."""
    result = []

    for definition in WORKOUT_SET_DEFINITIONS:
        exercises = []
        total_minutes = 0

        for exercise_name in definition["exercise_names"]:
            exercise = dataset["by_name"].get(exercise_name)
            if exercise is None:
                raise ValueError("Workout set exercise is missing from the dataset: " + exercise_name)
            exercises.append(public_exercise(exercise))
            total_minutes += exercise["duration_min"]

        result.append({
            "id": definition["id"],
            "title": definition["title"],
            "tag": definition["tag"],
            "description": definition["description"],
            "level": definition["level"],
            "equipment": definition["equipment"],
            "duration_min": total_minutes,
            "exercises": exercises
        })

    return result
