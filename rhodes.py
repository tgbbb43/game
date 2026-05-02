import requests
import os
from google import genai
import re
import time
from flask import request, jsonify, Blueprint, session, render_template
from bson import ObjectId
from urllib.parse import quote
from werkzeug.exceptions import NotFound, BadRequest, Conflict, UnprocessableEntity
from db import get_collection
from methods import validate_game_data
from datetime import datetime, timezone

game_bp = Blueprint("game", __name__)

class GameApiService:
    """מחלקה המרכזת את כל הפניות ל-APIs חיצוניים"""
    
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.rawg_key = os.getenv("RAWG_API_KEY")
        self.steam_header = {'User-Agent': 'EliProGameManager/1.0'}
        self.client = None

        if self.gemini_key and not self.gemini_key.startswith("YOUR_"):
            # שימוש בגרסה v1 היציבה למניעת שגיאות 404 שמופיעות לעיתים בגרסאות בטא
            self.client = genai.Client(api_key=self.gemini_key, http_options={'api_version': 'v1'})

    def _get_cached(self, key):
        """שליפת נתון מהמטמון ב-DB"""
        col = get_collection("cache")
        entry = col.find_one({"key": key})
        return entry["data"] if entry else None

    def _set_cached(self, key, data):
        """שמירת נתון במטמון עם חותמת זמן"""
        col = get_collection("cache")
        col.update_one(
            {"key": key},
            {"$set": {"data": data, "created_at": datetime.now(timezone.utc)}},
            upsert=True
        )

    def fetch_ai_description(self, title):
        """מייצר תיאור למשחק באמצעות Gemini"""
        cache_key = f"ai_desc_{title.lower()}"
        cached = self._get_cached(cache_key)
        if cached: return cached

        if not self.client: return None
        try:
            # זיהוי דינמי של המודל הראשון שזמין בחשבון שלך
            # הוספת בדיקה שהמאפיין קיים למניעת קריסות (AttributeError)
            models = list(self.client.models.list())
            available_models = [m.name for m in models if hasattr(m, 'supported_actions') and 'generateContent' in m.supported_actions]
            if not available_models: return None
            
            # חילוץ מזהי המודלים (IDs) ובחירת המודל הטוב ביותר הזמין
            model_ids = [name.split('/')[-1] for name in available_models]
            selected = 'gemini-1.5-flash' if 'gemini-1.5-flash' in model_ids else model_ids[0]
            
            prompt = f"כתוב תיאור קצר מאוד (עד 2 משפטים) בעברית למשחק '{title}'."
            response = self.client.models.generate_content(model=selected, contents=prompt)

            if response and response.text:
                res_text = response.text.strip()
                self._set_cached(cache_key, res_text)
                return res_text
        except Exception as e:
            print(f"DEBUG: Gemini Error: {e}")
        return None

    def fetch_game_image(self, title):
        """מחפש תמונת משחק ב-Steam או RAWG"""
        cache_key = f"img_{title.lower()}"
        cached = self._get_cached(cache_key)
        if cached: return cached

        # ניסיון ב-Steam
        try:
            url = f"https://store.steampowered.com/api/storesearch/?term={quote(title)}&l=english&cc=US"
            res = requests.get(url, headers=self.steam_header, timeout=5)
            if res.status_code == 200:
                items = res.json().get('items', [])
                if items: 
                    img_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{items[0]['id']}/header.jpg"
                    self._set_cached(cache_key, img_url)
                    return img_url
        except: pass

        # ניסיון ב-RAWG
        if self.rawg_key:
            try:
                url = f"https://api.rawg.io/api/games?search={quote(title)}&key={self.rawg_key}&page_size=1"
                res = requests.get(url, headers=self.steam_header, timeout=5)
                if res.status_code == 200:
                    results = res.json().get('results', [])
                    if results:
                        img_url = results[0].get('background_image')
                        self._set_cached(cache_key, img_url)
                        return img_url
            except: pass

        return f"https://placehold.co/600x400?text={quote(title)}"

    def search_external(self, query, platform=None):
        """מחפש משחקים ב-Steam וב-RAWG"""
        cache_key = f"search_{query.lower()}_{platform}"
        cached = self._get_cached(cache_key)
        if cached: return cached

        results, seen = [], set()
        
        # Steam
        if not platform or platform == "4":
            try:
                url = f"https://store.steampowered.com/api/storesearch/?term={quote(query)}&l=english&cc=US"
                res = requests.get(url, headers=self.steam_header, timeout=5)
                for item in res.json().get('items', []):
                    name = item['name']
                    if name.lower() not in seen:
                        results.append({"id": item['id'], "name": name, "source": "Steam", "img": f"https://cdn.akamai.steamstatic.com/steam/apps/{item['id']}/header.jpg"})
                        seen.add(name.lower())
            except: pass

        # RAWG
        if self.rawg_key:
            try:
                url = f"https://api.rawg.io/api/games?search={quote(query)}&key={self.rawg_key}&page_size=5"
                if platform: url += f"&platforms={platform}"
                res = requests.get(url, headers=self.steam_header, timeout=5)
                for item in res.json().get('results', []):
                    name = item['name']
                    if name.lower() not in seen:
                        results.append({"id": item['id'], "name": name, "source": "RAWG", "img": item.get('background_image'), "released": item.get('released')})
                        seen.add(name.lower())
            except: pass
        
        if results: self._set_cached(cache_key, results)
        return results

# אתחול שירות ה-API
api_service = GameApiService()

def get_youtube_embed_url(url):
    """מחלץ מזהה וידאו מיוטיוב והופך אותו לקישור הטמעה"""
    if not url: return None
    regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(regex, url)
    return f"https://www.youtube.com/embed/{match.group(1)}" if match else None

@game_bp.route("/game/search", methods=["GET"])
def search_steam_games():
    """מחפש רשימת משחקים ב-Steam וב-RAWG"""
    query = request.args.get("q", "")
    platform = request.args.get("platform", "")
    if not query: return jsonify([])

    results = api_service.search_external(query, platform)
    return jsonify(results)


@game_bp.route("/game", methods=["GET"])
def get_games():
    col = get_collection("pro")
    # מיון לפי תאריך יציאה בסדר יורד
    all_games = list(col.find().sort("release_date", -1))
    for game in all_games:
        game["_id"] = str(game["_id"])
    return jsonify(all_games)

@game_bp.route("/game/<game_id>/generate-description", methods=["POST"])
def generate_game_description(game_id):
    """נתיב המאפשר לייצר תיאור AI למשחק קיים"""
    # בדיקת הרשאה: רק מבקרים ומפתחים יכולים לייצר תיאור AI
    if "user" not in session or session["user"]["role"] not in ["developer", "critic"]:
        raise BadRequest("אין לך הרשאה לביצוע פעולה זו.")

    col = get_collection("pro")
    game = col.find_one({"_id": ObjectId(game_id)})
    if not game: raise NotFound("Game not found")
    
    new_desc = api_service.fetch_ai_description(game["title"])
    if not new_desc:
        raise UnprocessableEntity("ה-AI לא הצליח לייצר תיאור. בדוק את הטרמינל לקבלת פרטי השגיאה או וודא שהמפתח תקין.")
        
    col.update_one({"_id": ObjectId(game_id)}, {"$set": {"ai_description": new_desc}})
    return jsonify({"success": True, "description": new_desc})

@game_bp.route("/game/generate-missing-descriptions", methods=["POST"])
def generate_missing_descriptions():
    """מייצר תיאורי AI לכל המשחקים שחסר להם תיאור במסד הנתונים"""
    if "user" not in session or session["user"]["role"] not in ["developer", "critic"]:
        raise BadRequest("אין לך הרשאה לביצוע פעולה זו.")

    col = get_collection("pro")
    # מחפש משחקים שהתיאור שלהם ריק, חסר או מכיל רק רווחים
    query = {"$or": [{"ai_description": ""}, {"ai_description": {"$exists": False}}, {"ai_description": None}]}
    # הגבלה ל-3 משחקים בכל פעם כדי לא לחרוג ממכסת ה-RPM (5) ולא לגרום ל-Timeout בשרת
    games_to_update = list(col.find(query).limit(3)) # הופחת ל-3
    
    count = 0
    for game in games_to_update:
        new_desc = api_service.fetch_ai_description(game["title"])
        if new_desc:
            col.update_one({"_id": game["_id"]}, {"$set": {"ai_description": new_desc}})
            count += 1
            # השהייה של 12 שניות בין בקשה לבקשה (מבטיח מקסימום 5 בקשות בדקה)
            time.sleep(13) # השהייה בטוחה מעט יותר למניעת Rate Limit
            
    return jsonify({"success": True, "updated_count": count})

@game_bp.route("/game/genres", methods=["GET"])
def get_genres():
    """שולף רשימה של ז'אנרים ייחודיים הקיימים במסד הנתונים"""
    col = get_collection("pro")
    # שימוש ב-aggregation כדי לקבל כל ז'אנר ואת כמות המשחקים בו
    pipeline = [
        {"$group": {"_id": "$genre", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    genres = list(col.aggregate(pipeline))
    return jsonify(genres)



@game_bp.route("/game/<game_id>", methods=["GET"])
def get_game(game_id: str):
    col = get_collection("pro")
    try:
        game = col.find_one({"_id": ObjectId(game_id)})
    except Exception:
        raise BadRequest("Invalid ID format")
        
    if not game:
        raise NotFound(f"Game {game_id} not found")
    game["_id"] = str(game["_id"])  
    return jsonify(game)


@game_bp.route("/game", methods=["POST"])
def create_game():
    data = request.get_json(silent=True)
    data = validate_game_data(data) # שימוש במתודה החדשה

    col = get_collection("pro")
    
    # בדיקת הרשאה: רק מבקרים ומפתחים יכולים להוסיף משחקים
    if "user" not in session or (session["user"]["role"] != "critic" and session["user"]["role"] != "developer"):
        raise BadRequest("רק מבקרים ומפתחים יכולים להוסיף משחקים.")
    
    # בדיקה אם המשחק קיים (Case-insensitive)
    if col.find_one({"title": re.compile(f"^{re.escape(data['title'])}$", re.IGNORECASE)}):
        raise Conflict("המשחק כבר קיים ברשימה שלך")

    # תמיד ננסה להביא תיאור מ-Gemini עבור השדה הנפרד
    ai_description = api_service.fetch_ai_description(data["title"])

    # חילוץ הציון הראשוני שהוזן בטופס (dev_rating ב-JS)
    # תיקון קריטי: טיפול במצב שבו הציון נשלח כ-null או טקסט ריק
    try:
        raw_score = data.get("dev_rating")
        initial_score = int(raw_score) if raw_score is not None else 0
    except (ValueError, TypeError):
        initial_score = 0

    username = session["user"]["username"]
    is_critic = session["user"]["role"] == "critic"

    new_game = {
        "title": data["title"],
        "genre": data["genre"],
        "audience_score": 0, # מתחיל ב-0, מחושב לפי ביקורות
        "critic_score": initial_score if initial_score > 0 else 0,
        "critic_count": 1 if initial_score > 0 else 0,
        "review_count": 0,
        "release_date": data.get("release_date"),
        "image_url": data.get("image_url") or api_service.fetch_game_image(data["title"]),
        "description": data.get("description", ""),
        "ai_description": ai_description or "",
        "completed": False,
        "forum_posts": [], # רשימת פוסטים בפורום
        "reviews": [],
        "critics_who_rated": [username] if initial_score > 0 and is_critic else [],
        "critic_reviews": [{"username": username, "score": initial_score}] if initial_score > 0 and is_critic else []
    }
    
    col.insert_one(new_game)
    new_game["_id"] = str(new_game["_id"])
    
    return jsonify({"success": True, "data": new_game}), 201



@game_bp.route("/game/<game_id>", methods=["PUT"])
def change_game(game_id):
    data = request.get_json(silent=True)
    
    # בדיקת הרשאה: רק מבקרים ומפתחים יכולים לערוך משחקים
    if "user" not in session or session["user"]["role"] not in ["developer", "critic"]:
        raise BadRequest("אין לך הרשאה לערוך משחקים.")

    data = validate_game_data(data, partial=True) # אימות נתונים
    
    col = get_collection("pro")

    if "title" in data:
        # בדיקה אם הכותרת החדשה כבר קיימת במשחק אחר (מניעת כפילויות בעדכון)
        existing = col.find_one({"title": re.compile(f"^{re.escape(data['title'])}$", re.IGNORECASE)})
        if existing and str(existing["_id"]) != game_id:
            raise Conflict("כבר קיים משחק עם כותרת זו במערכת")
            
        # אם הכותרת השתנתה, נחפש תמונה חדשה באופן אוטומטי
        data["image_url"] = api_service.fetch_game_image(data["title"])

    allowed_keys = ("title", "completed", "genre", "description", "image_url", "ai_description")
    filtered_data = {k: v for k, v in data.items() if k in allowed_keys}

    try:
        result = col.update_one({"_id": ObjectId(game_id)}, {"$set": filtered_data})
    except Exception:
        raise BadRequest("Invalid ID format")

    if result.matched_count == 0:
        raise NotFound(f"{game_id} not found")

    return jsonify({"success": True, "updated_fields": filtered_data})

@game_bp.route("/game/<game_id>/refresh-image", methods=["POST"])
def refresh_game_image(game_id):
    """מפעיל חיפוש תמונה מחודש עבור משחק קיים"""
    col = get_collection("pro")
    try:
        game = col.find_one({"_id": ObjectId(game_id)})
    except Exception:
        raise BadRequest("Invalid ID format")
        
    if not game:
        raise NotFound(f"Game {game_id} not found")
        
    new_url = api_service.fetch_game_image(game["title"])
    col.update_one({"_id": ObjectId(game_id)}, {"$set": {"image_url": new_url}})
    
    return jsonify({"success": True, "image_url": new_url})

@game_bp.route("/game/<game_id>", methods=["PATCH"])
def patch_game_completed(game_id):
    data = request.get_json(silent=True)
    if not data or "completed" not in data:
        raise BadRequest("Missing 'completed' field")
    
    if not isinstance(data["completed"], bool):
        raise BadRequest("completed must be a boolean")

    col = get_collection("pro")
    try:
        result = col.update_one({"_id": ObjectId(game_id)}, {"$set": {"completed": data.get("completed")}})
    except Exception:
        raise BadRequest("Invalid ID format")
    
    if result.matched_count == 0:
        raise NotFound(f"Game {game_id} not found")
            
    return {"success": True, "message": "updated successfully"}

@game_bp.route("/game/<game_id>", methods=["DELETE"])
def delete_game(game_id):
    col = get_collection("pro")
    
    # רק אדמין או מבקר יכולים למחוק משחקים
    if "user" not in session or session["user"]["role"] not in ["developer", "critic"]:
        raise BadRequest("אין לך הרשאה למחוק משחקים.")

    try:
        result = col.delete_one({"_id": ObjectId(game_id)})
    except Exception:
        raise BadRequest("Invalid ID format")

    if result.deleted_count == 0:
        raise NotFound(f"{game_id} not found")

    return {"Message": "game removed successfully"}

@game_bp.route("/game/<game_id>/review", methods=["POST"])
def add_review(game_id):
    """הוספת ביקורת משתמש ועדכון ציון הקהל"""
    if "user" not in session:
        raise BadRequest("You must be logged in to post a review")

    data = request.get_json()
    rating = data.get("rating") # 1-5
    video_url = get_youtube_embed_url(data.get("video_url"))
    comment = data.get("comment", "")
    username = session["user"]["username"]

    if rating is None or not (1 <= rating <= 5):
        raise BadRequest("דירוג חייב להיות בין 1 ל-5")

    col = get_collection("pro")
    game = col.find_one({"_id": ObjectId(game_id)})
    if not game: raise NotFound("Game not found")

    # בדיקה אם המשתמש כבר דירג את המשחק הזה
    if any(r.get('username') == username for r in game.get('reviews', [])):
        raise BadRequest("כבר דירגת את המשחק הזה בעבר")

    # חישוב ממוצע חדש
    new_total_reviews = game.get("review_count", 0) + 1
    new_score = ((game.get("audience_score", 0) * game.get("review_count", 0)) + (rating * 20)) / new_total_reviews

    col.update_one(
        {"_id": ObjectId(game_id)},
        {
            "$set": {"audience_score": round(new_score), "review_count": new_total_reviews},
            "$push": {"reviews": {"username": username, "rating": rating, "comment": comment, "video_url": video_url}}
        }
    )
    return jsonify({"success": True})

@game_bp.route("/game/<game_id>/review", methods=["DELETE"])
def delete_review(game_id):
    """מחיקת דירוג משתמש ועדכון ממוצע הקהל מחדש"""
    if "user" not in session:
        raise BadRequest("עליך להיות מחובר כדי למחוק דירוג")

    username = session["user"]["username"]
    col = get_collection("pro")
    game = col.find_one({"_id": ObjectId(game_id)})
    if not game: raise NotFound("Game not found")

    # חיפוש הדירוג של המשתמש ברשימה
    user_review = next((r for r in game.get("reviews", []) if r.get('username') == username), None)
    if not user_review:
        raise BadRequest("לא נמצא דירוג שלך למשחק זה")

    rating = user_review.get("rating")
    count = game.get("review_count", 0)
    audience_score = game.get("audience_score", 0)

    # חישוב הממוצע החדש לאחר הסרת הדירוג
    new_total_reviews = count - 1
    new_score = 0
    if new_total_reviews > 0:
        new_score = ((audience_score * count) - (rating * 20)) / new_total_reviews

    col.update_one(
        {"_id": ObjectId(game_id)},
        {
            "$set": {"audience_score": round(new_score), "review_count": new_total_reviews},
            "$pull": {"reviews": {"username": username}}
        }
    )
    return jsonify({"success": True})

@game_bp.route("/game/<game_id>/critic-review", methods=["POST"])
def add_critic_review(game_id):
    """הוספת דירוג מבקר מקצועי (רק למבקרים)"""
    if "user" not in session or session["user"]["role"] != "critic":
        raise BadRequest("רק מבקרים רשומים יכולים להוסיף דירוג מבקר")

    data = request.get_json()
    username = session["user"]["username"]
    score = data.get("score") # ציון באחוזים 0-100

    if score is None or not (0 <= score <= 100):
        raise BadRequest("Invalid score: must be between 0 and 100")

    col = get_collection("pro")
    game = col.find_one({"_id": ObjectId(game_id)})
    if not game: raise NotFound("Game not found")

    # בדיקה אם המבקר כבר נתן ציון למשחק זה
    if username in game.get('critics_who_rated', []):
        raise BadRequest("כבר נתת דירוג מבקר למשחק זה")

    # חישוב ממוצע המבקרים
    new_total_critics = game.get("critic_count", 0) + 1
    new_critic_score = ((game.get("critic_score", 0) * game.get("critic_count", 0)) + score) / new_total_critics

    col.update_one(
        {"_id": ObjectId(game_id)},
        {
            "$set": {"critic_score": round(new_critic_score), "critic_count": new_total_critics},
            "$push": {
                "critics_who_rated": username,
                "critic_reviews": {"username": username, "score": score}
            }
        }
    )
    
    return jsonify({"success": True, "new_score": round(new_critic_score)})

@game_bp.route("/game/<game_id>/critic-review", methods=["DELETE"])
def delete_critic_review(game_id):
    """מחיקת דירוג מבקר ועדכון מדד המבקרים מחדש"""
    if "user" not in session or session["user"]["role"] != "critic":
        raise BadRequest("רק מבקרים יכולים למחוק דירוג מבקר")

    username = session["user"]["username"]
    col = get_collection("pro")
    game = col.find_one({"_id": ObjectId(game_id)})
    if not game: raise NotFound("Game not found")

    # חיפוש הדירוג הספציפי של המבקר
    user_review = next((r for r in game.get("critic_reviews", []) if r.get('username') == username), None)
    if not user_review:
        raise BadRequest("לא נמצא דירוג מבקר שלך למשחק זה")

    score_to_remove = user_review.get("score")
    count = game.get("critic_count", 0)
    current_critic_score = game.get("critic_score", 0)

    new_total = count - 1
    new_avg = 0
    if new_total > 0:
        new_avg = ((current_critic_score * count) - score_to_remove) / new_total

    col.update_one(
        {"_id": ObjectId(game_id)},
        {
            "$set": {"critic_score": round(new_avg), "critic_count": new_total},
            "$pull": {
                "critics_who_rated": username,
                "critic_reviews": {"username": username}
            }
        }
    )
    return jsonify({"success": True})

@game_bp.route("/game/<game_id>/forum", methods=["POST"])
def add_forum_post(game_id):
    """הוספת שאלה או פתרון בעיה לפורום"""
    if "user" not in session:
        raise BadRequest("You must be logged in to post in the forum")

    data = request.get_json()
    title = data.get("title")
    content = data.get("content")
    video_url = get_youtube_embed_url(data.get("video_url"))
    username = session["user"]["username"]

    if not title or not content:
        raise BadRequest("Title and content are required")

    col = get_collection("pro")
    game = col.find_one({"_id": ObjectId(game_id)})
    if not game:
        raise NotFound("Game not found")

    col.update_one(
        {"_id": ObjectId(game_id)},
        {"$push": {"forum_posts": {
            "id": str(ObjectId()),
            "username": username,
            "title": title,
            "content": content,
            "video_url": video_url,
            "timestamp": "עכשיו",
            "likes": []
        }}}
    )

    # יצירת התראות למבקרים שדירגו את המשחק
    critics = game.get("critics_who_rated", [])
    notif_col = get_collection("notifications")
    for critic_user in critics:
        if critic_user != username:  # לא לשלוח התראה לעצמי אם אני המבקר שכתב את הפוסט
            notif_col.insert_one({
                "to_user": critic_user,
                "from_user": username,
                "type": "forum_post",
                "message": f"פרסם פוסט חדש בקהילה של {game['title']}",
                "read": False,
                "created_at": datetime.now(timezone.utc)
            })

    return jsonify({"success": True})

@game_bp.route("/game/<game_id>/forum/<post_id>/like", methods=["POST"])
def toggle_forum_post_like(game_id, post_id):
    """הוספה או הסרה של לייק לפוסט בפורום"""
    if "user" not in session:
        raise BadRequest("עליך להיות מחובר כדי לעשות לייק")
    
    username = session["user"]["username"]
    col = get_collection("pro")
    
    # מציאת המשחק והפוסט הספציפי
    game = col.find_one({"_id": ObjectId(game_id), "forum_posts.id": post_id})
    if not game:
        raise NotFound("הפוסט לא נמצא")
    
    post = next(p for p in game["forum_posts"] if p["id"] == post_id)
    likes = post.get("likes", [])
    
    if username in likes:
        # הסרת לייק
        col.update_one(
            {"_id": ObjectId(game_id), "forum_posts.id": post_id},
            {"$pull": {"forum_posts.$.likes": username}}
        )
    else:
        # הוספת לייק
        col.update_one(
            {"_id": ObjectId(game_id), "forum_posts.id": post_id},
            {"$push": {"forum_posts.$.likes": username}}
        )
        
    return jsonify({"success": True})

@game_bp.route("/profile/<username>")
def profile_page(username):
    """מציג את דף הפרופיל של המשתמש"""
    return render_template("profile.html", profile_user=username)

@game_bp.route("/api/profile/<username>")
def get_profile_data(username):
    """שולף את כל הפעילות של משתמש מכל המשחקים"""
    game_col = get_collection("pro")
    user_col = get_collection("users")

    # שליפת נתוני משתמש מה-DB
    u_info = user_col.find_one({"username": username})
    if not u_info:
        raise NotFound("משתמש לא נמצא")

    followers = u_info.get("followers", [])
    following = u_info.get("following", [])
    
    is_following = False
    if "user" in session:
        is_following = session["user"]["username"] in followers

    # חיפוש כל המשחקים שבהם המשתמש פרסם פוסט או ביקורת
    games = list(game_col.find({
        "$or": [
            {"forum_posts.username": username},
            {"reviews.username": username}
        ]
    }))
    
    user_posts = []
    user_videos = []
    
    for game in games:
        game_id = str(game["_id"])
        game_title = game["title"]
        
        # חילוץ פוסטים מהפורום
        for post in game.get("forum_posts", []):
            if post.get("username") == username:
                post["game_id"] = game_id
                post["game_title"] = game_title
                user_posts.append(post)
        
        # חילוץ ביקורות עם וידאו
        for rev in game.get("reviews", []):
            if rev.get("username") == username and rev.get("video_url"):
                rev["game_id"] = game_id
                rev["game_title"] = game_title
                user_videos.append(rev)
                
    return jsonify({
        "username": username,
        "role": u_info.get("role", "user"),
        "posts": user_posts,
        "videos": user_videos,
        "followers_count": len(followers),
        "following_count": len(following),
        "is_following": is_following
    })