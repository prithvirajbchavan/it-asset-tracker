# IT Asset and Software License Tracker

Inventory of hardware assets and software licenses with ownership, warranty and renewal tracking,
plus automatic data-quality checks (missing owner or serial, duplicate serials, expiring warranties,
over-allocated and under-used licenses, missing renewal dates).
Front end: single-page HTML/JS. Back end: Flask + SQLite (REST API).

## Run
    pip install -r requirements.txt
    python app.py
Open http://127.0.0.1:5000 (the database `tracker.db` is created on first run).
Opening `index.html` directly also works, in browser-only mode.

## API
| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/assets?status=&owner=&type= | List / filter assets |
| POST | /api/assets | Add an asset (`name` required) |
| PATCH | /api/assets/<id> | Update owner, status, serial, warranty |
| GET | /api/licenses | List licenses with seats and usage |
| GET | /api/quality | Data-quality score and issue list |
| GET/PUT | /api/state | Whole-state sync used by the UI |
