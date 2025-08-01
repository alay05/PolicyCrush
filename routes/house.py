from flask import Blueprint, render_template, request
from datetime import datetime, timedelta

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

from logic.classify import classify

house = Blueprint("house", __name__)

HOUSE = {
    "Appropriations": {
        "majority": fetch_appr_maj_articles,
        "minority": fetch_appr_min_articles,
    },
    "Budget": {
        "majority": fetch_budg_maj_articles,
        "minority": fetch_budg_min_articles,
    },
    "Education and Workforce": {
        "majority": fetch_eaw_maj_articles,
        "minority": fetch_eaw_min_articles,
    },
    "Energy and Commerce (E&C)": {
        "majority": fetch_eac_maj_articles,
        "minority": fetch_eac_min_articles,
    },
    "Homeland Security": {
        "majority": fetch_home_maj_articles,
        "minority": fetch_home_min_articles,
    },
    "Joint Economic": {
        "majority": fetch_jec_maj_articles,
        "minority": fetch_jec_min_articles,
    },
    "Judiciary": {
        "majority": fetch_jud_maj_articles,
        "minority": fetch_jud_min_articles,
    },
    "Natural Resources": {
        "majority": fetch_natr_maj_articles,
        "minority": fetch_natr_min_articles,
    },
    "Oversight": {
        "majority": fetch_ovs_maj_articles,
        "minority": fetch_ovs_min_articles,
    },
    "Rules": {
        "majority": fetch_rul_maj_articles,
        "minority": fetch_rul_min_articles,
    },
    "Small Business": {
        "majority": fetch_smb_maj_articles,
        "minority": fetch_smb_min_articles,
    },
    "Veterans Affairs": {
        "majority": fetch_vet_maj_articles,
        "minority": fetch_vet_min_articles,
    },
    "Ways and Means": {
        "majority": fetch_wam_maj_articles,
        "minority": fetch_wam_min_articles,
    },
}

@house.route("/house", methods=["GET", "POST"])
def house_view():
    input_date = (datetime.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = None
    error = None
    committees = {}
    use_openai = False

    if request.method == "POST":
        input_date = request.form.get("start_date", "").strip()
        use_openai = "use_openai" in request.form

        if input_date:
            try:
                start_date = datetime.strptime(input_date, "%Y-%m-%d").date()
            except ValueError:
                error = "Invalid date."

        if not error and start_date:
            for name, fetch in HOUSE.items():
                try:
                    maj_articles = fetch["majority"](start_date)
                    min_articles = fetch["minority"](start_date)

                    committees[name] = {
                        "majority": maj_articles,
                        "minority": min_articles,
                    }

                    if use_openai:
                      for article in maj_articles:
                          print("classifying")
                          article["suggestion"] = classify(article["title"])
                      for article in min_articles:
                          print("classifying")
                          article["suggestion"] = classify(article["title"])
                        
                except Exception as e:
                    print(f"Error loading {name}: {e}")

    return render_template("house.html", committees=committees, error=error, input_date=input_date, use_openai=use_openai)
