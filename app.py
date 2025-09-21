from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import nltk
from collections import Counter
import difflib
import os
import hashlib
import re
from werkzeug.utils import secure_filename

# -------------------- APP SETUP -------------------- #
app = Flask(__name__)
CORS(app)
app.secret_key = "supersecretkey123"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "txt", "doc", "docx"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'corpus.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -------------------- DATABASE MODELS -------------------- #
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)


class Corpus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    isiZulu = db.Column(db.String(255), nullable=False)
    English = db.Column(db.String(255), nullable=False)
    isiXhosa = db.Column(db.String(255))
    siSwati = db.Column(db.String(255))
    Context = db.Column(db.Text, nullable=False)
    Page = db.Column(db.String(50))
    file_path = db.Column(db.String(255))

# -------------------- HELPERS -------------------- #
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def valid_password(password):
    return len(password) >= 8 and re.search(r"[A-Z]", password) and re.search(r"[a-z]", password)


def rebuild_tokens():
    """Rebuilds token list from isiZulu field for global search suggestions"""
    global tokens
    all_text = " ".join([entry.isiZulu for entry in Corpus.query.all() if entry.isiZulu]).lower()
    try:
        tokens = nltk.word_tokenize(all_text)
    except LookupError:
        nltk.download("punkt")
        tokens = nltk.word_tokenize(all_text)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# -------------------- INITIALIZE DATABASE -------------------- #
with app.app_context():
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    db.create_all()
    rebuild_tokens()


# -------------------- ROUTES -------------------- #
@app.route("/")
def home_page():
    if "username" in session:
        return redirect(url_for("corpus_page"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        user = User.query.filter_by(username=username).first()
        if user and user.password == hash_password(password):
            session["username"] = username
            return redirect(url_for("corpus_page"))
        return render_template("login.html", error="Invalid username or password.")
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()

        if not valid_password(password):
            return render_template("signup.html", error="Password must be 8+ chars with upper & lowercase.")
        if User.query.filter_by(username=username).first():
            return render_template("signup.html", error="Username already exists.")

        new_user = User(username=username, password=hash_password(password))
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))


@app.route("/corpus")
def corpus_page():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", username=session["username"])


# -------------------- SEARCH (with frequency + common pairs) -------------------- #
@app.route("/search")
def search():
    query = request.args.get("q", "").lower().strip()
    if not query:
        return jsonify({
            "query": query,
            "results": [],
            "did_you_mean": [],
            "frequency": 0,
            "usage_percent": 0,
            "total_words": 0,
            "common_pairs": []
        })

    # Search across all fields
    results = Corpus.query.filter(
        (Corpus.isiZulu.ilike(f"%{query}%")) |
        (Corpus.English.ilike(f"%{query}%")) |
        (Corpus.isiXhosa.ilike(f"%{query}%")) |
        (Corpus.siSwati.ilike(f"%{query}%"))
    ).all()

    # Format results
    result_dicts = [
        {
            "isiZulu": r.isiZulu,
            "English": r.English,
            "isiXhosa": r.isiXhosa,
            "siSwati": r.siSwati,
            "Context": r.Context,
            "Page": r.Page,
            "file_path": r.file_path
        }
        for r in results
    ]

    # Rebuild the full text from all fields for frequency & pairs
    all_text = " ".join([
        " ".join([
            r.isiZulu or "",
            r.English or "",
            r.isiXhosa or "",
            r.siSwati or ""
        ]) for r in results
    ]).lower()

    tokens_local = nltk.word_tokenize(all_text) if all_text else []

    # Frequency
    freq = Counter(tokens_local)
    total_tokens = len(tokens_local)
    count = freq.get(query, 0)
    usage_percent = (count / total_tokens * 100) if total_tokens > 0 else 0

    # Common pairs (bigrams)
    bigrams = list(nltk.bigrams(tokens_local))
    bigram_freq = Counter(bigrams)
    related_pairs = [
        {"pair": " ".join(pair), "count": c}
        for pair, c in bigram_freq.items() if query in pair
    ]
    related_pairs = sorted(related_pairs, key=lambda x: x["count"], reverse=True)[:10]

    # Did you mean
    did_you_mean = []
    if not results:
        did_you_mean = difflib.get_close_matches(query, tokens, n=5, cutoff=0.6)

    return jsonify({
        "query": query,
        "results": result_dicts,
        "did_you_mean": did_you_mean,
        "frequency": count,
        "usage_percent": round(usage_percent, 4),
        "total_words": total_tokens,
        "common_pairs": related_pairs
    })


# -------------------- ADD ENTRY -------------------- #
@app.route("/add", methods=["POST"])
def add_entry():
    data = request.get_json()
    isiZulu = data.get("isiZulu", "").strip()
    English = data.get("English", "").strip()
    isiXhosa = data.get("isiXhosa", "").strip()
    siSwati = data.get("siSwati", "").strip()
    Context = data.get("Context", "").strip()
    Page = data.get("Page", "").strip()

    if not isiZulu or not English or not Context:
        return jsonify({"success": False, "message": "isiZulu, English and Context are required."})

    new_entry = Corpus(
        isiZulu=isiZulu,
        English=English,
        isiXhosa=isiXhosa,
        siSwati=siSwati,
        Context=Context,
        Page=Page
    )
    db.session.add(new_entry)
    db.session.commit()
    rebuild_tokens()

    return jsonify({"success": True, "message": f"Added '{isiZulu}' to corpus."})


# -------------------- UPLOAD -------------------- #
@app.route("/upload", methods=["POST"])
def upload_document():
    if "username" not in session:
        return jsonify({"success": False, "message": "Please login to upload."})

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file part."})

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "No selected file."})

    if not allowed_file(file.filename):
        return jsonify({"success": False, "message": "File type not allowed."})

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)

    new_entry = Corpus(
        isiZulu="File Upload",
        English=filename,
        Context="Uploaded document",
        file_path=f"uploads/{filename}"
    )
    db.session.add(new_entry)
    db.session.commit()
    rebuild_tokens()

    return jsonify({"success": True, "message": f"File '{filename}' uploaded successfully!"})


# -------------------- RUN -------------------- #
if __name__ == "__main__":
    app.run(debug=True)
