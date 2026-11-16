"""IT Asset and Software License Tracker - Flask + SQLite backend.
Run:  pip install -r requirements.txt  &&  python app.py   ->  http://127.0.0.1:5000
"""
import os
import sqlite3
from datetime import date

from flask import Flask, g, jsonify, request, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "tracker.db")
app = Flask(__name__, static_folder=None)

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT, serial TEXT, owner TEXT, status TEXT, warranty TEXT);
CREATE TABLE IF NOT EXISTS licenses(id TEXT PRIMARY KEY, name TEXT NOT NULL, vendor TEXT, seats INTEGER, used INTEGER, renewal TEXT);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.executescript(SCHEMA)
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def rows(table):
    return [dict(r) for r in db().execute("SELECT * FROM " + table + " ORDER BY id")]


def days_until(s):
    return (date.fromisoformat(s) - date.today()).days if s else None


def quality_issues():
    out, assets, lic = [], rows("assets"), rows("licenses")
    serials = [a["serial"] for a in assets if a["serial"]]
    for a in assets:
        d = days_until(a["warranty"])
        if not a["serial"]:
            out.append((a["id"], "High", "Missing serial number"))
        elif serials.count(a["serial"]) > 1:
            out.append((a["id"], "Critical", "Duplicate serial " + a["serial"]))
        if a["status"] == "In use" and not a["owner"]:
            out.append((a["id"], "High", "In use but no owner assigned"))
        if a["status"] != "Retired":
            if d is None:
                out.append((a["id"], "Medium", "No warranty date"))
            elif d < 0:
                out.append((a["id"], "High", "Warranty expired %d days ago" % -d))
            elif d <= 60:
                out.append((a["id"], "Medium", "Warranty ends in %d days" % d))
    for l in lic:
        d = days_until(l["renewal"])
        if l["used"] > l["seats"]:
            out.append((l["id"], "Critical", "Over-allocated: %d used of %d seats" % (l["used"], l["seats"])))
        elif l["seats"] and l["used"] / l["seats"] < 0.5:
            out.append((l["id"], "Low", "Under-used: below 50% of seats"))
        if d is None:
            out.append((l["id"], "Medium", "No renewal date"))
        elif d < 0:
            out.append((l["id"], "High", "Renewal overdue"))
        elif d <= 30:
            out.append((l["id"], "Medium", "Renews in %d days" % d))
    return [{"id": i, "severity": s, "issue": m} for i, s, m in out]


@app.get("/")
def index():
    return send_from_directory(BASE, "index.html")


@app.get("/api/state")
def get_state():
    meta = {r["key"]: int(r["value"]) for r in db().execute("SELECT * FROM meta")}
    return jsonify({"assets": rows("assets"), "lic": rows("licenses"),
                    "na": meta.get("na", 108), "nl": meta.get("nl", 205)})


@app.put("/api/state")
def put_state():
    s = request.get_json(force=True)
    conn = db()
    with conn:
        conn.execute("DELETE FROM assets")
        conn.execute("DELETE FROM licenses")
        for a in s.get("assets", []):
            conn.execute("INSERT INTO assets VALUES(?,?,?,?,?,?,?)",
                         (a["id"], a["name"], a["type"], a["serial"], a["owner"], a["status"], a["warranty"]))
        for l in s.get("lic", []):
            conn.execute("INSERT INTO licenses VALUES(?,?,?,?,?,?)",
                         (l["id"], l["name"], l["vendor"], int(l["seats"]), int(l["used"]), l["renewal"]))
        conn.execute("INSERT OR REPLACE INTO meta VALUES('na', ?)", (str(s.get("na", 108)),))
        conn.execute("INSERT OR REPLACE INTO meta VALUES('nl', ?)", (str(s.get("nl", 205)),))
    return jsonify(ok=True)


@app.get("/api/assets")
def list_assets():
    out = rows("assets")
    for key in ("status", "owner", "type"):
        if request.args.get(key):
            out = [a for a in out if a[key] == request.args[key]]
    return jsonify(out)


@app.post("/api/assets")
def add_asset():
    d = request.get_json(force=True)
    if not d.get("name"):
        return jsonify(error="name is required"), 400
    conn = db()
    with conn:
        row = conn.execute("SELECT value FROM meta WHERE key='na'").fetchone()
        n = int(row["value"]) if row else 108
        conn.execute("INSERT OR REPLACE INTO meta VALUES('na', ?)", (str(n + 1),))
        conn.execute("INSERT INTO assets VALUES(?,?,?,?,?,?,?)", ("AST-%d" % n, d["name"], d.get("type", "Other"),
                     d.get("serial", ""), d.get("owner", ""), d.get("status", "In stock"), d.get("warranty", "")))
    return jsonify(dict(conn.execute("SELECT * FROM assets WHERE id=?", ("AST-%d" % n,)).fetchone())), 201


@app.patch("/api/assets/<aid>")
def update_asset(aid):
    d = request.get_json(force=True)
    conn = db()
    with conn:
        for f in ("name", "type", "serial", "owner", "status", "warranty"):
            if f in d:
                conn.execute("UPDATE assets SET %s=? WHERE id=?" % f, (d[f], aid))
    r = conn.execute("SELECT * FROM assets WHERE id=?", (aid,)).fetchone()
    return (jsonify(dict(r)), 200) if r else (jsonify(error="Asset not found"), 404)


@app.get("/api/licenses")
def list_licenses():
    return jsonify(rows("licenses"))


@app.get("/api/quality")
def quality():
    issues = quality_issues()
    total = len(rows("assets")) + len(rows("licenses"))
    flagged = len({i["id"] for i in issues})
    return jsonify({"score": round((1 - flagged / total) * 100) if total else 100, "count": len(issues), "issues": issues})


if __name__ == "__main__":
    app.run(debug=True)
