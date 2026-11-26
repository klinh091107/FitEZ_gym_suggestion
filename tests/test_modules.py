"""Unit and integration tests for FitEZ's DSA algorithms and API."""

import json
import os
import random
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
# The API tests do not need the real secret from .env.
os.environ.setdefault("SECRET_KEY", "test-only-secret")

from dsa_core_layer.structures.max_heap import get_top_k
from dsa_core_layer.exercise_ranker import passes_filters, rank_exercises, score_exercise
from dsa_core_layer.progression_graph import build_graph, has_cycle, shortest_path
from dsa_core_layer.scheduler import solve_daily_knapsack
from data_layer.data_loader import load_data
from application_logic_layer.profile_parser import parse_profile, compute_bmi
from application_logic_layer.recommender import recommend, public_exercise
from application_logic_layer.workout_sets import build_workout_sets
try:
    from interface_layer.web.app import app, DATASET, GRAPH
    FLASK_AVAILABLE = True
except ModuleNotFoundError:
    app = None
    DATASET = load_data(os.path.join(ROOT, "data_layer", "data", "raw", "exercises.csv"), os.path.join(ROOT, "data_layer", "data", "beginner_exercises.json"))
    with open(os.path.join(ROOT, "data_layer", "data", "progression_edges.json"), encoding="utf-8") as file:
        GRAPH_EDGES = json.load(file)
    GRAPH = build_graph(GRAPH_EDGES)
    FLASK_AVAILABLE = False

DATA_PATH = os.path.join(ROOT, "data_layer", "data", "raw", "exercises.csv")
BEGINNER_PATH = os.path.join(ROOT, "data_layer", "data", "beginner_exercises.json")

def select_top_by_linear_scan(items, count):
    """Simple test reference: repeatedly scan for the highest-priority item."""
    remaining = list(items)
    result = []

    # Find and remove the best item until enough results are collected.
    while len(result) < count and len(remaining) > 0:
        best_index = 0
        for index in range(1, len(remaining)):
            key = remaining[index][0]
            best_key = remaining[best_index][0]
            # Higher score and group count win; on a tie, the smaller id wins.
            if key[:2] > best_key[:2] or (key[:2] == best_key[:2] and key[2] < best_key[2]):
                best_index = index
        result.append(remaining[best_index])
        del remaining[best_index]

    return result


class HeapTests(unittest.TestCase):
    def test_heap_matches_linear_scan_reference(self):
        random.seed(10)
        for _ in range(1000):
            values = []
            for index in range(random.randint(0, 60)):
                values.append(((random.randint(0, 20), random.randint(1, 5), index), index))
            count = random.randint(0, 70)
            expected = select_top_by_linear_scan(values, count)
            self.assertEqual(get_top_k(values, count), expected)

    def test_heap_edges(self):
        self.assertEqual(get_top_k([], 5), [])
        self.assertEqual(get_top_k([((1, 1, 1), "a")], 0), [])
        self.assertEqual(get_top_k([((1, 1, 1), "a")], 5), [((1, 1, 1), "a")])
        values = [((4, 1, 1), "a"), ((4, 1, 2), "b"), ((4, 1, 3), "c")]
        self.assertEqual(set(get_top_k(values, 3)), set(values))

class GraphTests(unittest.TestCase):
    def test_project_graph_is_acyclic(self):
        self.assertFalse(has_cycle(GRAPH))

    def test_cycle_is_detected(self):
        self.assertTrue(has_cycle(build_graph([["A", "B"], ["B", "C"], ["C", "A"]])))

    def test_shortest_path_and_edges(self):
        graph = build_graph([["A", "C"], ["A", "B"], ["B", "D"], ["C", "D"], ["D", "E"]])
        self.assertEqual(shortest_path(graph, "A"), ["A"])
        path = shortest_path(graph, "E")
        self.assertEqual(path[0], "A")
        self.assertEqual(path[-1], "E")
        self.assertEqual(len(path), 4)
        self.assertIn(path[1], ("B", "C"))
        self.assertEqual(shortest_path(graph, "missing"), [])
        self.assertEqual(shortest_path(build_graph([["Root", "Leaf"]]), "Root"), ["Root"])

class SchedulerTests(unittest.TestCase):
    def test_greedy_counterexample(self):
        pool = [
            {"score": 10, "units": 3, "bit": 1},
            {"score": 9, "units": 3, "bit": 1},
            {"score": 8, "units": 3, "bit": 1},
            {"score": 1, "units": 1, "bit": 2},
            {"score": 1, "units": 1, "bit": 4}
        ]
        chosen, score, groups_ok = solve_daily_knapsack(pool, 10, 3)
        self.assertEqual(chosen, [0, 1, 3, 4])
        self.assertEqual(score, 21)
        self.assertTrue(groups_ok)

    def test_budget_and_group_coverage_against_bruteforce(self):
        random.seed(14)
        for _ in range(200):
            size = random.randint(1, 12)
            budget = random.randint(2, 12)
            minimum = random.randint(1, 3)
            pool = []
            for index in range(size):
                pool.append({"score": random.randint(1, 12), "units": random.randint(1, 5), "bit": 1 << random.randint(0, 4)})
            chosen, score, groups_ok = solve_daily_knapsack(pool, budget, minimum)
            best_valid = None
            best_any = None
            for mask in range(1 << size):
                used_time = 0
                total_score = 0
                groups = 0
                for index in range(size):
                    if mask & (1 << index):
                        used_time += pool[index]["units"]
                        total_score += pool[index]["score"]
                        groups |= pool[index]["bit"]
                if used_time <= budget:
                    if best_any is None or total_score > best_any:
                        best_any = total_score
                    bits = 0
                    current = groups
                    while current:
                        bits += current & 1
                        current >>= 1
                    if bits >= minimum and (best_valid is None or total_score > best_valid):
                        best_valid = total_score
            expected_ok = best_valid is not None
            expected_score = best_valid if expected_ok else best_any
            self.assertEqual(groups_ok, expected_ok)
            self.assertEqual(score, expected_score)
            actual_time = 0
            for index in chosen:
                actual_time += pool[index]["units"]
            self.assertLessEqual(actual_time, budget)

class DataAndRankerTests(unittest.TestCase):
    def test_data_counts_and_edges(self):
        data = load_data(DATA_PATH, BEGINNER_PATH)
        self.assertEqual(len(data["all_rows"]), 1066)
        self.assertEqual(len(data["main_pool"]), 869)
        self.assertEqual(len(data["warm_up_pool"]), 65)
        self.assertEqual(len(data["cool_down_pool"]), 118)
        self.assertEqual(len(data["hip_mobility_pool"]), 14)
        for exercise in data["warm_up_pool"]:
            self.assertEqual(exercise["role"], "warm up")
        for exercise in data["cool_down_pool"]:
            self.assertEqual(exercise["role"], "cool down")
        for exercise in data["hip_mobility_pool"]:
            self.assertEqual(exercise["group"], "hip_mobility")
        with open(os.path.join(ROOT, "data_layer", "data", "progression_edges.json"), encoding="utf-8") as file:
            edges = json.load(file)
        missing = []
        for edge in edges:
            for name in edge:
                if name not in data["by_name"] and name not in missing:
                    missing.append(name)
        self.assertEqual(missing, [])

    def test_filters_and_profile_ranking(self):
        profile = {"equipment": ["dumbbell"], "has_pullup_bar": False, "level": "beginner", "bmi_class": "Normal",
                   "goals": ["build_muscle"], "focus_muscles": ["Chest"]}
        top = rank_exercises(DATASET["main_pool"], profile, 5)
        self.assertEqual(len(top), 5)
        for score, exercise in top:
            self.assertLessEqual({"beginner": 1, "intermediate": 2, "expert": 3}[exercise["level"]], 1)
            self.assertFalse(exercise["needs_bar"])
            self.assertTrue(exercise["equipment"] in ("body only", "dumbbell"))

    def test_ranker_matches_linear_scan_reference_for_random_profiles(self):
        random.seed(21)
        for _ in range(100):
            level = random.choice(["beginner", "intermediate", "expert"])
            goals = random.sample(["build_muscle", "get_stronger", "lose_weight", "endurance"], random.randint(1, 4))
            equipment = random.sample(["dumbbell", "barbell", "machine", "bands", "cable"], random.randint(0, 5))
            focus = random.sample(["Chest", "Back", "LegsFront", "Core", "Posterior"], random.randint(0, 5))
            profile = {"equipment": equipment, "has_pullup_bar": random.choice([True, False]),
                       "level": level, "bmi_class": random.choice(["Normal", "Overweight", "Obese"]),
                       "goals": goals, "focus_muscles": focus}
            items = []
            for exercise in DATASET["main_pool"]:
                if passes_filters(exercise, profile):
                    from dsa_core_layer.exercise_ranker import score_exercise
                    score = score_exercise(exercise, profile, DATASET["beginner_bonus_names"])
                    key = (score, exercise["n_groups"], exercise["id"])
                    items.append((key, exercise))
            expected = select_top_by_linear_scan(items, 7)
            actual = rank_exercises(DATASET["main_pool"], profile, 7, DATASET["beginner_bonus_names"])
            expected_pairs = [(item[0][0], item[1]["id"]) for item in expected]
            actual_pairs = [(score, exercise["id"]) for score, exercise in actual]
            self.assertEqual(actual_pairs, expected_pairs)

    def test_beginner_exercise_gets_one_bonus_point(self):
        exercise = DATASET["by_name"]["Knee Push-Up"]
        profile = {"level": "beginner", "goals": [], "focus_muscles": []}
        base_score = score_exercise(exercise, profile, set())
        bonus_score = score_exercise(exercise, profile, DATASET["beginner_bonus_names"])
        self.assertEqual(bonus_score, base_score + 1)

    def test_beginner_bonus_is_not_given_to_other_levels(self):
        exercise = DATASET["by_name"]["Knee Push-Up"]
        profile = {"level": "intermediate", "goals": [], "focus_muscles": []}
        base_score = score_exercise(exercise, profile, set())
        with_bonus_list = score_exercise(exercise, profile, DATASET["beginner_bonus_names"])
        self.assertEqual(with_bonus_list, base_score)

class ParserTests(unittest.TestCase):
    def valid_payload(self):
        return {"height_cm": 165, "weight_kg": 65, "age": 22, "bmi_standard": "asian",
                "session_min": 45, "sessions_per_day": 1, "days_per_week": 3,
                "level": "beginner", "goals": ["build_muscle"], "equipment": ["dumbbell"],
                "focus_muscles": [], "has_pullup_bar": False, "include_stretch": True,
                "include_hip_mobility": False}

    def test_bmi_boundaries(self):
        self.assertEqual(compute_bmi(100, 18.5, "asian"), (18.5, "Normal"))
        self.assertEqual(compute_bmi(100, 23, "asian"), (23.0, "Overweight"))
        self.assertEqual(compute_bmi(100, 25, "asian"), (25.0, "Obese"))
        self.assertEqual(compute_bmi(100, 23, "european"), (23.0, "Normal"))
        self.assertEqual(compute_bmi(100, 24.9, "european"), (24.9, "Normal"))
        self.assertEqual(compute_bmi(100, 25, "european"), (25.0, "Overweight"))
        self.assertEqual(compute_bmi(100, 30, "european"), (30.0, "Obese"))

    def test_invalid_profiles(self):
        base = self.valid_payload()
        invalid_payloads = []
        item = dict(base); item.pop("age"); invalid_payloads.append(item)
        item = dict(base); item["height_cm"] = 119; invalid_payloads.append(item)
        item = dict(base); item["height_cm"] = 231; invalid_payloads.append(item)
        item = dict(base); item["weight_kg"] = 29; invalid_payloads.append(item)
        item = dict(base); item["weight_kg"] = 181; invalid_payloads.append(item)
        item = dict(base); item["weight_kg"] = "65"; invalid_payloads.append(item)
        item = dict(base); item["age"] = 15; invalid_payloads.append(item)
        item = dict(base); item["age"] = 61; invalid_payloads.append(item)
        item = dict(base); item["bmi_standard"] = "unknown"; invalid_payloads.append(item)
        item = dict(base); item["level"] = "rookie"; invalid_payloads.append(item)
        item = dict(base); item["goals"] = []; invalid_payloads.append(item)
        item = dict(base); item["goals"] = ["unknown"]; invalid_payloads.append(item)
        item = dict(base); item["equipment"] = "dumbbell"; invalid_payloads.append(item)
        item = dict(base); item["session_min"] = 4; invalid_payloads.append(item)
        item = dict(base); item["session_min"] = 30.5; invalid_payloads.append(item)
        item = dict(base); item["days_per_week"] = 7; invalid_payloads.append(item)
        item = dict(base); item["has_pullup_bar"] = "false"; invalid_payloads.append(item)
        for payload in invalid_payloads:
            with self.assertRaises(ValueError):
                parse_profile(payload)

class RecommenderTests(unittest.TestCase):
    def test_end_to_end_recommendation_payload(self):
        payload = {"height_cm": 165, "weight_kg": 65, "age": 22, "level": "beginner",
                   "goals": ["lose_weight"], "equipment": ["dumbbell", "machine"],
                   "focus_muscles": [], "session_min": 45, "sessions_per_day": 1,
                   "days_per_week": 3, "has_pullup_bar": False, "include_stretch": True}
        result = recommend(payload, DATASET)
        self.assertEqual(len(result["top_k"]), 5)
        self.assertEqual(len(result["schedule"]), 3)
        self.assertEqual(result["profile"]["bmi_class"], "Overweight")
        for day in result["schedule"]:
            self.assertLessEqual(day["main_minutes"], 45)
            self.assertEqual(len(day["warm_up"]), 1)
            self.assertEqual(len(day["cool_down"]), 1)

    def test_suggestions_fit_the_available_minutes(self):
        for minutes in (5, 10, 15, 20, 45, 120):
            payload = ParserTests().valid_payload()
            payload["session_min"] = minutes
            payload["include_hip_mobility"] = minutes > 10
            result = recommend(payload, DATASET)
            self.assertTrue(result["top_k"])
            for picks in [result["top_k"]] + list(result["by_group"].values()):
                self.assertLessEqual(sum(item["duration_min"] for item in picks), minutes)
            today_hip = [item for item in result["top_k"] if item["group"] == "hip_mobility"]
            self.assertEqual(len(today_hip), 2 if minutes > 10 else 0)
            self.assertLessEqual(len(result["top_k"]) - len(today_hip), 5)
            for day in result["schedule"]:
                self.assertTrue(day["exercises"])
                hip_minutes = sum(item["duration_min"] for item in day["hip_mobility"])
                self.assertEqual(day["total_minutes"], day["main_minutes"] + hip_minutes)
                self.assertLessEqual(day["total_minutes"], minutes)
                # Support moves are suggested separately, even on very short days.
                self.assertEqual(len(day["warm_up"]), 1)
                self.assertEqual(len(day["cool_down"]), 1)
                self.assertEqual(len(day["hip_mobility"]), 2 if minutes > 10 else 0)

    def test_hip_mobility_is_optional_and_comes_from_its_group(self):
        payload = ParserTests().valid_payload()
        payload["include_stretch"] = False
        payload["include_hip_mobility"] = True
        result = recommend(payload, DATASET)
        used_names = []
        for day in result["schedule"]:
            self.assertEqual(day["day"], "Day " + str(result["schedule"].index(day) + 1))
            self.assertEqual(len(day["hip_mobility"]), 2)
            for exercise in day["hip_mobility"]:
                self.assertEqual(exercise["group"], "hip_mobility")
                used_names.append(exercise["name"])
            self.assertEqual(day["warm_up"], [])
            self.assertEqual(day["cool_down"], [])
        self.assertEqual(len(used_names), len(set(used_names)))

    def test_hip_mobility_is_not_added_when_not_selected(self):
        payload = ParserTests().valid_payload()
        payload["include_hip_mobility"] = False
        result = recommend(payload, DATASET)
        for day in result["schedule"]:
            self.assertEqual(day["hip_mobility"], [])

    def test_progression_graph_can_find_a_path_without_a_profile(self):
        path = shortest_path(GRAPH, "Bodyweight Squat")
        self.assertTrue(path)
        self.assertEqual(path[-1], "Bodyweight Squat")

    def test_workout_sets_use_dataset_exercises_and_exact_durations(self):
        routines = build_workout_sets(DATASET, public_exercise)
        self.assertEqual(len(routines), 3)
        for routine in routines:
            total = 0
            for exercise in routine["exercises"]:
                self.assertIn(exercise["name"], DATASET["by_name"])
                total += exercise["duration_min"]
            self.assertEqual(routine["duration_min"], total)
            self.assertEqual(routine["duration_min"], 10)

    def test_schedule_keeps_warm_up_and_cool_down_separate(self):
        payload = ParserTests().valid_payload()
        payload["include_stretch"] = True
        result = recommend(payload, DATASET)
        for day in result["schedule"]:
            self.assertEqual(len(day["warm_up"]), 1)
            self.assertEqual(len(day["cool_down"]), 1)
            self.assertEqual(day["warm_up"][0]["role"], "warm up")
            self.assertEqual(day["cool_down"][0]["role"], "cool down")

    def test_stretch_toggle_does_not_change_main_selection(self):
        payload = {"height_cm": 165, "weight_kg": 65, "age": 22, "level": "beginner",
                   "goals": ["build_muscle"], "equipment": ["dumbbell", "machine"],
                   "focus_muscles": [], "session_min": 45, "sessions_per_day": 1,
                   "days_per_week": 2, "has_pullup_bar": False, "include_stretch": True}
        with_stretch = recommend(payload, DATASET)
        payload["include_stretch"] = False
        without_stretch = recommend(payload, DATASET)
        for first, second in zip(with_stretch["schedule"], without_stretch["schedule"]):
            self.assertEqual([item["id"] for item in first["exercises"]],
                             [item["id"] for item in second["exercises"]])
            self.assertEqual(second["warm_up"], [])
            self.assertEqual(second["cool_down"], [])

@unittest.skipUnless(FLASK_AVAILABLE, "Install Flask to run API integration tests.")
class ApiTests(unittest.TestCase):
    def setUp(self):
        # These tests check the recommendation API, so the database is replaced with fakes.
        user = {"id": 1, "username": "tester", "email": "tester@example.com"}
        patcher = mock.patch.multiple(
            "data_layer.database",
            find_user_by_id=mock.DEFAULT, get_profile=mock.DEFAULT, save_plan=mock.DEFAULT
        )
        self.database = patcher.start()
        self.addCleanup(patcher.stop)
        self.database["find_user_by_id"].return_value = user
        self.client = app.test_client()
        with self.client.session_transaction() as test_session:
            test_session["user_id"] = user["id"]
            test_session["csrf_token"] = "test-token"

    def test_metadata(self):
        response = self.client.get("/api/metadata")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["stats"]["total"], 1066)
        self.assertGreater(response.get_json()["stats"]["beginner_bonus_exercises"], 0)
        self.assertEqual(response.get_json()["stats"]["warm_up"], 65)
        self.assertEqual(response.get_json()["stats"]["cool_down"], 118)
        self.assertEqual(response.get_json()["stats"]["hip_mobility"], 14)
        self.assertIn("hip_mobility", response.get_json()["groups"])

    def test_all_exercise_api_filters(self):
        all_response = self.client.get("/api/exercises")
        self.assertEqual(all_response.status_code, 200)
        self.assertEqual(all_response.get_json()["count"], 1066)
        hip_response = self.client.get("/api/exercises?group=hip_mobility&level=beginner")
        self.assertEqual(hip_response.status_code, 200)
        for exercise in hip_response.get_json()["exercises"]:
            self.assertEqual(exercise["group"], "hip_mobility")
            self.assertEqual(exercise["level"], "beginner")

    def test_progression_api_does_not_require_a_profile(self):
        response = self.client.get("/api/progression?target=Bodyweight%20Squat")
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["path"][-1]["name"], "Bodyweight Squat")

    def test_workout_sets_api(self):
        response = self.client.get("/api/workout-sets")
        self.assertEqual(response.status_code, 200)
        routines = response.get_json()["sets"]
        self.assertEqual(len(routines), 3)
        for routine in routines:
            self.assertEqual(routine["duration_min"], 10)

    def test_recommendation_and_bad_request(self):
        headers = {"X-CSRF-Token": "test-token"}
        self.database["get_profile"].return_value = ParserTests().valid_payload()
        response = self.client.post("/api/recommend", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.database["save_plan"].assert_called_once_with(1, response.get_json())
        self.assertIn("top_k", response.get_json())
        self.assertIn("schedule", response.get_json())
        self.assertEqual(response.get_json()["schedule"][0]["day"], "Day 1")
        self.database["get_profile"].return_value = None
        missing = self.client.post("/api/recommend", headers=headers)
        self.assertEqual(missing.status_code, 400)

if __name__ == "__main__":
    unittest.main(verbosity=2)
