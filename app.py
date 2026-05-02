import os
from dotenv import load_dotenv
load_dotenv() # טעינת משתני סביבה לפני הכל

from flask import Flask, render_template, session
from db import init_db, setup_indexes
from rhodes import game_bp
from auth import auth_bp
from errors import register_error_handlers

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_fallback_key")
init_db(app)
setup_indexes() # קריאה לפונקציה ליצירת אינדקסים

app.register_blueprint(game_bp)
app.register_blueprint(auth_bp)
register_error_handlers(app)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/game-view/<game_id>")
def game_view(game_id):
    return render_template("game_details.html", game_id=game_id)

if __name__ == "__main__":
    app.run(debug=True)