import hashlib
from datetime import datetime, date
from features.classify import classify

from sources.messages import authenticate, get_messages, extract_html_from_email

from sources.news.cms_inov import fetch_cms_inov_articles
from sources.news.cms import fetch_cms_articles
from sources.news.crs import fetch_crs_articles
from sources.news.congress import fetch_congress_articles
from sources.news.fda import fetch_fda_articles
from sources.news.fed_reg import fetch_federal_register_articles
from sources.news.hhs import fetch_hhs_articles
from sources.news.whitehouse import fetch_whitehouse_articles
from sources.news.omb import fetch_omb_articles

from sources.house.appropriations_maj import fetch_appr_maj_articles
from sources.house.appropriations_min import fetch_appr_min_articles
from sources.house.budget_maj import fetch_budg_maj_articles
from sources.house.budget_min import fetch_budg_min_articles
from sources.house.education_and_workforce_maj import fetch_eaw_maj_articles
from sources.house.education_and_workforce_min import fetch_eaw_min_articles
from sources.house.energy_and_commerce_maj import fetch_eac_maj_articles
from sources.house.energy_and_commerce_min import fetch_eac_min_articles
from sources.house.homeland_maj import fetch_home_maj_articles
from sources.house.homeland_min import fetch_home_min_articles
from sources.house.joint_economic_maj import fetch_jec_maj_articles
from sources.house.joint_economic_min import fetch_jec_min_articles
from sources.house.judiciary_maj import fetch_jud_maj_articles
from sources.house.judiciary_min import fetch_jud_min_articles
from sources.house.natural_resources_maj import fetch_natr_maj_articles
from sources.house.natural_resources_min import fetch_natr_min_articles
from sources.house.oversight_maj import fetch_ovs_maj_articles
from sources.house.oversight_min import fetch_ovs_min_articles
from sources.house.rules_maj import fetch_rul_maj_articles
from sources.house.rules_min import fetch_rul_min_articles
from sources.house.small_business_maj import fetch_smb_maj_articles
from sources.house.small_business_min import fetch_smb_min_articles
from sources.house.veterans_maj import fetch_vet_maj_articles
from sources.house.veterans_min import fetch_vet_min_articles
from sources.house.ways_and_means_maj import fetch_wam_maj_articles
from sources.house.ways_and_means_min import fetch_wam_min_articles

from sources.senate.aging import fetch_age_articles
from sources.senate.appropriations import fetch_appr_articles
from sources.senate.budget import fetch_budg_articles
from sources.senate.finance import fetch_fin_articles
from sources.senate.help import fetch_help_articles
from sources.senate.homeland import fetch_home_articles
from sources.senate.indian import fetch_ind_articles
from sources.senate.judiciary import fetch_jud_articles
from sources.senate.small_business import fetch_smb_articles
from sources.senate.veterans import fetch_vet_articles


def fetch_gmail_unread():
    service = authenticate()
    messages = get_messages(service)
    out = []
    for msg in messages:
        subject, html = extract_html_from_email(service, msg["id"])
        if html:
            out.append({
                "id": msg["id"],
                "title": subject or "(no subject)",
                "url": "",
                "date": "",
                "html": html,
                "source": "gmail",
            })
    return out


NEWS = {
    "CMS": fetch_cms_articles,
    "CMS Innovation Center": fetch_cms_inov_articles,
    "CRS": fetch_crs_articles,
    "Congress": fetch_congress_articles,
    "FDA": fetch_fda_articles,
    "Federal Register Public Inspection Desk": fetch_federal_register_articles,
    "HHS": fetch_hhs_articles,
    "OMB First Glance Rulemaking": fetch_omb_articles,
    "White House": fetch_whitehouse_articles,
}

def _shift_back_one_day(d):
    try:
        if isinstance(d, datetime.datetime):
            return d - datetime.timedelta(days=1)
        if isinstance(d, datetime.date):
            return d - datetime.timedelta(days=1)
        if isinstance(d, str) and d:
            # try ISO first
            try:
                dt = datetime.datetime.fromisoformat(d.replace("Z", "+00:00"))
                newdatetime = dt - datetime.timedelta(days=1)
                # preserve datetime vs date-like string
                if "T" in d or ":" in d:
                    return newdatetime.isoformat()
                return newdatetime.date().isoformat()
            except ValueError:
                # fallback: YYYY-MM-DD
                dt = datetime.datetime.strptime(d, "%Y-%m-%d")
                return (dt.date() - datetime.timedelta(days=1)).isoformat()
    except Exception:
        pass
    return d

def _aid(url: str, source: str) -> str:
    return hashlib.sha1(f"{source}|{url}".encode("utf-8")).hexdigest()[:16]

def fetch_news_bundle(start_date: datetime.date, use_openai: bool = False):
    out = {}
    for name, fetch in NEWS.items():
        try:
            payload = fetch(start_date)
            items = []
            for art in payload.get("articles", []):
                date_val = art.get("date", "")
                if name == "Congress" and date_val:               
                    date_val = _shift_back_one_day(date_val)
                item = {
                    "id": _aid(art["url"], name),
                    "title": art["title"],
                    "url": art["url"],
                    "date": date_val,
                    "source": name,
                }
                if "suggestion" in art and art["suggestion"]:
                    item["suggestion"] = art["suggestion"]
                elif use_openai:
                    item["suggestion"] = classify(item["title"])
                items.append(item)
            out[name] = {"url": payload.get("url", ""), "items": items}
        except Exception:
            continue
    return out


HOUSE = {
    "Appropriations": {"majority": fetch_appr_maj_articles, "minority": fetch_appr_min_articles},
    "Budget": {"majority": fetch_budg_maj_articles, "minority": fetch_budg_min_articles},
    "Education and Workforce": {"majority": fetch_eaw_maj_articles, "minority": fetch_eaw_min_articles},
    "Energy and Commerce (E&C)": {"majority": fetch_eac_maj_articles, "minority": fetch_eac_min_articles},
    "Homeland Security": {"majority": fetch_home_maj_articles, "minority": fetch_home_min_articles},
    "Joint Economic": {"majority": fetch_jec_maj_articles, "minority": fetch_jec_min_articles},
    "Judiciary": {"majority": fetch_jud_maj_articles, "minority": fetch_jud_min_articles},
    "Natural Resources": {"majority": fetch_natr_maj_articles, "minority": fetch_natr_min_articles},
    "Oversight": {"majority": fetch_ovs_maj_articles, "minority": fetch_ovs_min_articles},
    "Rules": {"majority": fetch_rul_maj_articles, "minority": fetch_rul_min_articles},
    "Small Business": {"majority": fetch_smb_maj_articles, "minority": fetch_smb_min_articles},
    "Veterans Affairs": {"majority": fetch_vet_maj_articles, "minority": fetch_vet_min_articles},
    "Ways and Means": {"majority": fetch_wam_maj_articles, "minority": fetch_wam_min_articles},
}

def _hid(url: str, committee: str, side: str) -> str:
    return hashlib.sha1(f"{committee}|{side}|{url}".encode("utf-8")).hexdigest()[:16]

def fetch_house_bundle(start_date: datetime.date, use_openai: bool = False):
    out = {}
    for committee, fns in HOUSE.items():
        try:
            maj = fns["majority"](start_date)
            mino = fns["minority"](start_date)

            def norm(items, side):
                res = []
                for a in items:
                    item = {
                        "id": _hid(a["url"], committee, side),
                        "title": a["title"],
                        "url": a["url"],
                        "date": a.get("date", ""),
                        "committee": committee,
                        "side": side,
                    }
                    if "suggestion" in a and a["suggestion"]:
                        item["suggestion"] = a["suggestion"]
                    elif use_openai:
                        item["suggestion"] = classify(item["title"])
                    res.append(item)
                return res

            out[committee] = {
                "majority": norm(maj, "majority"),
                "minority": norm(mino, "minority"),
            }
        except Exception:
            continue
    return out


SENATE = {
    "Aging": fetch_age_articles,
    "Appropriations": fetch_appr_articles,
    "Budget": fetch_budg_articles,
    "Finance": fetch_fin_articles,
    "Health, Education, Labor & Pensions (HELP)": fetch_help_articles,
    "Homeland Security and Governmental Affairs (Oversight)": fetch_home_articles,
    "Indian Affairs": fetch_ind_articles,
    "Judiciary": fetch_jud_articles,
    "Veterans Affairs": fetch_vet_articles,
    "Small Business": fetch_smb_articles,
}

def _sid(url: str, committee: str, tag: str) -> str:
    return hashlib.sha1(f"{committee}|{tag}|{url}".encode("utf-8")).hexdigest()[:16]

def fetch_senate_bundle(start_date: datetime.date, use_openai: bool = False):
    out = {}
    for name, fetch in SENATE.items():
        try:
            payload = fetch(start_date)  # {"articles":[{title,url,date,tag?}], "base_url": "..."}
            base_url = payload.get("base_url", "")
            majority, minority, hearing = [], [], []

            for art in payload.get("articles", []):
                tag = art.get("tag", "")
                item = {
                    "id": _sid(art["url"], name, tag or "article"),
                    "title": art["title"],
                    "url": art["url"],
                    "date": art["date"].isoformat() if isinstance(art.get("date"), (date, datetime)) else art.get("date", ""),
                    "committee": name,
                    "tag": tag or "article",
                }
                if "suggestion" in art and art["suggestion"]:
                    item["suggestion"] = art["suggestion"]
                elif use_openai:
                    item["suggestion"] = classify(item["title"])

                if tag == "majority":
                    majority.append(item)
                elif tag == "minority":
                    minority.append(item)
                elif tag == "hearing":
                    hearing.append(item)
                else:
                    majority.append(item)

            out[name] = {"url": base_url, "majority": majority, "minority": minority, "hearing": hearing}
        except Exception:
            continue
    return out

