"""Validate every progression edge against the exercise CSV."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_layer.data_loader import load_data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = load_data(os.path.join(ROOT, "data_layer", "data", "raw", "exercises.csv"), os.path.join(ROOT, "data_layer", "data", "beginner_exercises.json"))
with open(os.path.join(ROOT, "data_layer", "data", "progression_edges.json"), encoding="utf-8") as file:
    edges = json.load(file)
missing = []
for edge in edges:
    for name in edge:
        if name not in data["by_name"] and name not in missing:
            missing.append(name)
print("missing:", len(missing))
if missing:
    print("\n".join(missing))
    raise SystemExit(1)
print("0 missing")
