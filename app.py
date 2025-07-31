from flask import Flask, render_template
from routes.senate import senate
from routes.gmail import gmail

app = Flask(__name__)
app.register_blueprint(senate)
app.register_blueprint(gmail)

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
