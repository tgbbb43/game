from werkzeug.exceptions import BadRequest, UnprocessableEntity

def validate_game_data(data, partial=False):
    """פונקציה לאימות נתוני המשחק (game/pro)"""
    if not data or not isinstance(data, dict):
        raise BadRequest("Request body must be JSON")

    # בדיקת כותרת (חובה רק אם זה לא עדכון חלקי)
    if not partial and "title" not in data:
        raise BadRequest("Title is required")

    if "title" in data:
        title = data["title"]
        if not isinstance(title, str):
            raise BadRequest("Title must be a string")
        if not title.strip():
            raise UnprocessableEntity("Title must contain text")
        data["title"] = title.strip()

    # בדיקת ז'אנר
    if not partial and "genre" not in data:
        raise BadRequest("Genre is required")
    if "genre" in data:
        if not isinstance(data["genre"], str) or not data["genre"].strip():
            raise BadRequest("Genre must be a non-empty string")
        data["genre"] = data["genre"].strip()

    # בדיקת תיאור/המלצה
    if "description" in data and data["description"]:
        if not isinstance(data["description"], str):
            raise BadRequest("Description must be a string")
        data["description"] = data["description"].strip()

    if "completed" in data and not isinstance(data["completed"], bool):
        raise BadRequest("Completed must be a boolean")

    return data