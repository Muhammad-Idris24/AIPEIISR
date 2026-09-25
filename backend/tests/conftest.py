import os
import sys

HERE = os.path.dirname(__file__)
BACKEND = os.path.dirname(HERE)
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

TEST_DB = os.path.join(BACKEND, "test_aipeiisr.db")
if os.path.exists(TEST_DB):
    try:
        os.remove(TEST_DB)
    except OSError:
        pass

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["WORKER_DISABLED"] = "1"
os.environ["SCHEDULER_DISABLED"] = "1"

import importlib
from app import db as _db_module
importlib.reload(_db_module)
from app.db import Base, engine, init_db

Base.metadata.create_all(engine)
init_db()
