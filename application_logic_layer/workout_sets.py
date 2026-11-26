"""Small curated workout sets built only from exercises in the supplied CSV."""

WORKOUT_SET_DEFINITIONS = [
    {
        "id": "stretch-reset",
        "title": "10-Minute Stretch Reset",
        "tag": "FLEXIBILITY",
        "description": "Gentle floor stretches and yoga poses (Cat-Cow, Seated Forward Fold, Child's Pose) for your back, hamstrings and hips.",
        "level": "Beginner",
        "equipment": "Body only",
        "exercise_names": ["Cat-Cow", "Seated Forward Fold", "Child's Pose"],
        # Finish with a longer rest pose so the set totals exactly 10 minutes.
        "durations": {"Child's Pose": 4}
    },
    {
        "id": "office-break",
        "title": "10-Minute Office Break",
        "tag": "DESK-FRIENDLY",
        "description": "A short desk break: stretch your neck, shoulders, chest and torso, then walk easily to reset after sitting.",
        "level": "Beginner",
        "equipment": "Body only",
        "exercise_names": [
            "Side Neck Stretch", "Overhead Stretch", "Clasped Hands Chest Opener",
            "Shoulder Stretch", "Slow Walk Recovery"
        ],
        # Two minutes for each movement, so the set totals exactly 10 minutes.
        "durations": {
            "Side Neck Stretch": 2, "Overhead Stretch": 2, "Clasped Hands Chest Opener": 2,
            "Shoulder Stretch": 2, "Slow Walk Recovery": 2
        }
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
            item = dict(public_exercise(exercise))
            item["duration_min"] = definition.get("durations", {}).get(
                exercise_name, exercise["duration_min"]
            )
            exercises.append(item)
            total_minutes += item["duration_min"]

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
