"""PDF booklet-imposition and page-splitting tools as an installable Flask app.

The package answers to two contracts and requires neither.

**As a plain Flask blueprint**, for a site with no framework at all::

    from pp_pdf import pdf_blueprint

    app.register_blueprint(pdf_blueprint, url_prefix="/pdf/")

or let the site discover it through the ``holdenweb.apps`` entry-point group,
whose value resolves to the blueprint itself. Where it is mounted is the site's
decision, as it is in Django. Anything needed at registration time goes through
``pdf_blueprint.record_once``, Flask's equivalent of Django's
``AppConfig.ready`` -- no bespoke install hook is required.

**As a podpack app**, by adding this package's import name to ``apps`` in the
site's config file::

    [site]
    apps = ["pp_pdf"]

    [apps.pp_pdf]
    max_pages = 200

podpack reads ``site_app`` below and takes the mount point, the nav entry and the
config namespace from it.

The two coexist because the podpack half is a config translator, not a second
code path: both hosts settle ``PP_PDF_BASE_TEMPLATE`` and ``PP_PDF_MAX_PAGES``
before the first request, and the views read only those. So the pages wear the
site's own chrome under podpack, and a complete layout of their own without it.
A host of either kind can also override any template in this package by shipping
a file at the same path -- Flask searches the application's template folder
before any blueprint's, so ``templates/pp_pdf/base.html`` simply wins.
"""

from importlib.util import find_spec

from .views import pdf_blueprint

__all__ = ["pdf_blueprint", "site_app"]


def _init(app):
    """podpack's registration hook: adapt this app to the site installing it.

    Runs before the blueprint is registered, so these defaults land ahead of the
    blueprint's own and win. Under podpack ``base.html`` always resolves -- to
    the site's chrome if it ships any, and to podpack's default if it does not.
    """
    from podpack import app_config

    # `app_config` resolves the app from `request.blueprint` when called without
    # a name; there is no request here, so name it. It needs an app context
    # either way, and the registry pushes none.
    with app.app_context():
        settings = app_config("pp_pdf")

    app.config.setdefault("PP_PDF_BASE_TEMPLATE", "base.html")
    if "max_pages" in settings:
        app.config["PP_PDF_MAX_PAGES"] = settings["max_pages"]


# podpack is optional and deliberately so: it is on no index, and this package's
# first contract is to need no framework at all. `find_spec` rather than
# `except ImportError` for the reason podpack's own registry gives for the same
# choice -- a genuine failure *inside* podpack, a typo or a missing dependency,
# must not be mistaken for its absence. Swallowing one would leave `site_app` as
# None and produce a baffling "exposes no module-level site_app" from the
# registry in place of the real traceback.
if find_spec("podpack") is None:
    site_app = None
else:
    from podpack import Section, SiteApp

    site_app = SiteApp(
        # `name` is the blueprint's own name, because podpack resolves this app's
        # data directory and config namespace from `request.blueprint`. Nothing
        # checks that they agree; if they diverge, both go quietly wrong.
        name="pp_pdf",
        blueprint=pdf_blueprint,
        # Where this app asks to be mounted. A site that wants it elsewhere
        # says so with `url_prefix` in `[apps.pp_pdf]`, and the nav entry below
        # follows without either side restating it, because it names an
        # endpoint rather than a path.
        url_prefix="/pdf",
        nav=(Section("PDF tools", "pp_pdf.root_page"),),
        init=_init,
    )
