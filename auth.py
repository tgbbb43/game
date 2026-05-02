from flask import Blueprint, request, jsonify, session
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_collection
from werkzeug.exceptions import BadRequest, Conflict, NotFound
from datetime import datetime

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role = "user" # הרשמה רגילה מהממשק תמיד יוצרת משתמש רגיל

    if not username or not password:
        raise BadRequest("Username and password are required")

    col = get_collection("users")
    if col.find_one({"username": username}):
        raise Conflict("Username already exists")

    hashed_password = generate_password_hash(password)
    col.insert_one({
        "username": username,
        "password": hashed_password,
        "role": role,
        "is_blocked": False
    })

    return jsonify({"success": True, "message": "User created successfully"}), 201

@auth_bp.route("/admin/create-critic", methods=["POST"])
def create_critic():
    """נתיב מאובטח המאפשר רק למבקר או מנהל ליצור מבקרים חדשים"""
    if "user" not in session or session["user"]["role"] not in ["developer", "critic"]:
        raise BadRequest("Unauthorized: Only critics or developers can create critics")

    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        raise BadRequest("Username and password are required")

    col = get_collection("users")
    if col.find_one({"username": username}):
        raise Conflict("Username already exists")

    hashed_password = generate_password_hash(password)
    col.insert_one({
        "username": username,
        "password": hashed_password,
        "role": "critic",
        "is_blocked": False
    })

    return jsonify({"success": True, "message": "Critic account created successfully"}), 201

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    col = get_collection("users")
    user = col.find_one({"username": username})

    if not user or not check_password_hash(user["password"], password):
        raise BadRequest("Invalid username or password")

    if user.get("is_blocked"):
        raise BadRequest("החשבון שלך חסום. פנה למנהל המערכת.")

    session["user"] = {"username": username, "role": user.get("role", "user")}
    return jsonify({"success": True, "user": session["user"]})

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    return jsonify({"success": True})

@auth_bp.route("/me", methods=["GET"])
def get_me():
    """מחזיר את פרטי המשתמש המחובר כרגע"""
    if "user" in session:
        return jsonify({"logged_in": True, "user": session["user"]})
    return jsonify({"logged_in": False})

@auth_bp.route("/users", methods=["GET"])
def get_all_users():
    """רשימת משתמשים - רק למנהלים"""
    if "user" not in session or session["user"]["role"] not in ["developer", "critic"]:
        raise BadRequest("Unauthorized")
    
    col = get_collection("users")
    users = list(col.find({}, {"password": 0})) # לא מחזירים סיסמאות
    for u in users:
        u["_id"] = str(u["_id"])
    return jsonify(users)

@auth_bp.route("/users/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    """מחיקת משתמש - רק למנהלים"""
    if "user" not in session or session["user"]["role"] not in ["developer", "critic"]:
        raise BadRequest("Unauthorized")
    
    col = get_collection("users")
    col.delete_one({"_id": ObjectId(user_id)})
    return jsonify({"success": True})

@auth_bp.route("/users/<user_id>/block", methods=["PATCH"])
def block_user(user_id):
    """חסימה או ביטול חסימה של משתמש"""
    if "user" not in session or session["user"]["role"] not in ["developer", "critic"]:
        raise BadRequest("Unauthorized")
    
    col = get_collection("users")
    user = col.find_one({"_id": ObjectId(user_id)})
    if not user: raise BadRequest("User not found")
    
    new_status = not user.get("is_blocked", False)
    col.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_blocked": new_status}})
    return jsonify({"success": True, "is_blocked": new_status})

@auth_bp.route("/profile/<target_username>/follow", methods=["POST"])
def toggle_follow(target_username):
    """הוספה או הסרה של עוקב"""
    if "user" not in session:
        raise BadRequest("עליך להיות מחובר כדי לעקוב")
    
    current_username = session["user"]["username"]
    if current_username == target_username:
        raise BadRequest("אתה לא יכול לעקוב אחרי עצמך")
        
    col = get_collection("users")
    target_user = col.find_one({"username": target_username})
    if not target_user:
        raise NotFound("משתמש לא נמצא")
        
    # בדיקה אם המשתמש כבר עוקב
    followers = target_user.get("followers", [])
    is_following = current_username in followers
    
    if is_following:
        # הסרת עקיבה
        col.update_one({"username": target_username}, {"$pull": {"followers": current_username}})
        col.update_one({"username": current_username}, {"$pull": {"following": target_username}})
    else:
        # הוספת עקיבה
        col.update_one({"username": target_username}, {"$push": {"followers": current_username}})
        col.update_one({"username": current_username}, {"$push": {"following": target_username}})
        
        # יצירת התראה למשתמש שקיבל עוקב חדש
        get_collection("notifications").insert_one({
            "to_user": target_username,
            "from_user": current_username,
            "type": "follow",
            "message": f"התחיל לעקוב אחריך!",
            "read": False,
            "created_at": datetime.utcnow()
        })
        
    return jsonify({"success": True, "is_following": not is_following})

@auth_bp.route("/notifications", methods=["GET"])
def get_notifications():
    """שליפת התראות למשתמש המחובר"""
    if "user" not in session:
        return jsonify([])
    
    col = get_collection("notifications")
    notifs = list(col.find({"to_user": session["user"]["username"]}).sort("created_at", -1).limit(10))
    for n in notifs:
        n["_id"] = str(n["_id"])
    
    # סימון כנקרא לאחר השליפה (אופציונלי, תלוי בעיצוב)
    col.update_many({"to_user": session["user"]["username"], "read": False}, {"$set": {"read": True}})
    
    return jsonify(notifs)