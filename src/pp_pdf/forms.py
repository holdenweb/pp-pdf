from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField, StringField
from wtforms.validators import DataRequired


class PDFBookletForm(FlaskForm):
    file_details = FileField('file_details', validators=[DataRequired()])
    submit = SubmitField("Generate Booklet")


class PDFSplitterForm(FlaskForm):
    file_details = FileField('file_details', validators=[DataRequired()])
    file_prefix = StringField('file_prefix')
    submit = SubmitField('Get Pages')


