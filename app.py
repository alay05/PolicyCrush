from flask import Flask, render_template

from routes.gmail import gmail
from routes.news import news
from routes.senate import senate
# from routes.house import house
from routes.pretty_date import pretty_date

app = Flask(__name__)

app.register_blueprint(gmail)
app.register_blueprint(news)
#app.register_blueprint(house)
app.register_blueprint(senate)
app.jinja_env.filters["pretty_date"] = pretty_date

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
