"""Views for the PDF helper utilities: booklet imposition and page splitting.

Nothing here knows which contract installed it. Both hosts settle the same two
config keys before the first request -- podpack through `SiteApp.init`, a plain
Flask app through `record_once` below -- so the view code is written once.
"""
import os
from io import BytesIO
from logging import getLogger
from zipfile import ZipFile

from flask import (Blueprint, current_app, flash, render_template, request,
                   send_file)
import pdfrw
from werkzeug.utils import secure_filename

from .booklet import make_booklet
from .forms import PDFBookletForm, PDFSplitterForm

logger = getLogger(__name__)

# The blueprint's name is also the app's name under podpack, which resolves an
# app's data directory and config namespace from `request.blueprint`. Keep the
# two in step; see the SiteApp in __init__.py.
pdf_blueprint = Blueprint("pp_pdf", __name__, template_folder="templates")

# What these pages extend when no host has said otherwise. Namespaced, like every
# other template here: Flask searches *every* blueprint's templates for a name
# the application itself does not supply, so a `base.html` in this package would
# silently become the site-wide base for a podpack site and reparent every other
# installed app.
STANDALONE_LAYOUT = "pp_pdf/standalone.html"

# The splitter builds its zip entirely in memory, one member per page, so an
# unbounded document is a way to exhaust the process rather than a document we
# cannot read. A site raises or lowers this with `[apps.pp_pdf] max_pages`.
DEFAULT_MAX_PAGES = 200


@pdf_blueprint.record_once
def _defaults(state):
    """Settle this app's configuration at registration time.

    Flask's own deferred-registration hook, which is this package's equivalent of
    Django's ``AppConfig.ready``. ``setdefault`` rather than assignment because a
    host may have decided already: podpack's ``SiteApp.init`` runs before this
    one and points the layout at the site's own chrome.
    """
    state.app.config.setdefault("PP_PDF_BASE_TEMPLATE", STANDALONE_LAYOUT)
    state.app.config.setdefault("PP_PDF_MAX_PAGES", DEFAULT_MAX_PAGES)


@pdf_blueprint.context_processor
def _layout():
    """Tell ``pp_pdf/base.html`` what to extend.

    Registered on the blueprint, so the name is in scope for this app's templates
    and for nothing else in the application.
    """
    return {"pdf_layout": current_app.config["PP_PDF_BASE_TEMPLATE"]}


@pdf_blueprint.route("/", methods=['GET'])
def root_page():
    return render_template("pp_pdf/index.html", title="PDF Helpers")


@pdf_blueprint.route("/booklet", methods=['GET', 'POST'])
def get_or_post_booklet():
    """
    Post-design imposition of A6 booklets from A4 paper.

    This page requests a file from the user, and returns a zipfile containing
    its pages, each shrunk to 50% and imposed four-up on A4. This allows
    creation of a signature from each eight original pages, four-up on an
    even and an odd side.

    The even and odd sides are then written into separate PDF files and
    packed in a zipfile, which is delivered to the user as a downloaded.
    """
    form = PDFBookletForm()
    logger.info("Booklet requested")
    if form.validate_on_submit():
        my_file = request.files['file_details']
        try:
            output_pdfs = make_booklet(my_file.stream)
            outzip = BytesIO()
            container = ZipFile(outzip, 'w')
            for p_typ, pdf in zip(('odd', 'even'), output_pdfs):
                container.writestr(f"pdf/{p_typ}.pdf",
                                   pdf.getvalue())
            container.close()
            outzip.seek(0)
            return send_file(outzip,
                             mimetype="application/zip",
                             as_attachment=True,
                             download_name="pages.zip")
        except Exception as e:
            # Plain text, no markup: a host's layout may escape flashed messages
            # -- podpack's does -- and the message interpolates an exception that
            # can contain the client's own filename.
            logger.exception("booklet imposition failed")
            flash("I'm sorry, it seems I couldn't do that. Please report the "
                  f"following message if it makes no sense to you: {e}")
    return render_template('pp_pdf/booklet_form.html', form=form, title="PDF Booklet Maker")


@pdf_blueprint.route("/pagezip", methods=['GET', 'POST'])
def get_or_post_pagezip():
    form = PDFSplitterForm()
    if form.validate_on_submit():
        in_storage = request.files['file_details']
        # The uploaded name becomes a directory inside the zip and the name of
        # the download, so it is the client's string until sanitised.
        infile_name = os.path.splitext(
            secure_filename(in_storage.filename))[0] or "document"
        file_prefix = request.form['file_prefix'] or 'page'
        try:
            inputpdf = pdfrw.PdfReader(fname=in_storage.stream)
            max_pages = current_app.config["PP_PDF_MAX_PAGES"]
            if len(inputpdf.pages) > max_pages:
                # A refusal rather than an error, and outside the loop, so the
                # bare except below cannot turn it into "not a PDF".
                flash(f"That document has {len(inputpdf.pages)} pages and this "
                      f"tool splits at most {max_pages}.")
                return render_template('pp_pdf/pagesplit_form.html', form=form,
                                       title="PDF Page Splitter")
            outzip = BytesIO()
            container = ZipFile(outzip, 'w')
            for i, page in enumerate(inputpdf.pages):
                output = pdfrw.PdfWriter()
                file_name = f"{file_prefix}_{i+1:03}.pdf"
                output.addpage(page)
                outfile = BytesIO()
                output.write(outfile)
                container.writestr(f"{infile_name}/{file_name}",
                                   outfile.getvalue())
            container.close()
            outzip.seek(0)
            return send_file(outzip,
                             mimetype="application/octet-stream",
                             as_attachment=True,
                             download_name=f"{infile_name}.pages.zip")
        except Exception:
            logger.exception("could not read the upload as a PDF")
            flash("Could not open file as a PDF - please try again")
    return render_template('pp_pdf/pagesplit_form.html', form=form, title="PDF Page Splitter")
