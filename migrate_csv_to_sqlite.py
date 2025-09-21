import pandas as pd
from app import db, Corpus, app

CSV_PATH = "data/corpus.csv"

df = pd.read_csv(CSV_PATH)
df = df.fillna("")

with app.app_context():
    for _, row in df.iterrows():
        entry = Corpus(
            isiZulu=row.get("isiZulu", "").strip(),
            English=row.get("English", "").strip(),
            isiXhosa=row.get("isiXhosa", "").strip(),
            siSwati=row.get("siSwati", "").strip(),
            Context=row.get("Context", "").strip(),
            Page=str(row.get("Page", "")).strip()
        )
        db.session.add(entry)

    db.session.commit()
    print("✅ CSV imported to SQLite successfully!")
