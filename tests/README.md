# FitEZ test notes

Run with:

```bash
python -m unittest discover -s tests -v
python tests/check_edges.py
```

The unit suite checks:

- **Heap:** custom max-heap against a manually written linear-scan reference, including empty and boundary inputs.
- **Graph:** BFS shortest paths, root and unknown targets, plus Kahn cycle detection.
- **Scheduler:** bitmask DP against brute force, time-budget limits and group coverage.
- **Dataset:** 1,066 total records, 869 main/cardio, 65 regular warm-up, 118 regular cool-down and 14 Hip Mobility rows.
- **Beginner bonus:** a mapped exercise gets exactly +1 point for a Beginner profile and no bonus for other levels.
- **Recommendations:** equipment and level filters, profile validation, BMI cutoffs and optional Hip Mobility.
- **Your plan:** warm-up and cool-down records are returned in separate fields and use the matching role from the raw dataset.
- **Quick Routines:** every preset references an existing dataset exercise and displayed durations equal the sum of exercise durations.
- **API:** Flask tests cover metadata, All Exercise filters, standalone Progression, Quick Routines and recommendations. They use fake database functions, so no database is needed for them.
- **Accounts (`test_auth.py`):** route protection and CSRF checks, plus password hashing, login, logout, duplicate accounts and per-user data separation. The database tests run on SQLite, and also on PostgreSQL when `TEST_DATABASE_URL` is set.

The test algorithms do not use `sorted()` or library DSA implementations as the reference for the custom heap.
