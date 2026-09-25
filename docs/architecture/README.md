# Architecture

MVP is a FastAPI modular monolith with a transactional relational database, background-worker boundary and public/internal projections. Development defaults to SQLite and deterministic providers; Docker Compose declares PostgreSQL and Redis for integration mode.
