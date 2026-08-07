"""
booklet.py: Produce an 8-page booklet from a single sheet of
paper printed duplex.
"""
import io
import sys
from itertools import cycle
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
from pdfrw import PdfReader
from pdfrw.buildxobj import pagexobj
from pdfrw.toreportlab import makerl


width, height = A4

transforms = [
	(0, 0.5, 0),
	(0.5, 0.5, 0),
	(1, 0.5, 180),
	(0.5, 0.5, 180)
]

page_layouts = (8, 1, 4, 5), (2, 7, 6, 3)

def make_booklet(in_doc, out_docs=None):
    doc_pages = PdfReader(in_doc).pages
    if out_docs is None:
        out_docs = (io.BytesIO(), io.BytesIO())
    elif len(out_docs) != 2:
        raise ValueError("An out_docs argument to make_booklet did not have two elements")
    # Create an odd an and even side imposed page stream, to which PDF
    # content will be written.
    imp_sides = []
    for out_doc in out_docs:
        imp_sides.append(imp_side := Canvas(out_doc))
        imp_side.setPageSize(A4)
    # Iterate over the pages in groups of eight, each group
    # of original pages being the two sides of a signature.
    for i in range(0, len(doc_pages), 8):
        pages = doc_pages[i:i+8]
        # Odd pages get sides 8, 1, 4 and 5
        # Even pages get sides 2, 7, 6 and 3
        for imp_side, page_numbers in zip(imp_sides, page_layouts):
            page_data = [(k, t) for (k, t) in zip(page_numbers, transforms)]
            # Each of the four pages in the imposed layout has its own
            # transform: x-offset, y-offset and rotation angle. Offsets are
            # multiples of the unit width and length, respectively, and the
            # rotation angle is in degrees.
            for page_number, (x, y, angle) in page_data:
                # The final imposed page may not contain an exact multiple of
                # four original pages, so we simply ignore requests for
                # non-existent original pages, leaving them blank.
                if page_number <= len(pages):
                    orig_page = pages[page_number-1]
                    orig_page = makerl(imp_side, pagexobj(orig_page))
                    imp_side.saveState()
                    imp_side.translate(x*width, y*height)
                    imp_side.rotate(angle)
                    imp_side.scale(0.5, 0.5)
                    imp_side.doForm(orig_page)
                    imp_side.restoreState()
            imp_side.showPage()
    # Save the generated PDFs
    for imp_side in imp_sides:
        imp_side.save()
    # And return them to the caller
    return out_docs

if __name__ == '__main__':
    with open("out_odd.pdf", "wb") as out_f1, open("out_even.pdf", "wb") as out_f2:
        make_booklet(sys.argv[1], (out_f1, out_f2))
