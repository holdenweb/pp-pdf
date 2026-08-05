import io
import zipfile

from flask import Flask
from reportlab.pdfgen.canvas import Canvas

from hwpdf import pdf_blueprint


def _pdf_of(pages):
    """A real, minimal PDF, so the tests exercise pdfrw rather than a stub."""
    buffer = io.BytesIO()
    canvas = Canvas(buffer)
    for _ in range(pages):
        canvas.showPage()
    canvas.save()
    buffer.seek(0)
    return buffer


def test_index_lists_both_tools(client):
    response = client.get("/pdf/")
    assert response.status_code == 200
    assert b"PDF Booklet Maker" in response.data
    assert b"PDF Splitter" in response.data


def test_both_forms_render(client):
    for path in ("/pdf/booklet", "/pdf/pagezip"):
        assert client.get(path).status_code == 200, path


def test_pagezip_returns_one_pdf_per_page(client):
    response = client.post(
        "/pdf/pagezip",
        data={"file_details": (_pdf_of(3), "three.pdf"), "file_prefix": "page"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        assert len(archive.namelist()) == 3


def test_booklet_returns_odd_and_even_sides(client):
    response = client.post(
        "/pdf/booklet",
        data={"file_details": (_pdf_of(8), "eight.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        assert sorted(archive.namelist()) == ["pdf/even.pdf", "pdf/odd.pdf"]


def test_mounts_at_any_prefix():
    """The index's links must survive being mounted somewhere else.

    The original code hardcoded `./booklet` and `./pagezip`, which only worked
    at /pdf/; url_for makes the blueprint genuinely relocatable.
    """
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test")
    app.register_blueprint(pdf_blueprint, url_prefix="/tools/pdf")
    response = app.test_client().get("/tools/pdf/")
    assert response.status_code == 200
    assert b"/tools/pdf/booklet" in response.data


def test_host_site_can_override_the_layout(tmp_path):
    """A site's own templates/hwpdf/base.html must shadow the package's.

    This is the whole override mechanism -- Flask searches the application's
    template folder before any blueprint's -- so it is worth pinning down.
    """
    site_templates = tmp_path / "templates" / "hwpdf"
    site_templates.mkdir(parents=True)
    (site_templates / "base.html").write_text(
        "<!DOCTYPE html><html><body><p>site chrome</p>"
        "{% block content %}{% endblock %}</body></html>"
    )

    app = Flask(__name__, template_folder=str(tmp_path / "templates"))
    app.config.update(TESTING=True, SECRET_KEY="test")
    app.register_blueprint(pdf_blueprint, url_prefix="/pdf/")

    response = app.test_client().get("/pdf/")
    assert response.status_code == 200
    assert b"site chrome" in response.data
