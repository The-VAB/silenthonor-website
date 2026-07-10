"""
One-time migration: add roles[] array to all existing users.
Run on the VPS: python3 /app/backend/migrate_roles.py
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv("/app/.env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "silenthonor")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@silenthonor.org")

async def migrate():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Add roles array to every user that doesn't have it yet
    users = await db.users.find({"roles": {"$exists": False}}).to_list(None)
    print(f"Found {len(users)} users without roles array — migrating...")

    for user in users:
        role = user.get("role", "member")
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"roles": [role]}}
        )

    print(f"  Migrated {len(users)} users")

    # Grant admin+counselor dual-role to the admin account
    result = await db.users.update_one(
        {"email": ADMIN_EMAIL},
        {"$set": {"roles": ["admin", "counselor"]}}
    )
    print(f"  Set {ADMIN_EMAIL} roles=['admin','counselor']: matched={result.matched_count}")

    # Verify
    admin = await db.users.find_one({"email": ADMIN_EMAIL}, {"email": 1, "role": 1, "roles": 1})
    print(f"  Admin record: role={admin.get('role')}  roles={admin.get('roles')}")

    total = await db.users.count_documents({"roles": {"$exists": True}})
    print(f"Migration complete — {total} users now have roles array")

    client.close()

if __name__ == "__main__":
    asyncio.run(migrate())
