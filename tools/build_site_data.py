"""
Build the site's data file from the SQLite ledger.

  SQLite ledger (master)  ->  data/cbse10.json  ->  cbse10.html

The ledger at C:\\Users\\achou\\Documents\\vidarbha50.db is the SOURCE OF TRUTH.
It lives OUTSIDE this repo on purpose: it carries provenance (which email, which
attachment, how confident we are in the school attribution) and that must not be
published. Only the ranked, publishable rows are written into data/.

Run:  python tools/build_site_data.py
Then: git add data/cbse10.json && git commit && git push

Rules this script enforces:
  * percentages are copied verbatim from the ledger, NEVER computed
  * only students inside the Top 50 dense ranks are published
  * ties are ordered by school name A-Z, then student name (same as the page)
"""
import sqlite3, json, os, datetime

DB   = r"C:\Users\achou\Documents\vidarbha50.db"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(REPO, "data", "cbse10.json")
TOP_N = 50

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
c = con.cursor()

rows = [dict(r) for r in c.execute("""
    SELECT student_name, percentage, school_name_as_uploaded, city, confidence
    FROM students
    WHERE percentage IS NOT NULL AND TRIM(percentage) <> ''
""")]
con.close()

for r in rows:
    r["pct_f"] = float(r["percentage"])

# dense rank on percentage alone
pcts = sorted({r["pct_f"] for r in rows}, reverse=True)
keep = set(pcts[:TOP_N])
pub  = [r for r in rows if r["pct_f"] in keep]

# same ordering the page uses: pct desc, school A-Z, student A-Z
pub.sort(key=lambda r: (-r["pct_f"], r["school_name_as_uploaded"], r["student_name"]))

rank_of = {p: i + 1 for i, p in enumerate(sorted(keep, reverse=True))}

students = [{
    "name":    r["student_name"],
    "pct":     r["pct_f"],
    "college": r["school_name_as_uploaded"],
    "branch":  r["city"],
    "rank":    rank_of[r["pct_f"]],
} for r in pub]

now = datetime.datetime.now(datetime.timezone.utc)
payload = {
    "board":          "cbse10",
    "generated_at":   now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "source":         "vidarbha50.db (SQLite ledger)",
    "total_students": len(students),
    "total_schools":  len({s["college"] for s in students}),
    "ranks":          len(keep),
    "cutoff":         min(keep),
    "students":       students,
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=1)

print("wrote", OUT)
print("  students %d | schools %d | ranks %d | cutoff %s"
      % (payload["total_students"], payload["total_schools"],
         payload["ranks"], payload["cutoff"]))
print("  rank 1:", [s["name"] + " (" + s["college"] + ")"
                    for s in students if s["rank"] == 1])
print("  ledger rows not published (below cut-off): %d" % (len(rows) - len(pub)))
