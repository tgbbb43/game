from flask import jsonify
from werkzeug.exceptions import HTTPException
from pymongo.errors import DuplicateKeyError

def register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        """מחזיר שגיאות HTTP כ-JSON במקום HTML"""
        response = jsonify({
            "success": False,
            "error": e.name,
            "message": e.description,
            "code": e.code
        })
        return response, e.code

    @app.errorhandler(DuplicateKeyError)
    def handle_duplicate_key(e):
        """מטפל בשגיאות כפילות של MongoDB שנוצרות עקב אינדקס ייחודי"""
        return jsonify({
            "success": False,
            "error": "Conflict",
            "message": "הפעולה נכשלה: פריט עם נתונים אלו (כמו שם המשחק) כבר קיים במערכת.",
            "code": 409
        }), 409