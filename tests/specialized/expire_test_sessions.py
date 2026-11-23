"""Simulate expiry only in this runner's fresh slots_test database."""

import os
import sys
import uuid
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
assert "@127.0.0.1:" in url and url.endswith("/slots_test")
value = uuid.UUID(sys.argv[1])
engine = create_engine(url)
with engine.begin() as c:
    changed = c.execute(
        text(
            "UPDATE user_session SET expires_at=CURRENT_TIMESTAMP - interval '1 minute' WHERE user_id=:id"
        ),
        {"id": value},
    ).rowcount
assert changed > 0
engine.dispose()
print("Synthetic sessions expired")
