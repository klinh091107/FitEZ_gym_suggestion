# FitEZ — four-layer architecture

FitEZ is a Flask workout recommendation website for the COMP50065 DSA project. Its source folders are organized into the **same four architecture layers** as `system_design.drawio`:

1. Interface Layer
2. Application / Logic Layer
3. DSA Core Layer
4. Data Layer

The `tests/` directory is offline evaluation support, not a fifth runtime layer. Benchmark and baseline folders are intentionally omitted because the project scope was changed to remove Benchmark.

## Project structure

```text
FitEZ/
├── interface_layer/                 # 1. INTERFACE LAYER
│   ├── templates/
│   │   ├── index.html                # Web Page (UI)
│   │   ├── login.html                # Login page
│   │   └── register.html             # Create account page
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/app.js
│   └── web/
│       ├── __init__.py
│       └── app.py                    # API Gateway (Flask)
│
├── application_logic_layer/         # 2. APPLICATION / LOGIC LAYER
│   ├── auth.py                       # Account validation & password hashing
│   ├── profile_parser.py             # Profile Service
│   ├── recommender.py                 # Recommendation Controller
│   └── workout_sets.py                # Quick Routines logic
│
├── dsa_core_layer/                   # 3. DSA CORE LAYER
│   ├── progression_graph.py           # Progression Planner
│   ├── exercise_ranker.py             # Exercise Ranker
│   ├── scheduler.py                   # Weekly Scheduler
│   └── structures/
│       ├── graph.py                   # Custom adjacency-list Graph
│       └── max_heap.py                # Custom Max Heap
│
├── data_layer/                       # 4. DATA LAYER
│   ├── data_loader.py                 # Data Loader & Enrichment
│   ├── user_data.py                 # Tables (SQLAlchemy models)
│   ├── database.py                    # Engine, sessions and queries (SQLite / PostgreSQL)
│   └── data/
│       ├── raw/exercises.csv          # Exercise dataset
│       ├── progression_edges.json     # Progression edges
│       └── beginner_exercises.json    # Beginner +1-point mapping
│
├── tests/                             # Offline tests (not a runtime layer)
│   ├── check_edges.py
│   ├── test_auth.py
│   └── test_modules.py
├── .env.example
├── requirements.txt
└── README.md
```

## How the four layers connect

- **Interface → Application / Logic:** `web/app.py` receives browser requests, validates the request shape, calls the profile/recommendation services and returns JSON.
- **Application / Logic → DSA Core:** `recommender.py` uses the ranker, progression planner and weekly scheduler.
- **DSA Core → Data:** algorithms receive in-memory lists, dictionaries, indexes and progression edges prepared by the Data Layer.
- **Data Layer:** `data_loader.py` loads the exercise CSV and the JSON mapping files once at application startup, derives fields and builds `by_name`, muscle-group indexes and the other in-memory pools. A database (`user_data.py` defines the tables, `database.py` runs the queries with SQLAlchemy: SQLite locally, PostgreSQL in the cloud) stores accounts, profiles and saved plans; the exercise data stays in the files.

## Features

- **Profile:** height, weight, age, BMI standard, level, goals, equipment and weekly availability.
- **Today Exercise:** press Discover to generate recommendations.
- **All Exercise:** browse and filter by muscle group and level.
- **Quick Routines:** three short routines sourced from the dataset.
- **Progression:** BFS path finder works without a saved profile (login is still required).
- **Exercise time:** muscle training counts 3 sets (1 min each) with 1 min rest between sets, 5 min in total. Suggestions also count 2 min rest between exercises. Quick Routines have no rest.
- **Your plan:** main exercises and optional Hip Mobility within the session time, plus separate warm-up (3 moves, most trained muscle groups first) and cool-down suggestions.
- **Accounts:** register, log in with email or username, and log out. Every page and API requires login.
- Each user's profile, preferences and latest plan are stored in the database and reloaded at login. Saving a changed profile clears the old plan.

## Dataset

The Data Layer reads `data/raw/exercises.csv` directly at startup: 1,066 exercises.

| Pool | Count |
|---|---:|
| Main exercises + cardio | 869 |
| Warm-up | 65 |
| Cool-down | 118 |
| Hip Mobility | 14 |
| **Total** | **1,066** |

The dataset and edge files are located inside `data_layer/data/`.

## Beginner bonus

The Beginner list contains 139 source entries. Against this CSV, 107 unique exercise names match exactly; 17 unmatched names are retained for reference and do not receive a bonus. A matched exercise receives **+1 score only when the selected profile level is Beginner**. Intermediate and Expert profiles receive no bonus. Uncertain matches are not awarded a point.

## Run locally (macOS / Linux)

Local development uses **SQLite**, so no database server is needed. You need Python 3.10+. Run these commands from the `FitEZ/` project root.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No configuration is needed locally: on first start the app creates its own secret key in the file `.secret_key`. Then start the app:

```bash
python -m flask --app interface_layer.web.app run --debug
```

Open <http://127.0.0.1:5000>, choose **Create an account**, then save your profile and press **Discover**. The file `fitez.db` and its tables are created automatically. Delete that file to reset all local data.

## Cloud database (PostgreSQL)

1. Create a PostgreSQL database with your cloud provider.
2. Set these environment variables in the hosting settings:

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | `postgresql://USER:PASSWORD@HOST:5432/DATABASE`, as given by the provider (often with `?sslmode=require`). Percent-encode special characters in the password (for example `@` becomes `%40`). |
| `SECRET_KEY` | A long random value, different from your local one. |
| `SESSION_COOKIE_SECURE` | `true` (the site must use HTTPS). |

3. Create the tables once, with the same `DATABASE_URL`:

```bash
python -m data_layer.database
```

**Always set `DATABASE_URL` in the cloud.** If it is empty the app uses SQLite, and many hosts erase local files on restart. Local SQLite data is not copied to PostgreSQL.

The `flask run` command above is a development server. Use your host's production WSGI server when deploying. `.env` and `*.db` files are listed in `.gitignore`; never commit them.

## Login and security

- Passwords are stored only as salted hashes (Werkzeug).
- The login session is a signed, HTTP-only cookie that lasts 7 days and is renewed while you use the site.
- Forms and API writes are protected with a CSRF token.
- The user id always comes from the session, so a user can only read and change their own data.
- Not included: password reset, email verification and login rate limiting. Add rate limiting and HTTPS before putting the site on the internet.

## Run tests

```bash
python -m unittest discover -s tests -v
python tests/check_edges.py
```

The database tests run on a temporary SQLite file. To run them on PostgreSQL as well, create a separate database (`createdb fitez_test`) and set `TEST_DATABASE_URL=postgresql:///fitez_test` in `.env`. The tests remove the users they create.

The tests cover normal, edge and invalid inputs. Test references are kept outside the runtime algorithm implementations. No Benchmark or Baselines module is included.

## Algorithms

- **Max Heap:** custom implementation in `dsa_core_layer/structures/max_heap.py`.
- **Progression:** custom adjacency-list Graph in `structures/graph.py`, plus BFS and Kahn's cycle check in `progression_graph.py`.
- **Exercise ranking:** filters and weighted score in `exercise_ranker.py`, then custom Max Heap for top K.
- **Weekly schedule:** 0/1 knapsack with bitmask DP in `scheduler.py`.

The core algorithms are written using basic loops, conditions, lists, dictionaries and sets. They do not use `heapq`, `networkx`, `deque`, `sorted()` or `.sort()` to perform the core operations.
