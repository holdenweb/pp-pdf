"""Run the blueprint on a bare Flask app, for local inspection.

Not part of the package -- it exists so the app can be looked at without a
host site, which is also the quickest check that it needs nothing from one.
"""
from flask import Flask

from hwpdf import pdf_blueprint

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-only"
app.register_blueprint(pdf_blueprint, url_prefix="/pdf/")

if __name__ == "__main__":
    app.run(port=8459, debug=True)
