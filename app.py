from flask import Flask, render_template

from routes.gmail import gmail
from routes.news import news
from routes.senate import senate
from routes.house import house
from routes.add_event import add_event
from routes.add_event_pull import add_event_pull

from production.routes import production

from features.pretty_date import pretty_date

app = Flask(__name__)

app.register_blueprint(gmail)
app.register_blueprint(news)
app.register_blueprint(house)
app.register_blueprint(senate)
app.register_blueprint(add_event)
app.register_blueprint(add_event_pull)

app.register_blueprint(production, url_prefix="/production")

app.jinja_env.filters["pretty_date"] = pretty_date

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)