"""FitEZ Flask application and its JSON API."""

import json
import os
import secrets
from datetime import timedelta
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
)

from data_layer import database
from data_layer.data_loader import load_data, load_muscle_images
from application_logic_layer import auth
from application_logic_layer.profile_parser import ALLOWED_GOALS, ALLOWED_EQUIPMENT, LEVELS, parse_profile
from application_logic_layer.recommender import recommend, public_exercise
from application_logic_layer.workout_sets import build_workout_sets
from dsa_core_layer.progression_graph import build_graph, has_cycle, shortest_path

# The project root contains exactly four runtime layers.
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data_layer" / "data"
INTERFACE_DIR = BASE_DIR / "interface_layer"
MUSCLE_IMAGE_DIR = DATA_DIR / "Muscle_Groups_Images"

# Read DATABASE_URL and SECRET_KEY from .env (real environment variables win).
load_dotenv(BASE_DIR / ".env")

# Build the in-memory exercise store once when the API starts.
DATASET = load_data(
    str(DATA_DIR / "raw" / "exercises.csv"),
    str(DATA_DIR / "beginner_exercises.json")
)

MUSCLE_IMAGES = load_muscle_images(MUSCLE_IMAGE_DIR / "muscle_groups_table.csv")

with open(DATA_DIR / "progression_edges.json", encoding="utf-8") as file:
    PROGRESSION_EDGES = json.load(file)

missing_names = []
for edge in PROGRESSION_EDGES:
    for name in edge:
        if name not in DATASET["by_name"] and name not in missing_names:
            missing_names.append(name)
if missing_names:
    raise RuntimeError("Progression graph contains unknown exercise names: " + ", ".join(missing_names))

GRAPH = build_graph(PROGRESSION_EDGES)
if has_cycle(GRAPH):
    raise RuntimeError("Progression graph contains a cycle. Fix data/progression_edges.json before starting.")

app = Flask(
    __name__,
    template_folder=str(INTERFACE_DIR / "templates"),
    static_folder=str(INTERFACE_DIR / "static")
)
app.config["JSON_SORT_KEYS"] = False

# The secret key signs the session cookie, so logged-in users cannot be faked.
def load_secret_key():
    """Use SECRET_KEY if set; for local SQLite, create one and keep it in .secret_key."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    if os.environ.get("DATABASE_URL", "").strip():
        raise RuntimeError("SECRET_KEY is not set. It is required when DATABASE_URL is set.")
    key_file = BASE_DIR / ".secret_key"
    if not key_file.exists() or not key_file.read_text().strip():
        key_file.touch(mode=0o600)
        key_file.write_text(secrets.token_hex(32))
    return key_file.read_text().strip()


app.config.update(
    SECRET_KEY=load_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # Set SESSION_COOKIE_SECURE=true when the site is served over HTTPS.
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7)
)


def catalog_item(exercise):
    """Return the basic information shown on the All Exercise page."""
    return {
        "id": exercise["id"],
        "name": exercise["name"],
        "group": exercise["group"],
        "level": exercise["level"],
        "equipment": exercise["equipment"],
        "category": exercise["category"],
        "primary_muscle": exercise["primary_muscle"],
        "duration_min": exercise["duration_min"],
        "role": exercise["role"],
        "needs_bar": exercise["needs_bar"]
    }


# ---------- Sessions and security ----------

def csrf_token():
    """A random value tied to this session. Forms and API writes must send it back."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def check_csrf_token():
    """Reject writes from other websites, or from a tab left open after an account change."""
    if request.method not in ("POST", "PUT"):
        return None

    sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if expected and secrets.compare_digest(sent.encode(), expected.encode()):
        return None

    if request.path.startswith("/api/"):
        return jsonify({"error": "Your session has changed. Please reload the page."}), 403
    if request.endpoint in ("login", "register"):
        return redirect(url_for(request.endpoint, expired=1))
    return redirect(url_for("home"))


def login_required(view):
    """Only run the view for a logged-in user, who is then available as g.user."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = None
        if "user_id" in session:
            user = database.find_user_by_id(session["user_id"])

        if user is None:
            session.pop("user_id", None)
            if request.path.startswith("/api/"):
                return jsonify({"error": "Please log in to continue."}), 401
            return redirect(url_for("login"))

        g.user = user
        return view(*args, **kwargs)
    return wrapped


def start_session(user_id):
    """Log a user in with a fresh session that survives refreshes and restarts."""
    session.clear()
    session.permanent = True
    session["user_id"] = user_id


@app.after_request
def prevent_caching(response):
    """Stop the Back button showing private pages after logout."""
    if request.endpoint not in ("static", "muscle_image"):
        response.headers["Cache-Control"] = "no-store"
    return response


def database_error(error):
    app.logger.exception("Database error")
    message = "The database is unavailable. Please try again shortly."
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), 503
    return message, 503


for error_type in database.DatabaseError:
    app.register_error_handler(error_type, database_error)


# ---------- Register, log in, log out ----------

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("home"))

    error = None
    username = ""
    email = ""
    if request.method == "POST":
        username = auth.clean_login(request.form.get("username", ""))
        email = auth.clean_login(request.form.get("email", ""))
        password = request.form.get("password", "")
        error = auth.validate_registration(
            username, email, password, request.form.get("confirm_password", "")
        )
        if error is None:
            try:
                user_id = database.create_user(username, email, auth.hash_password(password))
            except database.DuplicateAccountError:
                error = "That username or email is already registered."
            else:
                start_session(user_id)
                return redirect(url_for("home"))
    elif request.args.get("expired"):
        error = "The page expired. Please try again."

    status = 400 if request.method == "POST" else 200
    return render_template("register.html", error=error, username=username, email=email), status


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))

    error = None
    login_name = ""
    status = 200
    if request.method == "POST":
        login_name = auth.clean_login(request.form.get("login", ""))
        password = request.form.get("password", "")
        if not login_name or not password:
            error = "Enter your email or username and your password."
            status = 400
        else:
            user = database.find_user_by_login(login_name)
            # One message for both cases, so it does not reveal which accounts exist.
            if user is None or not auth.password_is_correct(user["password_hash"], password):
                error = "Incorrect email/username or password."
                status = 401
            else:
                start_session(user["id"])
                return redirect(url_for("home"))
    elif request.args.get("expired"):
        error = "The page expired. Please try again."

    return render_template("login.html", error=error, login_name=login_name), status


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Website and API (login required) ----------

@app.get("/")
@login_required
def home():
    return render_template("index.html", user=g.user)


@app.get("/muscle-images/<filename>")
def muscle_image(filename):
    """Serve the muscle group pictures shown on exercise cards."""
    return send_from_directory(MUSCLE_IMAGE_DIR, filename)


@app.get("/api/profile")
@login_required
def get_profile_api():
    """Return the logged-in user's saved profile and latest plan."""
    return jsonify({
        "profile": database.get_profile(g.user["id"]),
        "plan": database.get_plan(g.user["id"])
    })


@app.put("/api/profile")
@login_required
def save_profile_api():
    """Validate and save the logged-in user's profile."""
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Request body must contain valid JSON."}), 400
    try:
        profile = parse_profile(payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    # The user id comes from the session, never from the request.
    database.save_profile(g.user["id"], profile)
    return jsonify({"profile": profile})


@app.get("/api/metadata")
@login_required
def metadata():
    progression_nodes = []
    for name in GRAPH.adjacency_list:
        exercise = DATASET["by_name"][name]
        progression_nodes.append({
            "name": name,
            "equipment": exercise["equipment"],
            "level": exercise["level"],
            "group": exercise["group"]
        })

    return jsonify({
        "goals": ALLOWED_GOALS,
        "equipment": ALLOWED_EQUIPMENT,
        "levels": LEVELS,
        "groups": DATASET["group_names"],
        "main_groups": DATASET["main_group_names"],
        "progression_nodes": progression_nodes,
        "muscle_images": {
            muscle: url_for("muscle_image", filename=filename)
            for muscle, filename in MUSCLE_IMAGES.items()
        },
        "stats": {
            "total": len(DATASET["all_rows"]),
            "main": len(DATASET["main_pool"]),
            "warm_up": len(DATASET["warm_up_pool"]),
            "cool_down": len(DATASET["cool_down_pool"]),
            "hip_mobility": len(DATASET["hip_mobility_pool"]),
            "edges": len(PROGRESSION_EDGES),
            "beginner_bonus_exercises": len(DATASET["beginner_bonus_names"]),
            "beginner_bonus_points": DATASET["beginner_bonus_points"]
        }
    })


@app.get("/api/exercises")
@login_required
def all_exercises():
    """Return every exercise, optionally filtered by group and difficulty."""
    group = request.args.get("group", "all")
    level = request.args.get("level", "all")

    if group != "all" and group not in DATASET["group_names"]:
        return jsonify({"error": "Unknown exercise group."}), 400
    if level != "all" and level not in LEVELS:
        return jsonify({"error": "Unknown exercise level."}), 400

    exercises = []
    for exercise in DATASET["all_rows"]:
        if group != "all" and exercise["group"] != group:
            continue
        if level != "all" and exercise["level"] != level:
            continue
        exercises.append(catalog_item(exercise))

    return jsonify({"count": len(exercises), "exercises": exercises})


@app.get("/api/progression")
@login_required
def progression_api():
    """Find a progression path without requiring a saved user profile."""
    target = request.args.get("target", "").strip()
    if not target:
        return jsonify({"error": "Choose a target exercise first."}), 400
    if target not in GRAPH.adjacency_list:
        return jsonify({"error": "Choose an exercise listed in the progression search."}), 400

    path_names = shortest_path(GRAPH, target)
    path = []
    for name in path_names:
        path.append(public_exercise(DATASET["by_name"][name]))

    return jsonify({
        "target": target,
        "note": "This path is available independently of your Profile. It follows the progression links in the project graph.",
        "path": path
    })


@app.get("/api/workout-sets")
@login_required
def workout_sets_api():
    """Return short, curated routines made from dataset exercises."""
    return jsonify({"sets": build_workout_sets(DATASET, public_exercise)})


@app.post("/api/recommend")
@login_required
def recommendation_api():
    """Generate and save a plan from the logged-in user's stored profile."""
    profile = database.get_profile(g.user["id"])
    if profile is None:
        return jsonify({"error": "Please complete and save your profile first."}), 400

    try:
        result = recommend(profile, DATASET)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception:
        app.logger.exception("Unexpected recommendation error")
        return jsonify({"error": "Something went wrong while generating the plan. Please try again."}), 500

    database.save_plan(g.user["id"], result)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
