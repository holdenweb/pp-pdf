"""PDF booklet-imposition and page-splitting tools as an installable Flask app.

Install into a site with::

    from hwpdf import pdf_blueprint

    app.register_blueprint(pdf_blueprint, url_prefix="/pdf/")

or let the site discover it through the ``holdenweb.apps`` entry-point group,
whose value resolves to the blueprint itself. Where the app is mounted is the
site's decision, as it is in Django.

Anything this app ever needs doing at registration time goes through
``pdf_blueprint.record_once``, which is Flask's equivalent of Django's
``AppConfig.ready`` -- no bespoke install hook is required.

To wrap these pages in the host site's own furniture, add a template at
``templates/hwpdf/base.html`` containing ``{% extends "your-base.html" %}``.
Flask searches the application's template folder before any blueprint's, so
that file shadows the fallback layout shipped here. The same trick overrides
any other template in this package.
"""

from .views import pdf_blueprint

__all__ = ["pdf_blueprint"]
