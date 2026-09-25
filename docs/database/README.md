# Database

Development schema lives in `backend/app/db.py`. It uses UUID primary keys, timestamps, content-hash uniqueness and restricted evidence. Replace startup `create_all` with Alembic migrations before any shared deployment.
