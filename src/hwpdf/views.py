"""
pdf.py: Various bits of PDF functionality
"""
from io import BytesIO
from logging import getLogger
from zipfile import ZipFile

from booklet import make_booklet
from flask_wtf import FlaskForm
from flask import (Blueprint, Flask, Response, render_template, flash,
                   send_file, redirect, request, url_for)
import pdfrw
from wtforms import FileField, SubmitField, StringField
from wtforms.validators import DataRequired

logger = getLogger(__name__)
pdf_blueprint = Blueprint("PDF Handling", __name__)


class BookletForm(FlaskForm):
    file_details = FileField('file_details', validators=[DataRequired()])
    submit = SubmitField("Generate Booklet")


class PDF_Form(FlaskForm):
    file_details = FileField('file_details', validators=[DataRequired()])
    file_prefix = StringField('file_prefix')
    submit = SubmitField('Get Pages')

@pdf_blueprint.route("/", methods=['GET'])
def root_page():
    return Response("Here are some PDF things you can do!")

@pdf_blueprint.route("/pagezip", methods=['GET', 'POST'])
def get_or_post_pagezip():
    form = PDF_Form()
    if form.validate_on_submit():
        my_file = request.files['file_details']
        file_prefix = request.form['file_prefix'] or 'page'
        try:
            inputpdf = pdfrw.PdfReader(fname=my_file.stream)
            outzip = BytesIO()
            container = ZipFile(outzip, 'w')
            for i, page in enumerate(inputpdf.pages):
                output = pdfrw.PdfWriter()
                file_name = f"{file_prefix}_{i+1:03}.pdf"
                output.addpage(page)
                outfile = BytesIO()
                output.write(outfile)
                container.writestr(f"pdf/{file_name}",
                                   outfile.getvalue())
            container.close()
            outzip.seek(0)
            return send_file(outzip,
                             mimetype="application/octet-stream",
                             as_attachment=True,
                             download_name="pages.zip")
        except Exception:
            flash(f"Could not open file as a PDF - please try again")
            raise
    return render_template('pagesplit_form.html', form=form)


@pdf_blueprint.route("/booklet", methods=['GET', 'POST'])
def get_or_post_booklet():
    """
    Post-design imposition of A6 booklets from A4 paper.

    This page requests a file from the user, and returns a zipfile containing
    its pages, shrunk to 50% and imposed four-up on A4. This allows creation
    of a signature from each eight original pages, four-up on an even and an
    odd side.

    The even and odd sides are then written into separate PDF files and
    packed in a zipfile, which is delivered to the user as a downloaded.
    """
    form = BookletForm()
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
            return f"""\
I'm sorry, it seems I couldn't do that.
Please report the following message if it makes no sense to you:
{e}"""
    return render_template('booklet_form.html', form=form)
