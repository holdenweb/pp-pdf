import pytest
from flask import Flask

from hwpdf import pdf_blueprint


@pytest.fixture
def app():
    """A bare Flask app -- deliberately nothing holdenweb-specific.

    If these tests pass, the package really is self-contained: no site
    templates, no database, no config beyond a secret key.
    """
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test", WTF_CSRF_ENABLED=False)
    app.register_blueprint(pdf_blueprint, url_prefix="/pdf/")
    return app


@pytest.fixture
def client(app):
    return app.test_client()
