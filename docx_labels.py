"""
docx_labels.py

Native Microsoft Word label generator for the
Cochise County Master Gardener Association Seed Library.

Designed as a drop-in companion to generate_labels_pdf().

Requires:
    python-docx

Returns:
    bytes suitable for st.download_button()
"""

from io import BytesIO

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import (
    WD_ALIGN_PARAGRAPH,
    WD_BREAK,
)
from docx.enum.table import (
    WD_TABLE_ALIGNMENT,
    WD_CELL_VERTICAL_ALIGNMENT,
)
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


##############################################################################
# Avery 94207 constants
##############################################################################

PAGE_WIDTH = 8.5
PAGE_HEIGHT = 11.0

LEFT_MARGIN = 0.25
RIGHT_MARGIN = 0.25
TOP_MARGIN = 0.50
BOTTOM_MARGIN = 0.50

LABEL_WIDTH = 4.0
LABEL_HEIGHT = 2.0

ROWS = 5
COLS = 2
LABELS_PER_PAGE = ROWS * COLS

##############################################################################
# Fonts
##############################################################################

TITLE_SIZE = 10
FAMILY_SIZE = 10
VARIETY_SIZE = 10
BODY_SIZE = 9
SMALL_SIZE = 8
TINY_SIZE = 7

GREEN = RGBColor(34, 85, 34)
RED = RGBColor(180, 0, 0)
BLACK = RGBColor(0, 0, 0)

##############################################################################
# XML helper functions
##############################################################################

def _set_row_height(row, height_inches):
    """
    Force an exact row height.
    """
    trPr = row._tr.get_or_add_trPr()

    h = OxmlElement("w:trHeight")
    h.set(qn("w:val"), str(int(height_inches * 1440)))
    h.set(qn("w:hRule"), "exact")

    trPr.append(h)


def _set_cell_width(cell, width_inches):
    """
    Fix cell width.
    """
    cell.width = Inches(width_inches)


def _remove_cell_margins(cell):
    """
    Remove Word's default internal padding.
    """
    tcPr = cell._tc.get_or_add_tcPr()

    tcMar = tcPr.first_child_found_in("w:tcMar")

    if tcMar is None:
        tcMar = OxmlElement("w:tcMar")
        tcPr.append(tcMar)

    for side in ("top", "bottom", "left", "right"):

        node = tcMar.find(qn(f"w:{side}"))

        if node is None:
            node = OxmlElement(f"w:{side}")
            tcMar.append(node)

        node.set(qn("w:w"), "0")
        node.set(qn("w:type"), "dxa")


##############################################################################
# Paragraph helpers
##############################################################################

def _new_paragraph(cell):
    """
    Create a paragraph with zero spacing.
    """
    p = cell.add_paragraph()

    fmt = p.paragraph_format

    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    fmt.line_spacing = 1.0

    return p


def _add_text(
    cell,
    text,
    *,
    size=9,
    bold=False,
    italic=False,
    color=BLACK,
    align=WD_ALIGN_PARAGRAPH.LEFT,
):
    """
    Add one formatted paragraph.
    """
    if not text:
        return None

    p = _new_paragraph(cell)

    p.alignment = align

    run = p.add_run(str(text))

    run.bold = bold
    run.italic = italic

    run.font.name = "Arial"
    run.font.size = Pt(size)
    run.font.color.rgb = color

    return p


##############################################################################
# Cell initialization
##############################################################################

def _clear_cell(cell):
    """
    Remove default paragraph and prepare cell.
    """
    cell.text = ""

    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

    _remove_cell_margins(cell)


##############################################################################
# Field helpers
##############################################################################

def _value(row, key):
    """
    Safe string lookup.
    """
    return (row.get(key) or "").strip()


def _has_text(value):
    return bool(value and value.strip())


##############################################################################
# Label list builder
##############################################################################

def _build_label_list(label_data, include_background=False):
    """
    Returns:

        [
            (row, False),
            (row, False),
            (row, True),
            ...
        ]
    """

    labels = []

    for row, qty in label_data:

        for _ in range(qty):
            labels.append((row, False))

        if include_background:

            bg = _value(row, "BackgroundInfo")

            if bg:

                for _ in range(qty):
                    labels.append((row, True))

    return labels

##############################################################################
# Document setup
##############################################################################

def _setup_document():
    """
    Create a Word document configured for Avery 94207 labels.
    """
    document = Document()

    section = document.sections[0]

    section.page_width = Inches(PAGE_WIDTH)
    section.page_height = Inches(PAGE_HEIGHT)

    section.left_margin = Inches(LEFT_MARGIN)
    section.right_margin = Inches(RIGHT_MARGIN)

    section.top_margin = Inches(TOP_MARGIN)
    section.bottom_margin = Inches(BOTTOM_MARGIN)

    return document


##############################################################################
# Table formatting
##############################################################################

def _prepare_table(table):
    """
    Configure one 5x2 label table.
    """

    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    try:
        table.allow_autofit = False
    except AttributeError:
        pass

    for column in table.columns:
        for cell in column.cells:
            _set_cell_width(cell, LABEL_WIDTH)

    for row in table.rows:

        _set_row_height(row, LABEL_HEIGHT)

        for cell in row.cells:

            _clear_cell(cell)


##############################################################################
# Page creation
##############################################################################

def _create_page(document):
    """
    Add one Avery page (5 rows x 2 columns).

    Returns
    -------
    table
        Prepared table ready to receive labels.
    """

    table = document.add_table(
        rows=ROWS,
        cols=COLS,
    )

    _prepare_table(table)

    return table


##############################################################################
# Cell lookup
##############################################################################

def _label_cell(table, slot):
    """
    Convert a label slot number (0-9)
    into the appropriate table cell.

    0 1
    2 3
    4 5
    6 7
    8 9
    """

    row = slot // COLS
    col = slot % COLS

    return table.cell(row, col)


##############################################################################
# Page iterator
##############################################################################

def _page_chunks(labels):
    """
    Yield one page of labels at a time.
    """

    for start in range(0, len(labels), LABELS_PER_PAGE):

        yield labels[start:start + LABELS_PER_PAGE]


##############################################################################
# Main page builder
##############################################################################

def _build_document(document, labels):
    """
    Create all document pages.

    Rendering of individual labels is delegated to
    _draw_seed_label() and _draw_background_label(),
    which are implemented in later sections.
    """

    first_page = True

    for page in _page_chunks(labels):

        if not first_page:
            document.add_page_break()

        first_page = False

        table = _create_page(document)

        for slot, (row, is_background) in enumerate(page):

            cell = _label_cell(table, slot)

            if is_background:
                _draw_background_label(cell, row)
            else:
                _draw_seed_label(cell, row)


##############################################################################
# Standard seed label
##############################################################################

def _draw_seed_label(cell, row):
    """
    Render one standard seed label.
    """

    _clear_cell(cell)

    # ------------------------------------------------------------------
    # Extract fields
    # ------------------------------------------------------------------

    family = _value(row, "Family")
    variety = _value(row, "Variety")
    season = _value(row, "Season")
    edible = _value(row, "Edible")
    year = _value(row, "Year")
    num = _value(row, "NumSeeds")
    saver = _value(row, "SeedSaverLevel")
    germ = _value(row, "Germination")
    soil = _value(row, "SoilTemperature")
    hybrid = _value(row, "HybridDoNotSave")
    comments = _value(row, "Comments")

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    p = _new_paragraph(cell)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    run = p.add_run(
        "Cochise County Master Gardener Association"
    )
    run.bold = True
    run.font.size = Pt(TITLE_SIZE)
    run.font.color.rgb = GREEN
    run.font.name = "Arial"

    run = p.add_run()
    run.add_break()

    run = p.add_run("Seed Library")
    run.bold = True
    run.font.size = Pt(TITLE_SIZE)
    run.font.color.rgb = GREEN
    run.font.name = "Arial"

    # ------------------------------------------------------------------
    # Divider
    # ------------------------------------------------------------------

    # p = _new_paragraph(cell)

    # run = p.add_run(
    #    "────────────────────────────────"
    )
    #
    run.font.size = Pt(6)
    run.font.color.rgb = BLACK

    # ------------------------------------------------------------------
    # Main table
    #
    # Two columns:
    #
    # +----------------------+-------------+
    # | left                 | right       |
    # +----------------------+-------------+
    #
    # ------------------------------------------------------------------

    inner = cell.add_table(
        rows=1,
        cols=2,
    )

    inner.autofit = False
    inner.alignment = WD_TABLE_ALIGNMENT.CENTER

    left = inner.cell(0, 0)
    right = inner.cell(0, 1)

    _clear_cell(left)
    _clear_cell(right)

    _set_cell_width(left, 2.60)
    _set_cell_width(right, 1.20)

    left.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
    right.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

    # ------------------------------------------------------------------
    # LEFT COLUMN
    # ------------------------------------------------------------------

    if family:

        _add_text(
            left,
            family,
            size=FAMILY_SIZE,
            bold=True,
            color=RED,
        )

    if variety:

        _add_text(
            left,
            variety,
            size=VARIETY_SIZE,
            italic=True,
        )

    # Hybrid warning

    if hybrid:

        p = _new_paragraph(left)

        run = p.add_run(
            "* HYBRID — DO NOT SAVE SEEDS *"
        )

        run.bold = True
        run.font.size = Pt(TINY_SIZE)
        run.font.color.rgb = RGBColor(183, 28, 28)
        run.font.name = "Arial"

    # Comments

    if comments:

        comments = " ".join(comments.split())

        _add_text(
            left,
            comments[:300],
            size=BODY_SIZE,
        )

    # ------------------------------------------------------------------
    # RIGHT COLUMN
    # ------------------------------------------------------------------

    if year:

        _add_text(
            right,
            year,
            size=BODY_SIZE,
            bold=False,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

    if edible:

        _add_text(
            right,
            edible.upper(),
            size=BODY_SIZE,
            bold=False,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

    if season:

        _add_text(
            right,
            season,
            size=BODY_SIZE,
            italic=True,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

    if num:

        _add_text(
            right,
            f"{num} Seeds",
            size=BODY_SIZE,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

    if saver:

        _add_text(
            right,
            saver,
            size=TINY_SIZE,
            bold=True,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

    if germ:

        _add_text(
            right,
            f"Germ: {germ}",
            size=SMALL_SIZE,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

    if soil:

        _add_text(
            right,
            f"Soil: {soil}",
            size=SMALL_SIZE,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

    # ------------------------------------------------------------------
    # Keep label together
    # ------------------------------------------------------------------

    for paragraph in cell.paragraphs:

        fmt = paragraph.paragraph_format

        fmt.keep_together = True
        fmt.keep_with_next = False

##############################################################################
# Background information label
##############################################################################

def _draw_background_label(cell, row):
    """
    Render one Background Information label.
    """

    _clear_cell(cell)

    family = _value(row, "Family")
    variety = _value(row, "Variety")
    background = _value(row, "BackgroundInfo")

    # --------------------------------------------------------------
    # Family
    # --------------------------------------------------------------

    if family:

        _add_text(
            cell,
            family,
            size=FAMILY_SIZE,
            bold=True,
            color=BLACK,
        )

    # --------------------------------------------------------------
    # Title
    # --------------------------------------------------------------

    title = variety

    if title:
        title += " — Background Information"
    else:
        title = "Background Information"

    _add_text(
        cell,
        title,
        size=BODY_SIZE,
        bold=True,
    )

    # Blank line

    _new_paragraph(cell)

    # --------------------------------------------------------------
    # Body text
    # --------------------------------------------------------------

    if background:

        background = " ".join(background.split())

        p = _new_paragraph(cell)

        p.alignment = WD_ALIGN_PARAGRAPH.LEFT

        run = p.add_run(background)

        run.font.name = "Arial"
        run.font.size = Pt(BODY_SIZE)

    # --------------------------------------------------------------
    # Keep together
    # --------------------------------------------------------------

    for paragraph in cell.paragraphs:

        fmt = paragraph.paragraph_format

        fmt.keep_together = True
        fmt.keep_with_next = False

##############################################################################
# Public entry point
##############################################################################

def generate_labels_docx(
    label_data,
    include_background=False,
):
    """
    Generate Avery 94207 labels as a Microsoft Word document.

    Parameters
    ----------
    label_data
        List of (row, quantity) tuples identical to
        generate_labels_pdf().

    include_background
        If True, append one Background Information
        label for every printed seed label that
        contains BackgroundInfo text.

    Returns
    -------
    bytes | None
        DOCX document bytes.
    """

    labels = _build_label_list(
        label_data,
        include_background,
    )

    if not labels:
        return None

    document = _setup_document()

    _build_document(
        document,
        labels,
    )

    buff = BytesIO()

    document.save(buff)

    buff.seek(0)

    return buff.getvalue()
