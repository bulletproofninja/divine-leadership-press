import json
import os
from pathlib import Path
import secrets
import sys
import uuid
from datetime import timedelta

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')
load_dotenv('/app/backend/.env.local', override=True)

if '/app/backend' not in sys.path:
    sys.path.append('/app/backend')

from auth_security import hash_reset_token, utc_now


def main():
    base_url = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
    api = f"{base_url}/api"
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']

    email = f"TEST_ui_reset_{uuid.uuid4().hex[:8]}@example.com"
    password = "UiResetSeed4!"
    response = requests.post(
        f"{api}/auth/register",
        json={"email": email, "name": "UI Reset Seed", "password": password},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    user_id = payload['user']['id']

    raw_token = secrets.token_urlsafe(48)
    now = utc_now()

    with MongoClient(mongo_url) as client:
        db = client[db_name]
        db.password_reset_tokens.insert_one(
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "token_hash": hash_reset_token(raw_token),
                "created_at": now,
                "expires_at": now + timedelta(minutes=30),
                "used_at": None,
            }
        )

    output = Path('/tmp/iter21_reset_seed.json')
    output.write_text(json.dumps({"email": email, "old_password": password, "reset_token": raw_token}))
    output.chmod(0o600)
    print(str(output))


if __name__ == "__main__":
    main()
