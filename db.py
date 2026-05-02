import os
from pymongo import MongoClient

_client = None
_db = None

def init_db(app):
    global _client, _db
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri or "xxxxx" in mongo_uri:
        print("\n" + "!"*50)
        print("שגיאה: לא הגדרת כתובת MongoDB תקינה בקובץ .env")
        print("!"*50 + "\n")
    else:
        # הדפסת בדיקה (מסתירה את הסיסמה)
        masked_uri = mongo_uri.split("@")[-1]
        print(f"DEBUG: Connecting to MongoDB Cluster: {masked_uri}")

    _client = MongoClient(mongo_uri)
    _db = _client["pro"]
    app.config["DB"] = _db

def get_collection(name):
    global _db
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db(app) first.")
    return _db[name]

def setup_indexes():
    """מגדיר אינדקסים ייחודיים ואינדקסים נוספים לקולקציות."""
    pro_collection = get_collection("pro")
    # אינדקס ייחודי על שדה ה-title, תוך התעלמות מאותיות קטנות/גדולות
    # זה ימנע הוספה של משחקים עם אותו שם בדיוק (ללא תלות באותיות קטנות/גדולות)
    pro_collection.create_index([("title", 1)], unique=True, collation={"locale": "en", "strength": 2})

    # אינדקס TTL לקולקציית המטמון - רשומות יימחקו אוטומטית לאחר 24 שעות (86400 שניות)
    get_collection("cache").create_index("created_at", expireAfterSeconds=86400)