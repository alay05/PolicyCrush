from flask import Blueprint, render_template, request, session, redirect, url_for, make_response, jsonify
from datetime import datetime, timedelta
import json
import re
from weasyprint import HTML
import hashlib
from collections import OrderedDict

from production.adapters import fetch_gmail_unread
from production.adapters import fetch_news_bundle
from production.adapters import fetch_house_bundle
from production.adapters import fetch_senate_bundle
from features.categorize import categorize_article, SPECIAL_CALENDAR, CATEGORIES

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
    if "categorize_ready" not in session:
        session["categorize_ready"] = False
    if "categories_cache" not in session:
        session["categories_cache"] = None
    if "sublinks" not in session:
        session["sublinks"] = {}

def _rehydrate(items, store):
    resolved = []
    for a in items or []:
        if a.get("manual"):
            resolved.append(a)  
        else:
            obj = store.get(a.get("id"))
            if obj:
                resolved.append(obj)
            else:
                resolved.append(a)
    return resolved

def _reset_all():
    session.clear()
    GMAIL_STORE.clear()
    NEWS_STORE.clear()
    HOUSE_STORE.clear()
    SENATE_STORE.clear()

def _signature(items):
    """
    Stable signature of the selected items to avoid re-categorizing
    unnecessarily. Uses id/title/tag triplets.
    """
    parts = []
    for it in items:
        parts.append(f"{it.get('id','')}|{it.get('title','')}|{it.get('tag','')}")
    blob = "\n".join(sorted(parts))
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()

def _ref(item, source: str):
    """Create a tiny reference for session storage."""
    return {"id": item.get("id"), "source": source}

def _resolve_ref(ref, cur):
    """Turn a stored ref back into a full item (or None)."""
    rid = (ref or {}).get("id")
    src = (ref or {}).get("source")
    if not rid or not src:
      return None

    if src == "news":
        return NEWS_STORE.get(rid)
    if src == "house":
        return HOUSE_STORE.get(rid)
    if src == "senate":
        return SENATE_STORE.get(rid)
    if src == "gmail":
        # Gmail items are only manual and live inside session["curation"]["gmail"]
        for g in (cur.get("gmail") or []):
            if g.get("id") == rid:
                return g
        return None
    return None

def _has_time_component(ts: str) -> bool:
    """
    Returns True if the timestamp has a time component.
    Accepts ISO-ish strings like YYYY-MM-DDTHH:MM (optionally with seconds/zone).
    """
    ts = (ts or "").strip()
    # Look for 'T' followed by HH:MM (allow more after, e.g., seconds or TZ)
    return bool(re.search(r"T\d{2}:\d{2}", ts))

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
            ts = (a.get("date", "") or "").strip()  # stored as either YYYY-MM-DD or YYYY-MM-DDTHH:MM
            if "T" in ts:
                d_part, t_part = ts.split("T", 1)
            else:
                d_part, t_part = ts, ""
            grouped.setdefault(eid, []).append({
                "title": a.get("title", ""),
                "date": d_part,
                "time": t_part,      # <-- add this so the template can prefill the time input
                "url": a.get("url", "")
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
        times  = request.form.getlist(f"gmail_manual_time_{eid}[]") 
        urls   = request.form.getlist(f"gmail_manual_url_{eid}[]")

        n = max(len(titles), len(dates), len(times), len(urls))
        for i in range(n):
            title = (titles[i] if i < len(titles) else "").strip()
            url   = (urls[i]   if i < len(urls)   else "").strip()
            d_raw = (dates[i]  if i < len(dates)  else "").strip()    
            t_raw = (times[i]  if i < len(times)  else "").strip()    

            if d_raw:
                timestamp = f"{d_raw}T{t_raw}" if t_raw else d_raw
            else:
                timestamp = ""

            if title and url:
                manuals.append({
                    "id": f"g_manual_{eid}_{i+1}",
                    "title": title,
                    "url": url,
                    "date": timestamp,    
                    "manual": True,
                    "source": "gmail",
                    "origin_id": eid,
                })


    session["curation"]["gmail"] = manuals
    session.modified = True

    session["categorize_ready"] = False
    session["categories_cache"] = None
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

    selected_ids = set(request.form.getlist("selected"))
    session["news_manual_drafts"] = manual_rows
    session["curation"]["news"] = (
        [{"id": aid, "manual": False, "source": "news"} for aid in selected_ids]
        + manuals
    )
    session.modified = True

    session["categorize_ready"] = False
    session["categories_cache"] = None
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

    selected_ids = set(request.form.getlist("selected"))
    session["house_manual_drafts"] = manual_rows
    session["curation"]["house"] = (
        [{"id": aid, "manual": False, "source": "house"} for aid in selected_ids]
        + manuals
    )
    session.modified = True

    session["categorize_ready"] = False
    session["categories_cache"] = None
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

    selected_ids = set(request.form.getlist("selected"))
    session["senate_manual_drafts"] = manual_rows
    session["curation"]["senate"] = (
        [{"id": aid, "manual": False, "source": "senate"} for aid in selected_ids]
        + manuals
    )
    session.modified = True

    session["categorize_ready"] = False
    session["categories_cache"] = None
    session.modified = True

    if action == "back":
        return redirect(url_for("production.production_house"))
    return redirect(url_for("production.production_categorize"))


@production.get("/categorize")
def production_categorize():
    """
    Intermediate page: show selections grouped by source (like Review),
    with a button to build categories.
    """
    _ensure_session_bucket()
    cur = session.get("curation", {})
    # hydrate selected ids into full objects
    resp = make_response(render_template(
        "production_categorize.html",
        gmail_items=cur.get("gmail", []),
        news_items=_rehydrate(cur.get("news"), NEWS_STORE),
        house_items=_rehydrate(cur.get("house"), HOUSE_STORE),
        senate_items=_rehydrate(cur.get("senate"), SENATE_STORE),
        categorize_ready=bool(session.get("categorize_ready", False)),
    ))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@production.post("/categorize")
def production_build_categories():
    _ensure_session_bucket()
    cur = session.get("curation", {})

    gmail_items  = cur.get("gmail", [])
    news_items   = _rehydrate(cur.get("news"), NEWS_STORE)
    house_items  = _rehydrate(cur.get("house"), HOUSE_STORE)
    senate_items = _rehydrate(cur.get("senate"), SENATE_STORE)

    all_items = []
    def add(src, arr):
        for a in arr or []:
            all_items.append({
                "id": a.get("id"),
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "date": a.get("date", ""),     
                "source": src,
                "committee": a.get("committee", ""),
            })
    add("gmail", gmail_items)
    add("news", news_items)
    add("house", house_items)
    add("senate", senate_items)

    current_sig = _signature(all_items)
    cache = session.get("categories_cache") or {}
    if cache.get("sig") == current_sig and cache.get("index"):
        session["categorize_ready"] = True
        session.modified = True
        return redirect(url_for("production.production_review"))

    # …(existing code that builds `categories` via categorize_article)…

    # Build categories index (label -> list[ref])
    categories_index = {
        SPECIAL_CALENDAR: [],
        "Congress and the Administration": [],
        "Health Insurance": [],
        "Health Tech": [],
        "Medicaid": [],
        "Medicare": [],
        "Pharmaceuticals and Medical Devices": [],
        "Quality and Innovation": [],
    }

    for a in all_items:
        is_hearing = _has_time_component(a.get("date", ""))
        label = categorize_article(a.get("title", ""), is_hearing=is_hearing)
        if label not in categories_index:
            label = "Quality and Innovation"
        categories_index[label].append(_ref(a, a.get("source")))
        
    session["categories_cache"] = {
        "built_at": datetime.now().isoformat(),
        "sig": current_sig,
        "count": len(all_items),
        "index": categories_index,   # << store refs only
    }
    session["categorize_ready"] = True
    session.modified = True
    return redirect(url_for("production.production_review"))


@production.get("/review")
def production_review():
    _ensure_session_bucket()
    cache = session.get("categories_cache")

    if not isinstance(cache, dict) or "index" not in cache:
        return redirect(url_for("production.production_categorize"))

    cur = session.get("curation", {})
    index = cache.get("index") or {}
    overrides = session.get("title_overrides") or {}
    sublinks_map = session.get("sublinks") or {}  # <-- NEW: sublinks storage

    # Hydrate
    hydrated = {}
    for label, refs in index.items():
        items = []
        for ref in refs or []:
            resolved = _resolve_ref(ref, cur)
            if not resolved:
                continue

            # copy so we don't mutate store objects when overriding
            item = dict(resolved) if isinstance(resolved, dict) else dict(resolved)
            item["_ref"] = ref
            src = (ref or {}).get("source")
            rid = item.get("id")
            item["_src"] = src  # <-- NEW: keep source handy for the template/JS

            # apply title override if present (keyed by "source:id")
            if src and rid:
                key = f"{src}:{rid}"
                if key in overrides:
                    item["title"] = overrides[key]
                # attach sublinks for UI (list of {"heading","url"})
                item["_sublinks"] = list(sublinks_map.get(key, []))  # <-- NEW

            items.append(item)
        hydrated[label] = items

    # ---- Reorder just-in-time (no session changes, no template changes) ----
    preferred = [SPECIAL_CALENDAR, *CATEGORIES]  # Events first, then your fixed list
    ordered = OrderedDict((lab, hydrated.get(lab, [])) for lab in preferred if lab in hydrated)
    # append any unexpected categories at the end (robust to future additions)
    for lab, items in hydrated.items():
        if lab not in ordered:
            ordered[lab] = items

    return render_template(
        "production_review.html",
        categories=ordered,
        built_at=cache.get("built_at"),
    )


@production.post("/move-article")
def production_move_article():
    """
    Body: { id: str, from_category: str|None, to_category: str, new_index: int }
    Mutates session['categories_cache']['index'] so export sees the new order/category.
    """
    payload = request.get_json(silent=True) or {}
    art_id = (payload.get("id") or "").strip()
    from_cat = payload.get("from_category")
    to_cat = payload.get("to_category")
    new_index = payload.get("new_index")

    if not art_id or not to_cat or new_index is None:
        return jsonify(ok=False, error="Missing id/to_category/new_index"), 400

    _ensure_session_bucket()
    cache = session.get("categories_cache")
    if not isinstance(cache, dict) or "index" not in cache:
        return jsonify(ok=False, error="No category index in session"), 400

    index = cache.get("index") or {}
    # Ensure destination exists
    dest_list = index.setdefault(to_cat, [])

    # 1) Find which string we’re storing in `index` for this article.
    #    Your index stores "refs" (keys used by _resolve_ref). Sometimes `id == ref`,
    #    but to be safe, try to locate by either:
    def _remove_first_match():
        # try exact matches (id == ref)
        for cat, lst in index.items():
            for i, ref in enumerate(lst or []):
                if str(ref) == str(art_id):
                    return cat, lst.pop(i), i
        # if your hydrated items use a separate key, add a resolver here
        return None, None, None

    # Remove from source (if provided), else search globally
    removed_from, ref_value, old_pos = None, None, None
    if from_cat in index:
        lst = index[from_cat] or []
        for i, ref in enumerate(lst):
            if str(ref) == str(art_id):
                removed_from, ref_value, old_pos = from_cat, lst.pop(i), i
                break
    if ref_value is None:
        removed_from, ref_value, old_pos = _remove_first_match()

    if ref_value is None:
        return jsonify(ok=False, error="Article not found in index"), 404

    # 2) Insert into destination at requested position (clamped)
    insert_at = max(0, min(int(new_index), len(dest_list)))
    dest_list.insert(insert_at, ref_value)

    # 3) Persist & optionally bump the built_at to reflect edits
    cache["index"] = index
    cache["built_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session["categories_cache"] = cache
    session.modified = True

    return jsonify(ok=True)


@production.post("/rename-article")
def production_rename_article():
    payload = request.get_json(silent=True) or {}
    src = (payload.get("source") or "").strip()
    rid = (payload.get("id") or "").strip()
    title = (payload.get("title") or "").strip()

    if not src or not rid or not title:
        return jsonify(ok=False, error="Missing source/id/title"), 400

    _ensure_session_bucket()
    overrides = session.get("title_overrides") or {}
    overrides[f"{src}:{rid}"] = title
    session["title_overrides"] = overrides
    session.modified = True
    return jsonify(ok=True)


@production.get("/export-categories-pdf")
def production_export_categories_pdf():
    _ensure_session_bucket()
    cache = session.get("categories_cache") or {}
    index = cache.get("index")
    if not index:
        return redirect(url_for("production.production_categorize"))

    cur = session.get("curation", {})
    overrides    = session.get("title_overrides") or {}   # renamed titles
    sublinks_map = session.get("sublinks") or {}          # { "source:id": [ {heading,url}, ... ] }

    # Hydrate with overrides + sublinks
    hydrated = {}
    for label, refs in index.items():
        items = []
        for ref in refs or []:
            resolved = _resolve_ref(ref, cur)
            if not resolved:
                continue

            item = dict(resolved) if isinstance(resolved, dict) else dict(resolved)
            src = (ref or {}).get("source")
            rid = item.get("id")
            if src and rid:
                key = f"{src}:{rid}"
                if key in overrides:
                    item["title"] = overrides[key]
                item["sublinks"] = list(sublinks_map.get(key, []))
            items.append(item)
        hydrated[label] = items

    # ---- Order categories: Events first, then fixed list; append any extras
    preferred = [SPECIAL_CALENDAR, *CATEGORIES]
    ordered = OrderedDict((lab, hydrated.get(lab, [])) for lab in preferred if lab in hydrated)
    for lab, items in hydrated.items():
        if lab not in ordered:
            ordered[lab] = items

    html = render_template(
        "pdf.html",
        generated_at=datetime.now(),
        categories=ordered,   # pass ordered mapping to the template
    )

    pdf_bytes = HTML(string=html, base_url=request.root_url).write_pdf()
    stamp = datetime.now().strftime("%m/%d")
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'attachment; filename="PolicyCrush_Categories_{stamp}.pdf"'
    return resp


@production.post("/sublink/add")
def production_sublink_add():
    """
    Body: { source: str, id: str, heading: str, url: str }
    Appends a sublink to session['sublinks'][f"{source}:{id}"].
    """
    payload = request.get_json(silent=True) or {}
    src = (payload.get("source") or "").strip()
    rid = (payload.get("id") or "").strip()
    heading = (payload.get("heading") or "").strip()
    url = (payload.get("url") or "").strip()

    if not src or not rid or not heading or not url:
        return jsonify(ok=False, error="Missing source/id/heading/url"), 400

    _ensure_session_bucket()
    sl = session.get("sublinks") or {}
    key = f"{src}:{rid}"
    lst = sl.get(key) or []
    lst.append({"heading": heading, "url": url})
    sl[key] = lst
    session["sublinks"] = sl
    session.modified = True
    return jsonify(ok=True, sublinks=lst)


@production.post("/sublink/remove")
def production_sublink_remove():
    """
    Body: { source: str, id: str, index: int }
    Removes sublink at index.
    """
    payload = request.get_json(silent=True) or {}
    src = (payload.get("source") or "").strip()
    rid = (payload.get("id") or "").strip()
    idx = payload.get("index")
    if not src or not rid or idx is None:
        return jsonify(ok=False, error="Missing source/id/index"), 400

    _ensure_session_bucket()
    sl = session.get("sublinks") or {}
    key = f"{src}:{rid}"
    lst = sl.get(key) or []
    if not (0 <= int(idx) < len(lst)):
        return jsonify(ok=False, error="Index out of range"), 400
    lst.pop(int(idx))
    sl[key] = lst
    session["sublinks"] = sl
    session.modified = True
    return jsonify(ok=True, sublinks=lst)


@production.post("/addevent")
def production_addevent():
    """Create an AddEvent calendar entry for a hearing URL, honoring title overrides when available."""
    payload = request.get_json(silent=True) or {}
    url = (payload.get("url") or "").strip()
    tz = payload.get("timezone") or "America/New_York"
    default_minutes = int(payload.get("duration_minutes") or 60)

    # Optional hints (won't be required; we can infer from URL)
    title_hint = (payload.get("title") or "").strip()
    src_hint = (payload.get("source") or "").strip()
    rid_hint = (payload.get("id") or "").strip()

    if not url:
        return jsonify({"ok": False, "error": "Missing 'url'."}), 400

    # Try to resolve a title override from session
    override_title = None
    try:
        overrides = session.get("title_overrides") or {}

        # 1) If source/id are provided (optional), try that key first
        if src_hint and rid_hint:
            override_title = overrides.get(f"{src_hint}:{rid_hint}")

        # 2) If not found yet, try to infer the (source, id) by matching URL
        if not override_title:
            cur = session.get("curation", {}) or {}

            # Gmail manual entries live in session
            for g in cur.get("gmail") or []:
                if (g.get("url") or "").strip() == url:
                    override_title = overrides.get(f"gmail:{g.get('id')}")
                    if override_title:
                        break

            # News/House/Senate live in the in-memory stores
            if not override_title:
                for src_name, store in (("news", NEWS_STORE), ("house", HOUSE_STORE), ("senate", SENATE_STORE)):
                    for item_id, item in store.items():
                        if (item.get("url") or "").strip() == url:
                            override_title = overrides.get(f"{src_name}:{item_id}")
                            if override_title:
                                break
                    if override_title:
                        break
    except Exception:
        # Non-fatal: just ignore and fallback
        override_title = None

    try:
        # 1) scrape + extract canonical event fields
        page_text = fetch_hearing_html(url)
        info_raw = extract_event_info(page_text)  # JSON string from your model
        info = json.loads(info_raw)

        # 2) combine date + time  (expect "YYYY-MM-DD" and "HH:MM")
        dt_start = datetime.strptime(f"{info['date']} {info['time']}", "%Y-%m-%d %H:%M")
        dt_end = dt_start + timedelta(minutes=default_minutes)

        # 3) choose best title: override > title_hint from client > scraped
        base_title = info.get("title") or ""
        final_title = (override_title or title_hint or base_title).strip()

        # 4) build AddEvent payload (unchanged fields preserved)
        addevent_data = {
            "title": "[AUTO-TEST]" + final_title,
            "datetime_start": dt_start.strftime("%Y-%m-%d %H:%M"),
            "datetime_end": dt_end.strftime("%Y-%m-%d %H:%M"),
            "location": info.get("location") or "",
            "description": url,               # keep the source link
            "timezone": tz,                   # e.g., America/New_York
        }

        # 5) create event
        res = create_event_addevent(addevent_data)
        event_id = res.get("id") or res.get("event", {}).get("id")
        event_url = res.get("url") or res.get("event", {}).get("url") or res.get("link")

        return jsonify({"ok": True, "event_id": event_id, "event_url": event_url})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
