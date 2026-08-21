"""Conformance with the podpack plugin API.

Skipped where podpack is not importable. This package's first contract is to be
a plain Flask blueprint, so its own suite has to pass on a machine that has never
heard of the framework -- which is also what keeps the standalone half honest.

To run these, put the sibling checkout in the venv without putting it in the
lock file, which would make it mandatory for everyone::

    uv pip install -e ../podpack

Deliberately not in conftest.py: a conftest importing podpack would be imported
at collection time and break the whole suite where podpack is absent.
"""

import sys

import pytest

# Kept as a guard for `--no-dev` runs, where the dev group is absent. It no
# longer fires for an ordinary `uv sync`: podpack is locked from its
# repository rather than opted into by hand.
pytest.importorskip("podpack", reason="podpack is a dev dependency; run without --no-dev")

from podpack import Section, SiteApp, app_config, create_app  # noqa: E402

from pp_pdf import pdf_blueprint, site_app  # noqa: E402
from pp_pdf.views import DEFAULT_MAX_PAGES  # noqa: E402

# The kind of dict that would otherwise be read from the site's mounted TOML
# file. Note that `apps` holds the *import* name while `[apps.…]` is keyed by the
# app's own name; they are the same word here only because this app chose to make
# them so.
HOST_CONFIG = {
    "site": {"name": "test site", "environment": "test", "apps": ["pp_pdf"]},
    "apps": {"pp_pdf": {"max_pages": 7}},
}


@pytest.fixture
def site(monkeypatch, tmp_path):
    """Build a real podpack site with this app installed, as the framework would.

    Secrets come from the environment in production and `create_app` insists on
    them. The roots are throwaway directories so that the registry's per-app
    mkdir and log-handler wiring run for real rather than being stubbed out.
    """
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    # Required since podpack 0.5.2, when login became core: podpack refuses
    # to boot without it, whether or not the site or this app uses login.
    monkeypatch.setenv("SECURITY_PASSWORD_SALT", "test-password-salt")

    def _build(**overrides):
        host_config = {**HOST_CONFIG, **overrides.pop("host_config", {})}
        return create_app(
            host_config=host_config,
            data_root=tmp_path / "data",
            log_root=tmp_path / "logs",
            **overrides,
        )

    return _build


@pytest.fixture
def app(site):
    return site()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def site_package(tmp_path):
    """An importable stand-in site package with the given templates.

    A real site is a package with its own `templates/`, and template
    precedence cannot be tested without one -- which is the whole reason the
    hijack test below needs it.
    """
    created = []

    def _make(name, templates):
        root = tmp_path / name
        (root / "templates").mkdir(parents=True)
        (root / "__init__.py").write_text("")
        for path, content in templates.items():
            target = root / "templates" / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        created.append(name)
        if str(tmp_path) not in sys.path:
            sys.path.insert(0, str(tmp_path))
        return name

    yield _make

    for name in created:
        sys.modules.pop(name, None)
    if str(tmp_path) in sys.path:
        sys.path.remove(str(tmp_path))


def test_site_app_conforms():
    assert isinstance(site_app, SiteApp)
    assert site_app.blueprint is pdf_blueprint
    # podpack derives the app's name from the blueprint, so this is the name
    # that decides the template namespace, the data directory and the config
    # section. It used to be declared separately here and had to be kept in
    # step by hand; asserting it is now the framework's job, not this app's.
    assert site_app.name == "pp_pdf"


def test_installs_from_the_app_list_alone(client):
    """The whole point of the framework: a line of config, not a line of code."""
    response = client.get("/pdf/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "PDF Booklet Maker" in body
    assert "PDF Splitter" in body


def test_every_page_renders(client):
    for path in ("/pdf/", "/pdf/booklet", "/pdf/pagezip"):
        assert client.get(path).status_code == 200, path


def test_pages_wear_the_sites_chrome(app, client):
    """The layout must resolve to the site's base.html, not the one shipped here."""
    assert app.config["PP_PDF_BASE_TEMPLATE"] == "base.html"
    body = client.get("/pdf/").get_data(as_text=True)
    assert "Served by podpack" in body          # podpack's own default chrome
    assert "pp-pdf standalone layout" not in body


def test_does_not_hijack_the_sites_base_template(site, site_package):
    """Installing this app must not change how the rest of the site renders.

    podpack searches site templates, then every blueprint's, then its own
    defaults -- so an app shipping a top-level `base.html` would beat
    podpack's fallback and quietly become the base for every other installed
    app on any site that has not written a `base.html` of its own.

    Which is why this builds a site package that deliberately has no
    `base.html`. The earlier version of this test passed `create_app` no
    `site_package` at all, and in that configuration podpack *is* the Flask
    application -- `Flask(site_package or __name__)` -- so its own templates
    are the application's and are searched before any blueprint's. The hijack
    could not happen, the test could not fail, and it was checked by shipping
    the exact offending file and watching it pass anyway.
    """
    built = site(site_package=site_package("faux_site", {"faux/marker.html": "x"}))
    body = built.test_client().get("/").get_data(as_text=True)

    assert "Served by podpack" in body


def test_nav_entry_is_contributed_and_actually_resolves(app, client):
    """The endpoint has to exist, or podpack refuses to boot the whole site."""
    assert app.extensions["podpack"].nav == [Section("PDF tools", "pp_pdf.root_page")]
    assert 'href="/pdf/"' in client.get("/").get_data(as_text=True)


def test_the_site_can_mount_this_app_where_it_likes(site):
    """`url_prefix` is what this app asks for, not what it is entitled to.

    The standalone contract has always let the host choose the mount point; this
    is the podpack equivalent, and the nav entry follows for free because it
    names an endpoint rather than a path.
    """
    app = site(
        host_config={
            "site": {
                **HOST_CONFIG["site"],
                # Site policy, so it lives here rather than in `[apps.pp_pdf]`;
                # this app never sees where it was put.
                "mounts": {"pp_pdf": "/tools/pdf"},
            }
        }
    )
    client = app.test_client()

    assert client.get("/tools/pdf/").status_code == 200
    assert client.get("/pdf/").status_code == 404
    body = client.get("/tools/pdf/").get_data(as_text=True)
    assert "/tools/pdf/booklet" in body                      # the app's own links
    assert 'href="/tools/pdf/"' in client.get("/").get_data(as_text=True)  # the nav


def test_per_app_directories_are_named_after_the_app(app):
    state = app.extensions["podpack"]
    assert (state.data_root / "pp_pdf").is_dir()
    assert (state.log_root / "pp_pdf").is_dir()


def test_max_pages_comes_from_the_site_config(app):
    """Where the name invariant actually bites: a mismatch returns {} in silence."""
    with app.test_request_context("/pdf/"):
        assert app_config() == {"max_pages": 7}
    assert app.config["PP_PDF_MAX_PAGES"] == 7


def test_a_site_without_the_setting_gets_the_packaged_default(site):
    """`[apps.pp_pdf]` is optional; the app must boot without it."""
    app = site(host_config={"apps": {}})
    assert app.config["PP_PDF_MAX_PAGES"] == DEFAULT_MAX_PAGES
