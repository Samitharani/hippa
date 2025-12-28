from app.db import users_collection
from app.auth import get_password_hash
from datetime import datetime

users = [

    {
        "username": "doctor",
        "password": "doctor123",
        "role": "doctor"
    },
    {
        "username": "nurse1",
        "password": "nurse123",
        "role": "nurse"
    }
]

for u in users:
    if not users_collection.find_one({"username": u["username"]}):
        users_collection.insert_one({
            "username": u["username"],
            "password": get_password_hash(u["password"]),
            "role": u["role"],
            "created_at": datetime.utcnow()
        })
        print("✅ Inserted:", u["username"])
