# 🎮 Eli Pro Game Manager

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0-green.svg)
![MongoDB](https://img.shields.io/badge/mongodb-latest-green.svg)

מערכת ניהול משחקים מתקדמת המשלבת בינה מלאכותית (AI), אינטגרציה עם APIs בינלאומיים וקהילה חברתית תוססת. הפרויקט נבנה בדגש על חוויית משתמש (UX), אבטחה וקוד נקי.

## ✨ תכונות עיקריות (Key Features)

- 🤖 **Gemini AI Integration**: יצירה אוטומטית של תיאורי משחקים מעניינים בעברית ובאנגלית באמצעות הבינה המלאכותית של גוגל (`gemini-1.5-flash`).
- 🔍 **Global Game Search**: חיפוש וסנכרון נתונים בזמן אמת מול **Steam** ו-**RAWG** לקבלת תמונות, תאריכי יציאה ומטא-דאטה.
- 🌓 **Adaptive UI**: ממשק מודרני התומך ב-**Dark Mode** ו-**Light Mode** עם מעברים חלקים (Transitions).
- 🌍 **Multi-language Support**: תמיכה מלאה בעברית (RTL) ובאנגלית (LTR) בלחיצת כפתור.
- 👥 **Community & Forum**: פורומים ייעודיים לכל משחק, מערכת לייקים, פוסטים ושיתוף סרטוני ביקורת מיוטיוב.
- 🛡️ **Role-Based Access Control (RBAC)**: ניהול הרשאות קפדני בין משתמשים רגילים, מבקרים (Critics) ומנהלי מערכת (Developers).
- 👤 **Social Profiles**: דפי פרופיל אישיים המציגים את כל פעילות המשתמש, כולל מערכת עוקבים (Followers).
- ⚡ **Smart Caching**: מערכת מטמון מבוססת MongoDB לחיסכון בבקשות API ושיפור מהירות הטעינה, כולל מחיקה אוטומטית (TTL Index).

## 🚀 טכנולוגיות (Tech Stack)

- **Backend**: Python (Flask Framework)
- **Database**: MongoDB (Atlas) עם PyMongo
- **AI**: Google Gemini SDK (`google-genai`)
- **External APIs**: Steam Store API, RAWG API
- **Frontend**: Modern HTML5, JavaScript (ES6+), CSS3 Variables

## 🛠️ התקנה והרצה (Setup)

### דרישות קדם
- Python 3.12 ומעלה
- חשבון ב-MongoDB Atlas
- מפתחות API ל-Gemini ו-RAWG

### שלבי התקנה

1. **שיבוט הפרויקט**:
   ```bash
   git clone <repository-url>
   cd "eli pro"
   ```

2. **התקנת תלויות**:
   ```bash
   pip install flask pymongo requests google-genai python-dotenv
   ```

3. **הגדרת משתני סביבה**:
   צור קובץ `.env` בתיקיית השורש והזן את הערכים הבאים:
   ```env
   MONGO_URI=mongodb+srv://<user>:<password>@cluster...
   GEMINI_API_KEY=your_gemini_key
   RAWG_API_KEY=your_rawg_key
   SECRET_KEY=your_secret_session_key
   ```

4. **הרצת השרת**:
   ```bash
   python app.py
   ```

## 📂 מבנה הפרויקט (Project Structure)

- `app.py`: אתחול האפליקציה, הגדרת ה-Secret Key ורישום ה-Blueprints.
- `rhodes.py`: לב המערכת - ניהול לוגיקת המשחקים, ה-API Service (מחלקה מסודרת) וה-Caching.
- `auth.py`: ניהול משתמשים, הרשאות, פרופילים ומערכת העוקבים.
- `db.py`: הגדרת החיבור ל-MongoDB ויצירת אינדקסים (Unique, TTL).
- `methods.py`: פונקציות עזר לאימות נתונים (Validation).
- `errors.py`: טיפול גלובלי בשגיאות HTTP וכפילויות ב-Database.
- `static/style.css`: עיצוב מבוסס משתנים (Variables) התומך ב-Themes ו-RTL.
- `templates/`: דפי הממשק (Jinja2 Templates).

## 📝 רישיון ושימוש
הפרויקט נבנה למטרות למידה וניהול אישי. כל הזכויות שמורות לאלי.

---
*נבנה באהבה על ידי Eli Pro & Gemini Code Assist*# game
