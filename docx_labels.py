##############################################################################
# docx_labels.py
#
# Microsoft Word label generator
# Avery 94207 (2" × 4")
#
# Cochise County Master Gardener Association
##############################################################################

from io import BytesIO

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import (
    WD_TABLE_ALIGNMENT,
    WD_CELL_VERTICAL_ALIGNMENT,
    WD_ROW_HEIGHT_RULE,
)
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from docx.oxml import OxmlElement
from docx.oxml.ns import qn


##############################################################################
# Colors
##############################################################################

GREEN = RGBColor(0, 102, 51)
RED   = RGBColor(180, 0, 0)
BLACK = RGBColor(0, 0, 0)


##############################################################################
# Font sizes
##############################################################################

TITLE_SIZE   = 10
FAMILY_SIZE  = 11
VARIETY_SIZE = 10
BODY_SIZE    = 8
SMALL_SIZE   = 7
TINY_SIZE    = 6


##############################################################################
# Avery 94207 geometry
##############################################################################

PAGE_WIDTH  = 8.5
PAGE_HEIGHT = 11.0

LEFT_MARGIN   = 0.25
RIGHT_MARGIN  = 0.25
TOP_MARGIN    = 0.50
BOTTOM_MARGIN = 0.50

LABEL_WIDTH  = 4.00
LABEL_HEIGHT = 2.00

COLUMN_GAP = 0.125

ROWS = 5
COLS = 2
LABELS_PER_PAGE = ROWS * COLS


##############################################################################
# XML helpers
##############################################################################

def _set_cell_width(cell, width_inches):
    """
    Force a table cell to a fixed width.
    """

    cell.width = Inches(width_inches)

    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()

    tcW = tcPr.first_child_found_in("w:tcW")

    if tcW is None:
        tcW = OxmlElement("w:tcW")
        tcPr.append(tcW)

    tcW.set(qn("w:type"), "dxa")
    tcW.set(
        qn("w:w"),
        str(int(width_inches * 1440)),
    )


def _set_cell_margins(
    cell,
    top=0,
    bottom=0,
    left=0,
    right=0,
):
    """
    Remove Word's default cell margins.

    Values are twips.
    Zero means absolutely no padding.
    """

    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()

    tcMar = tcPr.first_child_found_in("w:tcMar")

    if tcMar is None:
        tcMar = OxmlElement("w:tcMar")
        tcPr.append(tcMar)

    for name, value in (
        ("top", top),
        ("left", left),
        ("bottom", bottom),
        ("right", right),
    ):
        node = tcMar.find(qn(f"w:{name}"))

        if node is None:
            node = OxmlElement(f"w:{name}")
            tcMar.append(node)

        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _remove_table_borders(table):
    """
    Create a completely borderless table.
    """

    tblPr = table._tbl.tblPr

    borders = tblPr.first_child_found_in("w:tblBorders")

    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tblPr.append(borders)

    for edge in (
        "top",
        "left",
        "bottom",
        "right",
        "insideH",
        "insideV",
    ):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "nil")
        borders.append(element)


def _set_row_height(row):
    """
    Force an exact Avery row height.
    """

    row.height = Inches(LABEL_HEIGHT)
    row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY

##############################################################################
# Paragraph / text helpers
##############################################################################

def _clear_cell(cell):
    """
    Remove Word's default empty paragraph from a table cell.
    """

    if cell.paragraphs:
        p = cell.paragraphs[0]._element
        p.getparent().remove(p)


def _paragraph(
    container,
    align=WD_ALIGN_PARAGRAPH.LEFT,
):
    """
    Create a paragraph with NO extra spacing.
    """

    p = container.add_paragraph()

    fmt = p.paragraph_format

    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)

    # Single spacing
    fmt.line_spacing = 1.0

    # Prevent Word from inserting page breaks
    fmt.keep_together = True
    fmt.keep_with_next = False

    p.alignment = align

    return p


def _add_text(
    container,
    text,
    *,
    size=BODY_SIZE,
    bold=False,
    italic=False,
    color=BLACK,
    align=WD_ALIGN_PARAGRAPH.LEFT,
):
    """
    Add one formatted paragraph.
    """

    if text is None:
        return

    text = str(text).strip()

    if not text:
        return

    p = _paragraph(
        container,
        align=align,
    )

    run = p.add_run(text)

    run.font.name = "Arial"
    run.font.size = Pt(size)

    run.bold = bold
    run.italic = italic

    run.font.color.rgb = color


def _value(row, field):
    """
    Safely retrieve a value from a seed record.
    """

    value = row.get(field)

    if value is None:
        return ""

    return str(value).strip()


def _normalize(text):
    """
    Collapse multiple whitespace characters into single spaces.
    """

    if not text:
        return ""

    return " ".join(str(text).split())


##############################################################################
# Label list builder
##############################################################################

def _build_label_list(
    label_data,
    include_background=False,
):
    """
    Expand (row, quantity) pairs into a flat list of labels.

    Returns

        [
            (row, False),
            (row, False),
            (row, True),
            ...
        ]
    """

    labels = []

    for row, qty in label_data:

        qty = int(qty)

        for _ in range(qty):
            labels.append((row, False))

        if include_background:

            background = _value(
                row,
                "BackgroundInfo",
            )

            if background:

                for _ in range(qty):
                    labels.append((row, True))

    return labels

##############################################################################
# Document setup
##############################################################################

def _setup_document():
    """
    Create a Word document configured specifically for
    Avery 94207 labels.
    """

    document = Document()

    ##########################################################################
    # Page setup
    ##########################################################################

    section = document.sections[0]

    section.start_type = WD_SECTION.NEW_PAGE

    section.page_width = Inches(PAGE_WIDTH)
    section.page_height = Inches(PAGE_HEIGHT)

    section.left_margin = Inches(LEFT_MARGIN)
    section.right_margin = Inches(RIGHT_MARGIN)

    section.top_margin = Inches(TOP_MARGIN)
    section.bottom_margin = Inches(BOTTOM_MARGIN)

    ##########################################################################
    # Header / Footer
    ##########################################################################

    section.header_distance = Inches(0)
    section.footer_distance = Inches(0)

    ##########################################################################
    # Document defaults
    ##########################################################################

    normal = document.styles["Normal"]

    normal.font.name = "Arial"
    normal.font.size = Pt(BODY_SIZE)

    pf = normal.paragraph_format

    pf.space_before = Pt(0)
    pf.space_after = Pt(0)

    pf.line_spacing = 1.0

    pf.keep_together = True
    pf.keep_with_next = False

    ##########################################################################
    # Table style defaults
    ##########################################################################

    if "Table Grid" in document.styles:

        tbl = document.styles["Table Grid"]

        tbl.font.name = "Arial"
        tbl.font.size = Pt(BODY_SIZE)

        tpf = tbl.paragraph_format

        tpf.space_before = Pt(0)
        tpf.space_after = Pt(0)
        tpf.line_spacing = 1.0

    ##########################################################################
    # Remove automatic paragraph after document creation
    ##########################################################################

    if document.paragraphs:

        p = document.paragraphs[0]._element
        p.getparent().remove(p)

    return document


##############################################################################
# Page helpers
##############################################################################

def _new_page(document):
    """
    Start a new label page.

    The first page already exists, so only add a section
    when the document already contains content.
    """

    if document.tables:

        document.add_page_break()


def _remaining_slots(label_count):
    """
    Number of empty labels needed to finish the page.
    """

    remainder = label_count % LABELS_PER_PAGE

    if remainder == 0:
        return 0

    return LABELS_PER_PAGE - remainder

##############################################################################
# Avery page builder
##############################################################################

def _create_page_table(document):
    """
    Create one Avery 94207 page.

        2 columns
        5 rows

    Every cell is exactly

        4.000" × 2.000"

    No borders.
    No padding.
    No autofit.
    """

    table = document.add_table(
        rows=ROWS,
        cols=COLS,
    )

    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    _remove_table_borders(table)

    #######################################################################
    # Fixed column widths
    #######################################################################

    for column in table.columns:

        column.width = Inches(LABEL_WIDTH)

    #######################################################################
    # Fixed row heights
    #######################################################################

    for row in table.rows:

        _set_row_height(row)

    #######################################################################
    # Configure every label cell
    #######################################################################

    for row in table.rows:

        for cell in row.cells:

            _clear_cell(cell)

            cell.vertical_alignment = (
                WD_CELL_VERTICAL_ALIGNMENT.TOP
            )

            _set_cell_width(
                cell,
                LABEL_WIDTH,
            )

            #
            # Absolutely no Word padding
            #
            _set_cell_margins(
                cell,
                top=0,
                bottom=0,
                left=0,
                right=0,
            )

    return table


##############################################################################
# Label container
##############################################################################

def _label_cell(table, index):
    """
    Return the table cell corresponding to a label number.

        0..9
    """

    row = index // COLS
    col = index % COLS

    return table.cell(row, col)


##############################################################################
# Two-column content layout
##############################################################################

def _content_table(cell):
    """
    Create the borderless table used inside each label.

    +----------------------+------------------+
    |                      |                  |
    |   LEFT CONTENT       | RIGHT CONTENT    |
    |                      |                  |
    +----------------------+------------------+

    This produces much more stable alignment than
    dozens of independent paragraphs.
    """

    inner = cell.add_table(
        rows=1,
        cols=2,
    )

    inner.autofit = False
    inner.alignment = WD_TABLE_ALIGNMENT.LEFT

    _remove_table_borders(inner)

    #######################################################################
    # Left side
    #######################################################################

    left = inner.columns[0]
    left.width = Inches(2.75)

    #######################################################################
    # Right side
    #######################################################################

    right = inner.columns[1]
    right.width = Inches(1.15)

    #######################################################################
    # Remove Word padding
    #######################################################################

    for c in inner.row_cells(0):

        c.vertical_alignment = (
            WD_CELL_VERTICAL_ALIGNMENT.TOP
        )

        _clear_cell(c)

        _set_cell_margins(
            c,
            top=0,
            bottom=0,
            left=0,
            right=0,
        )

    return inner


##############################################################################
# Page iterator
##############################################################################

def _page_chunks(labels):
    """
    Yield pages of ten labels.

    Example

        page 1 -> labels[0:10]
        page 2 -> labels[10:20]
    """

    for start in range(
        0,
        len(labels),
        LABELS_PER_PAGE,
    ):

        yield labels[
            start:start + LABELS_PER_PAGE
        ]

##############################################################################
# Standard seed label
##############################################################################

def _draw_seed_label(cell, row):
    """
    Draw one standard seed label.
    """

    family = _value(row, "Family")
    variety = _value(row, "Variety")
    hybrid = _value(row, "HybridDoNotSave")

    inner = _content_table(cell)

    left = inner.cell(0, 0)
    right = inner.cell(0, 1)

    ######################################################################
    # LEFT SIDE
    ######################################################################

    _add_text(
        left,
        "Cochise County Master Gardener Association",
        size=TITLE_SIZE,
        bold=True,
        color=GREEN,
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )

    _add_text(
        left,
        "Seed Library",
        size=TITLE_SIZE,
        bold=True,
        color=GREEN,
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )

    #
    # No divider in Version 2
    #

    if family:

        _add_text(
            left,
            family.upper(),
            size=FAMILY_SIZE,
            bold=True,
        )

    if variety:

        _add_text(
            left,
            variety,
            size=VARIETY_SIZE,
            bold=True,
        )

    ######################################################################
    # Hybrid warning
    ######################################################################

    if hybrid:

        value = hybrid.strip().lower()

        if value in (
            "y",
            "yes",
            "true",
            "1",
            "x",
        ):

            _add_text(
                left,
                "*** HYBRID - DO NOT SAVE SEED ***",
                size=BODY_SIZE,
                bold=True,
                color=RED,
            )

    ######################################################################
    # Comments
    ######################################################################

    comments = _normalize(
        _value(row, "Comments")
    )

    if comments:

        _add_text(
            left,
            comments,
            size=SMALL_SIZE,
        )

    ######################################################################
    # RIGHT SIDE
    ######################################################################

    year = _value(row, "Year")
    if year:
        _add_text(
            right,
            f"Year: {year}",
            size=BODY_SIZE,
            bold=True,
        )

    edible = _value(row, "Edible")
    if edible:
        _add_text(
            right,
            f"Edible: {edible}",
            size=BODY_SIZE,
        )

    season = _value(row, "Season")
    if season:
        _add_text(
            right,
            f"Season: {season}",
            size=BODY_SIZE,
        )

    num = _value(row, "NumSeeds")
    if num:
        _add_text(
            right,
            f"Seeds: {num}",
            size=BODY_SIZE,
        )

    saver = _value(row, "SeedSaverLevel")
    if saver:
        _add_text(
            right,
            f"Seed Saver: {saver}",
            size=BODY_SIZE,
        )

    ######################################################################
    # Germination
    ######################################################################

    germ = _value(row, "Germination")

    if germ:

        _add_text(
            right,
            f"Germ: {germ}",
            size=BODY_SIZE,
        )

    ######################################################################
    # Soil Temperature
    ######################################################################

    soil = _value(row, "SoilTemperature")

    if soil:

        _add_text(
            right,
            f"Soil: {soil}",
            size=BODY_SIZE,
        )

    ######################################################################
    # Blank lines to keep left/right balanced
    ######################################################################

    left_count = len(left.paragraphs)
    right_count = len(right.paragraphs)

    while left_count < right_count:

        _add_text(
            left,
            " ",
            size=TINY_SIZE,
        )

        left_count += 1

    while right_count < left_count:

        _add_text(
            right,
            " ",
            size=TINY_SIZE,
        )

        right_count += 1

    ######################################################################
    # Final cleanup
    ######################################################################

    #
    # Ensure every paragraph has identical spacing.
    #
    for c in (left, right):

        for p in c.paragraphs:

            fmt = p.paragraph_format

            fmt.space_before = Pt(0)
            fmt.space_after = Pt(0)
            fmt.line_spacing = 1.0

            fmt.keep_together = True
            fmt.keep_with_next = False

    return

##############################################################################
# Background Information Label
##############################################################################

def _draw_background_label(cell, row):
    """
    Draw one Background Information label.

    Unlike the standard seed label, this uses the
    full label width for the background text.
    """

    family = _value(row, "Family")
    variety = _value(row, "Variety")
    background = _normalize(
        _value(row, "BackgroundInfo")
    )

    ######################################################################
    # Single full-width content area
    ######################################################################

    _clear_cell(cell)

    _set_cell_margins(
        cell,
        top=0,
        bottom=0,
        left=0,
        right=0,
    )

    cell.vertical_alignment = (
        WD_CELL_VERTICAL_ALIGNMENT.TOP
    )

    ######################################################################
    # Title
    ######################################################################

    _add_text(
        cell,
        "Cochise County Master Gardener Association",
        size=TITLE_SIZE,
        bold=True,
        color=GREEN,
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )

    _add_text(
        cell,
        "Seed Library",
        size=TITLE_SIZE,
        bold=True,
        color=GREEN,
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )

    ######################################################################
    # Plant Identification
    ######################################################################

    if family:

        _add_text(
            cell,
            family.upper(),
            size=FAMILY_SIZE,
            bold=True,
        )

    if variety:

        _add_text(
            cell,
            variety,
            size=VARIETY_SIZE,
            bold=True,
        )

    ######################################################################
    # Background heading
    ######################################################################

    _add_text(
        cell,
        "Background Information",
        size=BODY_SIZE,
        bold=True,
        color=GREEN,
    )

    ######################################################################
    # Background text
    ######################################################################

    if background:

        _add_text(
            cell,
            background,
            size=SMALL_SIZE,
        )

    ######################################################################
    # Final cleanup
    ######################################################################

    for p in cell.paragraphs:

        fmt = p.paragraph_format

        fmt.space_before = Pt(0)
        fmt.space_after = Pt(0)
        fmt.line_spacing = 1.0

        fmt.keep_together = True
        fmt.keep_with_next = False

##############################################################################
# Document Builder
##############################################################################

def _build_document(
    document,
    labels,
):
    """
    Build the complete Word document.

    Labels are supplied as

        (row, is_background)

    where

        is_background == False

    produces a normal seed label

    and

        is_background == True

    produces a Background Information label.
    """

    if not labels:
        return

    ######################################################################
    # Build one Avery page at a time
    ######################################################################

    first_page = True

    for page in _page_chunks(labels):

        #
        # Every page after the first begins on a new page.
        #
        if not first_page:
            _new_page(document)

        first_page = False

        table = _create_page_table(document)

        ##################################################################
        # Draw each label
        ##################################################################

        for index, (row, is_background) in enumerate(page):

            cell = _label_cell(
                table,
                index,
            )

            if is_background:

                _draw_background_label(
                    cell,
                    row,
                )

            else:

                _draw_seed_label(
                    cell,
                    row,
                )

        ##################################################################
        # Blank out unused labels on the last page
        ##################################################################

        for blank in range(
            len(page),
            LABELS_PER_PAGE,
        ):

            cell = _label_cell(
                table,
                blank,
            )

            _clear_cell(cell)

            _set_cell_margins(
                cell,
                top=0,
                bottom=0,
                left=0,
                right=0,
            )

            cell.vertical_alignment = (
                WD_CELL_VERTICAL_ALIGNMENT.TOP
            )

    return document

def generate_labels_docx(
    label_data,
    include_background=False,
)

