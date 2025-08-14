from flask import Blueprint, render_template, request, session, redirect, url_for, make_response, jsonify
from datetime import datetime, timedelta
import json
from weasyprint import HTML

from production.adapters import fetch_gmail_unread
from production.adapters import fetch_news_bundle
from production.adapters import fetch_house_bundle
from production.adapters import fetch_senate_bundle

from features.calendar import (
    fetch_hearing_html,
    extract_event_info,
    create_event_addevent,
)

production = Blueprint("production", __name__, template_folder="templates")

GMAIL_STORE = {}
NEWS_STORE = {} 
HOUSE_STORE = {}
SENATE_STORE = {}

def _ensure_session_bucket():
    if "curation" not in session:
        session["curation"] = {"gmail": [], "news": [], "house": [], "senate": []}
    if "gmail_manual_drafts" not in session:
        session["gmail_manual_drafts"] = []
    if "news_ready" not in session:
        session["news_ready"] = False
    if "house_ready" not in session:
        session["house_ready"] = False
    if "senate_ready" not in session:
        session["senate_ready"] = False

def _reset_all():
    session.clear()
    GMAIL_STORE.clear()
    NEWS_STORE.clear()
    HOUSE_STORE.clear()
    SENATE_STORE.clear()

@production.get("/start")
def production_start():
    return render_template("production_start.html")

@production.post("/start")
def production_start_action():
    action = request.form.get("action")
    if action == "start":
        return redirect(url_for("production.production_gmail"))
    if action == "reset":
        _reset_all()
        return redirect(url_for("production.production_start"))
    return redirect(url_for("production.production_start"))

@production.get("/gmail")
def production_gmail():
    _ensure_session_bucket()
    ids = session.get("gmail_cache_ids") or []
    emails = [GMAIL_STORE[i] for i in ids if i in GMAIL_STORE]

    drafts = {}
    if emails:
        saved_manuals = [a for a in session["curation"]["gmail"] if a.get("manual") and a.get("source") == "gmail"]
        grouped = {}
        for a in saved_manuals:
            eid = a.get("origin_id", "")
            if not eid:
                continue
            grouped.setdefault(eid, []).append({
                "title": a.get("title",""),
                "date": a.get("date",""),
                "url": a.get("url","")
            })
        drafts = grouped

    return render_template(
        "production_gmail.html",
        articles=emails,
        error=None,
        action_was_load=bool(emails),
        drafts=drafts,
    )


@production.post("/select-gmail")
def production_select_gmail():
    _ensure_session_bucket()
    action = request.form.get("action", "next")

    if action == "load":
        try:
            emails = fetch_gmail_unread()
            for e in emails:
                GMAIL_STORE[e["id"]] = e
            session["gmail_cache_ids"] = [e["id"] for e in emails]
            # only when reloading Gmail do we invalidate downstream News
            session["news_ready"] = False
            session.modified = True
        except Exception as e:
            return render_template(
                "production_gmail.html",
                articles=None,
                error=f"Error: {e}",
                action_was_load=True,
                drafts={},
            )

        saved_manuals = [a for a in session["curation"]["gmail"] if a.get("manual") and a.get("source") == "gmail"]
        grouped = {}
        for a in saved_manuals:
            eid = a.get("origin_id", "")
            if not eid:
                continue
            grouped.setdefault(eid, []).append({
                "title": a.get("title",""),
                "date": a.get("date",""),
                "url": a.get("url","")
            })
        return render_template(
            "production_gmail.html",
            articles=emails,
            error=None,
            action_was_load=True,
            drafts=grouped,
        )

    # action == "next": collect manual items and move on without touching news_ready
    email_ids = request.form.getlist("email_id")

    manuals = []
    for eid in email_ids:
        titles = request.form.getlist(f"gmail_manual_title_{eid}[]")
        dates  = request.form.getlist(f"gmail_manual_date_{eid}[]")
        urls   = request.form.getlist(f"gmail_manual_url_{eid}[]")
        n = max(len(titles), len(dates), len(urls))
        for i in range(n):
            title = (titles[i] if i < len(titles) else "").strip()
            url   = (urls[i] if i < len(urls) else "").strip()
            date  = (dates[i] if i < len(dates) else "").strip()
            if title and url:
                manuals.append({
                    "id": f"g_manual_{eid}_{i+1}",
                    "title": title,
                    "url": url,
                    "date": date,
                    "manual": True,
                    "source": "gmail",
                    "origin_id": eid,
                })

    session["curation"]["gmail"] = manuals
    session.modified = True
    return redirect(url_for("production.production_news"))


@production.get("/news")
def production_news():
    _ensure_session_bucket()
    show_results = bool(session.get("news_ready", False))
    cache = session.get("news_cache")
    articles = None
    input_date = (datetime.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    use_openai = False

    if show_results and cache:
        input_date = cache.get("input_date", input_date)
        use_openai = bool(cache.get("use_openai", False))
        articles = {}
        for name, meta in cache.get("sources", {}).items():
            ids = meta.get("ids", [])
            items = [NEWS_STORE[i] for i in ids if i in NEWS_STORE]
            articles[name] = {"url": meta.get("url", ""), "items": items}

    prechecked = {a["id"] for a in session["curation"].get("news", []) if not a.get("manual")}
    manual_rows = session.get("news_manual_drafts") or [{}]
    return render_template(
        "production_news.html",
        articles=articles,
        prechecked=prechecked,
        input_date=input_date,
        use_openai=use_openai,
        error=None,
        action_was_load=bool(articles),
        manual_rows=manual_rows,
    )


@production.post("/select-news")
def production_select_news():
    _ensure_session_bucket()
    action = request.form.get("action", "next")

    if action == "load":
        input_date = (request.form.get("start_date") or "").strip()
        use_openai = "use_openai" in request.form
        error = None
        start_date = None
        if input_date:
            try:
                start_date = datetime.strptime(input_date, "%Y-%m-%d").date()
            except ValueError:
                error = "Invalid date."
        if error or not start_date:
            return render_template(
                "production_news.html",
                articles=None,
                prechecked=set(),
                input_date=input_date or "",
                use_openai=use_openai,
                error=error or None,
                action_was_load=True,
                manual_rows=session.get("news_manual_drafts") or [{}],
            )

        bundle = fetch_news_bundle(start_date, use_openai)
        sources = {}
        for name, meta in bundle.items():
            ids = []
            for item in meta["items"]:
                NEWS_STORE[item["id"]] = item
                ids.append(item["id"])
            sources[name] = {"url": meta["url"], "ids": ids}

        session["news_cache"] = {"sources": sources, "input_date": input_date, "use_openai": use_openai}
        session["news_ready"] = True
        session.modified = True

        articles = {name: {"url": m["url"], "items": [NEWS_STORE[i] for i in m["ids"] if i in NEWS_STORE]}
                    for name, m in sources.items()}
        prechecked = {a["id"] for a in session["curation"].get("news", []) if not a.get("manual")}
        manual_rows = session.get("news_manual_drafts") or [{}]
        return render_template(
            "production_news.html",
            articles=articles,
            prechecked=prechecked,
            input_date=input_date,
            use_openai=use_openai,
            error=None,
            action_was_load=True,
            manual_rows=manual_rows,
        )

    titles = request.form.getlist("news_manual_title[]")
    dates  = request.form.getlist("news_manual_date[]")
    urls   = request.form.getlist("news_manual_url[]")
    manual_rows = []
    manuals = []
    n = max(len(titles), len(dates), len(urls))
    for i in range(n):
        title = (titles[i] if i < len(titles) else "").strip()
        url   = (urls[i] if i < len(urls) else "").strip()
        date  = (dates[i] if i < len(dates) else "").strip()
        if title or url or date:
            manual_rows.append({"title": title, "date": date, "url": url})
        if title and url:
            manuals.append({
                "id": f"n_manual_{i+1}",
                "title": title,
                "url": url,
                "date": date,
                "manual": True,
                "source": "news",
            })

    selected_ids = request.form.getlist("selected")
    non_manuals = []
    cache = session.get("news_cache") or {}
    for name, meta in cache.get("sources", {}).items():
        for aid in meta.get("ids", []):
            if aid in selected_ids and aid in NEWS_STORE:
                non_manuals.append(NEWS_STORE[aid])

    session["news_manual_drafts"] = manual_rows
    session["curation"]["news"] = non_manuals + manuals
    session.modified = True

    if action == "back":
        return redirect(url_for("production.production_gmail"))
    return redirect(url_for("production.production_house"))


@production.get("/house")
def production_house():
    _ensure_session_bucket()
    show_results = bool(session.get("house_ready", False))
    cache = session.get("house_cache")
    committees = None
    input_date = (datetime.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    use_openai = False

    if show_results and cache and cache.get("committees"):
        use_openai = bool(cache.get("use_openai", False))
        input_date = cache.get("input_date", input_date)

        built = {}
        any_items = False
        for name, meta in cache["committees"].items():
            maj_ids = meta.get("majority", [])
            min_ids = meta.get("minority", [])
            maj = [HOUSE_STORE[i] for i in maj_ids if i in HOUSE_STORE]
            mino = [HOUSE_STORE[i] for i in min_ids if i in HOUSE_STORE]
            if maj or mino:
                any_items = True
            built[name] = {"majority": maj, "minority": mino}

        committees = built if any_items else None

    prechecked = {a["id"] for a in session["curation"].get("house", []) if not a.get("manual")}
    manual_rows = session.get("house_manual_drafts") or [{}]
    return render_template(
        "production_house.html",
        committees=committees,
        prechecked=prechecked,
        input_date=input_date,
        use_openai=use_openai,
        error=None,
        action_was_load=bool(committees),
        manual_rows=manual_rows,
    )


@production.post("/select-house")
def production_select_house():
    _ensure_session_bucket()
    action = request.form.get("action", "next")

    if action == "load":
        input_date = (request.form.get("start_date") or "").strip()
        use_openai = "use_openai" in request.form
        error = None
        start_date = None
        if input_date:
            try:
                start_date = datetime.strptime(input_date, "%Y-%m-%d").date()
            except ValueError:
                error = "Invalid date."
        if error or not start_date:
            return render_template(
                "production_house.html",
                committees=None,
                prechecked=set(),
                input_date=input_date or "",
                use_openai=use_openai,
                error=error or None,
                action_was_load=True,
                manual_rows=session.get("house_manual_drafts") or [{}],
            )

        bundle = fetch_house_bundle(start_date, use_openai)

        committees_meta = {}
        for name, groups in bundle.items():
            maj_ids, min_ids = [], []
            for item in groups["majority"]:
                HOUSE_STORE[item["id"]] = item
                maj_ids.append(item["id"])
            for item in groups["minority"]:
                HOUSE_STORE[item["id"]] = item
                min_ids.append(item["id"])
            committees_meta[name] = {"majority": maj_ids, "minority": min_ids}

        session["house_cache"] = {"committees": committees_meta, "input_date": input_date, "use_openai": use_openai}
        session["house_ready"] = True
        # only when House is reloaded do we invalidate downstream Senate
        session["senate_ready"] = False
        session.modified = True

        committees = {}
        for name, meta in committees_meta.items():
            committees[name] = {
                "majority": [HOUSE_STORE[i] for i in meta["majority"] if i in HOUSE_STORE],
                "minority": [HOUSE_STORE[i] for i in meta["minority"] if i in HOUSE_STORE],
            }

        prechecked = {a["id"] for a in session["curation"].get("house", []) if not a.get("manual")}
        manual_rows = session.get("house_manual_drafts") or [{}]
        return render_template(
            "production_house.html",
            committees=committees,
            prechecked=prechecked,
            input_date=input_date,
            use_openai=use_openai,
            error=None,
            action_was_load=True,
            manual_rows=manual_rows,
        )

    # non-load branch (Back/Next): DO NOT touch senate_ready
    titles = request.form.getlist("house_manual_title[]")
    dates  = request.form.getlist("house_manual_date[]")
    urls   = request.form.getlist("house_manual_url[]")
    manual_rows = []
    manuals = []
    n = max(len(titles), len(dates), len(urls))
    for i in range(n):
        title = (titles[i] if i < len(titles) else "").strip()
        url   = (urls[i] if i < len(urls) else "").strip()
        date  = (dates[i] if i < len(dates) else "").strip()
        if title or url or date:
            manual_rows.append({"title": title, "date": date, "url": url})
        if title and url:
            manuals.append({
                "id": f"h_manual_{i+1}",
                "title": title,
                "url": url,
                "date": date,
                "manual": True,
                "source": "house",
            })

    selected_ids = request.form.getlist("selected")
    non_manuals = []
    cache = session.get("house_cache") or {}
    for name, meta in cache.get("committees", {}).items():
        for aid in meta.get("majority", []) + meta.get("minority", []):
            if aid in selected_ids and aid in HOUSE_STORE:
                non_manuals.append(HOUSE_STORE[aid])

    session["house_manual_drafts"] = manual_rows
    session["curation"]["house"] = non_manuals + manuals
    session.modified = True

    if action == "back":
        return redirect(url_for("production.production_news"))
    return redirect(url_for("production.production_senate"))



@production.get("/senate")
def production_senate():
    _ensure_session_bucket()
    show_results = bool(session.get("senate_ready", False))
    cache = session.get("senate_cache")
    committees = None
    input_date = (datetime.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    use_openai = False

    if show_results and cache and cache.get("committees"):
        input_date = cache.get("input_date", input_date)
        use_openai = bool(cache.get("use_openai", False))
        built = {}
        any_items = False
        for name, meta in cache["committees"].items():
            maj_ids = meta.get("majority", [])
            min_ids = meta.get("minority", [])
            hear_ids = meta.get("hearing", [])
            url = meta.get("url", "")
            maj = [SENATE_STORE[i] for i in maj_ids if i in SENATE_STORE]
            mino = [SENATE_STORE[i] for i in min_ids if i in SENATE_STORE]
            hear = [SENATE_STORE[i] for i in hear_ids if i in SENATE_STORE]
            if maj or mino or hear:
                any_items = True
            built[name] = {"url": url, "majority": maj, "minority": mino, "hearing": hear}
        committees = built if any_items else None

    prechecked = {a["id"] for a in session["curation"].get("senate", []) if not a.get("manual")}
    manual_rows = session.get("senate_manual_drafts") or [{}]
    return render_template(
        "production_senate.html",
        committees=committees,
        prechecked=prechecked,
        input_date=input_date,
        use_openai=use_openai,
        error=None,
        action_was_load=bool(committees),
        manual_rows=manual_rows,
    )

@production.post("/select-senate")
def production_select_senate():
    _ensure_session_bucket()
    action = request.form.get("action", "next")

    if action == "load":
        input_date = (request.form.get("start_date") or "").strip()
        use_openai = "use_openai" in request.form
        error = None
        start_date = None
        if input_date:
            try:
                start_date = datetime.strptime(input_date, "%Y-%m-%d").date()
            except ValueError:
                error = "Invalid date."
        if error or not start_date:
            return render_template(
                "production_senate.html",
                committees=None,
                prechecked=set(),
                input_date=input_date or "",
                use_openai=use_openai,
                error=error or None,
                action_was_load=True,
                manual_rows=session.get("senate_manual_drafts") or [{}],
            )

        bundle = fetch_senate_bundle(start_date, use_openai)

        committees_meta = {}
        for name, groups in bundle.items():
            url = groups.get("url", "")
            maj_ids, min_ids, hear_ids = [], [], []
            for item in groups.get("majority", []):
                item["tag"] = "majority"
                SENATE_STORE[item["id"]] = item
                maj_ids.append(item["id"])

            for item in groups.get("minority", []):
                item["tag"] = "minority"
                SENATE_STORE[item["id"]] = item
                min_ids.append(item["id"])

            for item in groups.get("hearing", []):
                item["tag"] = "hearing"
                SENATE_STORE[item["id"]] = item
                hear_ids.append(item["id"])
            committees_meta[name] = {"url": url, "majority": maj_ids, "minority": min_ids, "hearing": hear_ids}

        session["senate_cache"] = {"committees": committees_meta, "input_date": input_date, "use_openai": use_openai}
        session["senate_ready"] = True
        session.modified = True

        committees = {}
        for name, meta in committees_meta.items():
            committees[name] = {
                "url": meta.get("url", ""),
                "majority": [SENATE_STORE[i] for i in meta["majority"] if i in SENATE_STORE],
                "minority": [SENATE_STORE[i] for i in meta["minority"] if i in SENATE_STORE],
                "hearing":  [SENATE_STORE[i] for i in meta["hearing"] if i in SENATE_STORE],
            }

        prechecked = {a["id"] for a in session["curation"].get("senate", []) if not a.get("manual")}
        manual_rows = session.get("senate_manual_drafts") or [{}]
        return render_template(
            "production_senate.html",
            committees=committees,
            prechecked=prechecked,
            input_date=input_date,
            use_openai=use_openai,
            error=None,
            action_was_load=True,
            manual_rows=manual_rows,
        )

    titles = request.form.getlist("senate_manual_title[]")
    dates  = request.form.getlist("senate_manual_date[]")
    urls   = request.form.getlist("senate_manual_url[]")
    manual_rows = []
    manuals = []
    n = max(len(titles), len(dates), len(urls))
    for i in range(n):
        title = (titles[i] if i < len(titles) else "").strip()
        url   = (urls[i] if i < len(urls) else "").strip()
        date  = (dates[i] if i < len(dates) else "").strip()
        if title or url or date:
            manual_rows.append({"title": title, "date": date, "url": url})
        if title and url:
            manuals.append({
                "id": f"s_manual_{i+1}",
                "title": title,
                "url": url,
                "date": date,
                "manual": True,
                "source": "senate",
            })

    selected_ids = request.form.getlist("selected")
    non_manuals = []
    cache = session.get("senate_cache") or {}
    for name, meta in cache.get("committees", {}).items():
        for aid in meta.get("majority", []) + meta.get("minority", []) + meta.get("hearing", []):
            if aid in selected_ids and aid in SENATE_STORE:
                non_manuals.append(SENATE_STORE[aid])

    session["senate_manual_drafts"] = manual_rows
    session["curation"]["senate"] = non_manuals + manuals
    session.modified = True

    if action == "back":
        return redirect(url_for("production.production_house"))
    return redirect(url_for("production.production_review"))

@production.get("/review")
def production_review():
    _ensure_session_bucket()
    curation = session.get("curation", {})
    resp = make_response(render_template(
        "production_review.html",
        gmail_items=curation.get("gmail", []),
        news_items=curation.get("news", []),
        house_items=curation.get("house", []),
        senate_items=curation.get("senate", []),
    ))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@production.post("/addevent")
def production_addevent():
    """Create an AddEvent calendar entry for a hearing URL."""
    payload = request.get_json(silent=True) or {}
    url = (payload.get("url") or "").strip()
    tz = payload.get("timezone") or "America/New_York"
    default_minutes = int(payload.get("duration_minutes") or 60)

    if not url:
        return jsonify({"ok": False, "error": "Missing 'url'."}), 400

    try:
        # 1) scrape + extract
        page_text = fetch_hearing_html(url)
        info_raw = extract_event_info(page_text)  # JSON string from your model
        info = json.loads(info_raw)

        # 2) combine date + time
        #    Expecting "YYYY-MM-DD" and "HH:MM" (24h) per your prompt.
        dt_start = datetime.strptime(
            f"{info['date']} {info['time']}", "%Y-%m-%d %H:%M"
        )
        dt_end = dt_start + timedelta(minutes=default_minutes)

        # 3) build AddEvent payload
        addevent_data = {
            "title": "[AUTO-TEST]" + info["title"],
            "datetime_start": dt_start.strftime("%Y-%m-%d %H:%M"),
            "datetime_end": dt_end.strftime("%Y-%m-%d %H:%M"),
            "location": info.get("location") or "",
            "description": url,               # keep the source link
            "timezone": tz,                   # e.g., America/New_York
        }

        # 4) create event
        res = create_event_addevent(addevent_data)
        # AddEvent typically returns id + url (name may vary; handle both)
        event_id = res.get("id") or res.get("event", {}).get("id")
        event_url = res.get("url") or res.get("event", {}).get("url") or res.get("link")

        return jsonify({"ok": True, "event_id": event_id, "event_url": event_url})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@production.get("/export-pdf")
def production_export_pdf():
    _ensure_session_bucket()
    cur = session.get("curation", {})

    html = render_template(
        "review_pdf.html",
        generated_at=datetime.now(),
        gmail_items=cur.get("gmail", []),
        news_items=cur.get("news", []),
        house_items=cur.get("house", []),
        senate_items=cur.get("senate", []),
    )

    pdf_bytes = HTML(string=html, base_url=request.root_url).write_pdf()
    stamp = datetime.now().strftime("%m/%d")
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'attachment; filename="PolicyCrush_{stamp}.pdf"'
    return resp
