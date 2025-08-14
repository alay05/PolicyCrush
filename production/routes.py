from flask import Blueprint, render_template, request, session, redirect, url_for

production = Blueprint("production", __name__, template_folder="templates")

def mock_gmail():
    return [
        {"id": "g1", "title": "Quest acquires assets from Fresenius", "date": "2025-08-05", "url": "https://example.com/a"},
        {"id": "g2", "title": "CMS releases new payment rule", "date": "2025-08-05", "url": "https://example.com/b"},
        {"id": "g3", "title": "HHS announces grant program", "date": "2025-08-04", "url": "https://example.com/c"},
    ]

def mock_senate():
    return [
        {"id": "s1", "title": "Finance Committee statement on drug pricing", "date": "2025-08-05", "url": "https://example.com/d"},
        {"id": "s2", "title": "HELP Committee hearing announced", "date": "2025-08-04", "url": "https://example.com/e"},
    ]

def _ensure_session_bucket():
    if "curation" not in session:
        session["curation"] = {"gmail": [], "senate": []}
    if "gmail_manual_drafts" not in session:
        session["gmail_manual_drafts"] = []
    if "senate_manual_drafts" not in session:
        session["senate_manual_drafts"] = []

def _collect_manual_rows(prefix, form):
    count = int(form.get(f"{prefix}_count", 0))
    rows = []
    for i in range(count):
        title = (form.get(f"{prefix}_title_{i}") or "").strip()
        url = (form.get(f"{prefix}_url_{i}") or "").strip()
        date = (form.get(f"{prefix}_date_{i}") or "").strip()
        if title or url or date:
            rows.append({"title": title, "url": url, "date": date})
    return rows

def _merge_selected(prev_list, current_ids, source_items):
    prev = {a["id"]: a for a in prev_list}
    for i in current_ids:
        if i in source_items:
            prev[i] = source_items[i]
    return list(prev.values())

def _manuals_to_drafts(items, source_name):
    drafts = []
    for a in items:
        if a.get("manual") and a.get("source") == source_name:
            drafts.append({"title": a.get("title",""), "url": a.get("url",""), "date": a.get("date","")})
    return drafts

@production.get("/start")
def production_start():
    _ensure_session_bucket()
    articles = mock_gmail()
    prechecked = {a["id"] for a in session["curation"]["gmail"] if a["id"] in {x["id"] for x in articles}}
    drafts = session.get("gmail_manual_drafts", [])
    if not drafts:
        drafts = _manuals_to_drafts(session["curation"]["gmail"], "gmail")
    manual_rows = drafts + [{}]
    return render_template("production_start.html", articles=articles, prechecked=prechecked, manual_rows=manual_rows)

@production.post("/select-gmail")
def production_select_gmail():
    _ensure_session_bucket()
    action = request.form.get("action", "next")
    ids = request.form.getlist("selected")
    source_map = {a["id"]: a for a in mock_gmail()}
    merged = _merge_selected(session["curation"]["gmail"], ids, source_map)
    current_rows = _collect_manual_rows("gmail_manual", request.form)
    if action == "add":
        session["curation"]["gmail"] = merged
        session["gmail_manual_drafts"] = current_rows
        session.modified = True
        return redirect(url_for("production.production_start"))
    valid_manuals = [r for r in current_rows if (r.get("title") and r.get("url"))]
    merged = [a for a in merged if not (a.get("manual") and a.get("source") == "gmail")]
    existing_ids = {a["id"] for a in merged}
    manual_index = 1
    for r in valid_manuals:
        mid = f"g_manual_{manual_index}"
        while mid in existing_ids:
            manual_index += 1
            mid = f"g_manual_{manual_index}"
        merged.append({
            "id": mid,
            "title": r["title"],
            "url": r["url"],
            "date": r.get("date", ""),
            "manual": True,
            "source": "gmail",
        })
        existing_ids.add(mid)
        manual_index += 1
    session["curation"]["gmail"] = merged
    session["gmail_manual_drafts"] = []
    session.modified = True
    return redirect(url_for("production.production_senate"))

@production.get("/senate")
def production_senate():
    _ensure_session_bucket()
    articles = mock_senate()
    prechecked = {a["id"] for a in session["curation"]["senate"] if a["id"] in {x["id"] for x in articles}}
    drafts = session.get("senate_manual_drafts", [])
    if not drafts:
        drafts = _manuals_to_drafts(session["curation"]["senate"], "senate")
    manual_rows = drafts + [{}]
    return render_template("production_senate.html", articles=articles, prechecked=prechecked, manual_rows=manual_rows)

@production.post("/select-senate")
def production_select_senate():
    _ensure_session_bucket()
    action = request.form.get("action", "next")

    ids = request.form.getlist("selected")
    source_map = {a["id"]: a for a in mock_senate()}
    merged = _merge_selected(session["curation"]["senate"], ids, source_map)
    current_rows = _collect_manual_rows("senate_manual", request.form)

    if action == "add":
        session["curation"]["senate"] = merged
        session["senate_manual_drafts"] = current_rows
        session.modified = True
        return redirect(url_for("production.production_senate"))

    if action == "back":
        session["curation"]["senate"] = merged
        session["senate_manual_drafts"] = current_rows
        session.modified = True
        return redirect(url_for("production.production_start"))

    valid_manuals = [r for r in current_rows if (r.get("title") and r.get("url"))]
    merged = [a for a in merged if not (a.get("manual") and a.get("source") == "senate")]
    existing_ids = {a["id"] for a in merged}
    manual_index = 1
    for r in valid_manuals:
        mid = f"s_manual_{manual_index}"
        while mid in existing_ids:
            manual_index += 1
            mid = f"s_manual_{manual_index}"
        merged.append({
            "id": mid,
            "title": r["title"],
            "url": r["url"],
            "date": r.get("date", ""),
            "manual": True,
            "source": "senate",
        })
        existing_ids.add(mid)
        manual_index += 1

    session["curation"]["senate"] = merged
    session["senate_manual_drafts"] = []
    session.modified = True
    return redirect(url_for("production.production_review"))


@production.get("/review")
def production_review():
    _ensure_session_bucket()
    data = session["curation"]
    return render_template("production_review.html", data=data)

@production.post("/reset")
def production_reset():
    session.pop("curation", None)
    session["gmail_manual_drafts"] = []
    session["senate_manual_drafts"] = []
    session.modified = True
    return redirect(url_for("production.production_start"))
