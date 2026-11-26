# Data Layer

Contains the exercise CSV, progression edges and Beginner bonus mapping.

- `data/raw/exercises.csv`: the only exercise dataset, read directly by the application.
- `data_loader.py`: normalises source group labels and prepares the in-memory exercise indexes once at startup.

- `user_data.py`: SQLAlchemy models for the `users`, `profiles` and `plans` tables. One schema for SQLite and PostgreSQL.
- `database.py`: engine, sessions and queries for accounts, profiles and saved plans. Missing tables are created automatically.

Exercise data comes from the files; only user data is stored in the database (SQLite locally, PostgreSQL in the cloud). See the root README for setup.
