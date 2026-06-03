#!/usr/bin/env python3
"""
Cochise County Master Gardener Association — Seed Library
Streamlit Web Application
Run with:  streamlit run streamlit_app.py
"""

import os
import io
import sys
import sqlite3
import tempfile
import streamlit as st

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CCMGA Seed Library",
    page_icon="🌹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# PASSWORD PROTECTION
# ─────────────────────────────────────────────────────────────
def check_password():
    """
    Returns True if the user is authenticated.
    Password is stored in st.secrets["APP_PASSWORD"].
    Falls back to a default for local development if secrets not configured.
    """
    if st.session_state.get("authenticated"):
        return True

    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="
            background-color:#1b5e20;
            padding:32px;
            border-radius:12px;
            text-align:center;
            margin-top:60px;
        ">
            <h1 style="color:white;margin:0 0 4px 0;">🌹</h1>
            <h2 style="color:white;margin:0 0 4px 0;">CCMGA Seed Library</h2>
            <p style="color:#c8e6c9;margin:0 0 24px 0;">
                Cochise County Master Gardener Association
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("###")
        pw = st.text_input("Password", type="password",
                           placeholder="Enter library password…")
        login_clicked = st.button("Login", use_container_width=True)

        if login_clicked:
            # Get password from secrets or fall back to default for local dev
            try:
                correct = st.secrets["APP_PASSWORD"]
            except (KeyError, FileNotFoundError):
                correct = "ccmga2024"   # local dev default — change before deploying

            if pw == correct:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password. Please try again.")

        st.markdown(
            "<p style='text-align:center;color:#888;font-size:0.8rem;"
            "margin-top:16px;'>"
            "Contact your library coordinator for access.</p>",
            unsafe_allow_html=True,
        )
    st.stop()
    return False

# ─────────────────────────────────────────────────────────────
# GLOBAL STYLES
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1b5e20;
    }
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    [data-testid="stSidebar"] .stRadio label {
        color: white !important;
        font-weight: bold;
        font-size: 1.05rem;
    }
    /* Page title */
    .ccmga-title {
        background-color: #1b5e20;
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        margin-bottom: 18px;
        text-align: center;
    }
    .ccmga-title h1 { color: white; margin: 0; font-size: 1.6rem; }
    .ccmga-title p  { color: #c8e6c9; margin: 4px 0 0 0; font-size: 0.95rem; }
    /* Blue action buttons */
    .stButton > button {
        background-color: #0076DB;
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: bold;
        padding: 8px 20px;
    }
    .stButton > button:hover {
        background-color: #005aaa;
        color: white;
    }
    /* Dataframe table */
    .stDataFrame { border: 1px solid #ddd; border-radius: 6px; }
    /* Field labels */
    .field-label { font-weight: bold; color: #1b5e20; }
    /* Success / error boxes */
    .stAlert { border-radius: 6px; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# DATABASE — loaded once per session into st.session_state
# ─────────────────────────────────────────────────────────────
COLS = [
    "FileNumber", "Family", "Variety", "SeedSource", "Comments",
    "NumSeeds", "Season", "SeedSaverLevel", "HybridDoNotSave",
    "Edible", "WhereGrown", "PerennialAnnual", "GrownBy",
    "Year", "SoilTemperature", "Germination", "BackgroundInfo",
]

CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS seeds (
        FileNumber INTEGER PRIMARY KEY,
        Family TEXT, Variety TEXT, SeedSource TEXT, Comments TEXT,
        NumSeeds TEXT, Season TEXT, SeedSaverLevel TEXT,
        HybridDoNotSave TEXT, Edible TEXT, WhereGrown TEXT,
        PerennialAnnual TEXT, GrownBy TEXT, Year TEXT,
        SoilTemperature TEXT, Germination TEXT, BackgroundInfo TEXT
    )
"""


def get_db() -> sqlite3.Connection:
    """Return the shared in-session SQLite connection."""
    if "db" not in st.session_state:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute(CREATE_SQL)
        conn.commit()
        st.session_state.db = conn
        _load_xlsx(conn)
    return st.session_state.db


def _load_xlsx(conn: sqlite3.Connection):
    """Load _SEED_LIBRARY_PARSED.xlsx using openpyxl (stdlib-compatible zip+xml)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    xlsx_path = None
    for d in [script_dir, os.path.dirname(script_dir), os.getcwd()]:
        cand = os.path.join(d, "_SEED_LIBRARY_PARSED.xlsx")
        if os.path.exists(cand):
            xlsx_path = cand
            break

    if not xlsx_path:
        st.session_state["db_status"] = "warning"
        st.session_state["db_msg"] = (
            "⚠️ _SEED_LIBRARY_PARSED.xlsx not found. "
            "Place it in the same folder as streamlit_app.py."
        )
        return

    try:
        # Read xlsx using openpyxl
        import openpyxl
        wb  = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        ws  = wb.active
        all_rows = list(ws.iter_rows(values_only=True))
        wb.close()

        if not all_rows:
            raise ValueError("Spreadsheet appears to be empty.")

        # First row = headers
        headers = [str(h).strip() if h is not None else "" for h in all_rows[0]]

        def ci(name):
            try:    return headers.index(name)
            except: return -1

        col_idx = {
            "FileNumber":      ci("FileNumber"),
            "Family":          ci("Family"),
            "Variety":         ci("Variety"),
            "SeedSource":      ci("Seed Source"),
            "Comments":        ci("Comments"),
            "NumSeeds":        ci("# of Seeds"),
            "Season":          ci("Season"),
            "SeedSaverLevel":  ci("Seed Saver Level"),
            "HybridDoNotSave": ci("Hybrid-Do Not Save"),
            "Edible":          ci("Edible"),
            "WhereGrown":      ci("Where Grown"),
            "PerennialAnnual": ci("Perennial/Annual"),
            "GrownBy":         ci("Grown By"),
            "Year":            ci("Year"),
            "SoilTemperature": ci("Soil Temperature"),
            "Germination":     ci("Germination"),
        }

        def get(row_vals, key):
            idx = col_idx.get(key, -1)
            if idx < 0 or idx >= len(row_vals):
                return ""
            v = row_vals[idx]
            return str(v).strip() if v is not None else ""

        inserted = 0
        for row_vals in all_rows[1:]:
            fn_raw = get(row_vals, "FileNumber")
            if not fn_raw or fn_raw == "None":
                continue
            try:
                fn = int(float(fn_raw))
            except:
                continue
            yr_raw = get(row_vals, "Year")
            try:
                yr = str(int(float(yr_raw))) if yr_raw and yr_raw != "None" else ""
            except:
                yr = yr_raw
            conn.execute(
                "INSERT OR REPLACE INTO seeds VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (fn,
                 get(row_vals, "Family"),    get(row_vals, "Variety"),
                 get(row_vals, "SeedSource"), get(row_vals, "Comments"),
                 get(row_vals, "NumSeeds"),   get(row_vals, "Season"),
                 get(row_vals, "SeedSaverLevel"), get(row_vals, "HybridDoNotSave"),
                 get(row_vals, "Edible"),     get(row_vals, "WhereGrown"),
                 get(row_vals, "PerennialAnnual"), get(row_vals, "GrownBy"),
                 yr,
                 get(row_vals, "SoilTemperature"), get(row_vals, "Germination"),
                 get(row_vals, "BackgroundInfo")),
            )
            inserted += 1
        conn.commit()
        st.session_state["db_status"] = "ok"
        st.session_state["db_msg"]    = f"✅ Loaded {inserted} seeds from xlsx."
    except ImportError:
        st.session_state["db_status"] = "error"
        st.session_state["db_msg"] = (
            "❌ openpyxl not installed. Run:  pip install openpyxl"
        )
    except Exception as e:
        st.session_state["db_status"] = "error"
        st.session_state["db_msg"]    = f"❌ Error loading xlsx: {e}"


def db_search(term: str = "") -> list[dict]:
    conn = get_db()
    t = f"%{term.lower()}%"
    if term:
        cur = conn.execute("""
            SELECT * FROM seeds
            WHERE LOWER(CAST(FileNumber AS TEXT)) LIKE ?
               OR LOWER(Family)  LIKE ?
               OR LOWER(Variety) LIKE ?
            ORDER BY FileNumber
        """, (t, t, t))
    else:
        cur = conn.execute("SELECT * FROM seeds ORDER BY FileNumber")
    return [dict(r) for r in cur.fetchall()]


def db_add(data: dict):
    conn = get_db()
    conn.execute(
        "INSERT INTO seeds VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        tuple(data.get(c, "") for c in COLS),
    )
    conn.commit()


def db_update(fn: int, data: dict):
    conn = get_db()
    conn.execute("""
        UPDATE seeds SET
            Family=?, Variety=?, SeedSource=?, Comments=?,
            NumSeeds=?, Season=?, SeedSaverLevel=?, HybridDoNotSave=?,
            Edible=?, WhereGrown=?, PerennialAnnual=?, GrownBy=?,
            Year=?, SoilTemperature=?, Germination=?, BackgroundInfo=?
        WHERE FileNumber=?
    """, (
        data["Family"], data["Variety"], data["SeedSource"], data["Comments"],
        data["NumSeeds"], data["Season"], data["SeedSaverLevel"],
        data["HybridDoNotSave"], data["Edible"], data["WhereGrown"],
        data["PerennialAnnual"], data["GrownBy"], data["Year"],
        data["SoilTemperature"], data["Germination"],
        data.get("BackgroundInfo", ""), fn,
    ))
    conn.commit()


def db_delete(file_numbers: list[int]):
    conn = get_db()
    for fn in file_numbers:
        conn.execute("DELETE FROM seeds WHERE FileNumber=?", (fn,))
    conn.commit()


def db_next_fn() -> int:
    conn = get_db()
    row = conn.execute("SELECT MAX(FileNumber) FROM seeds").fetchone()
    return (row[0] + 1) if row[0] else 1001


def db_count() -> int:
    conn = get_db()
    return conn.execute("SELECT COUNT(*) FROM seeds").fetchone()[0]


# ─────────────────────────────────────────────────────────────
# PDF GENERATION
# ─────────────────────────────────────────────────────────────
def generate_labels_pdf(label_data: list,
                        include_background: bool = False) -> bytes | None:
    """Returns PDF bytes or None on error.
    If include_background=True, appends a separate background-info label
    for each seed that has BackgroundInfo text.
    Hybrid warning is printed on every label where HybridDoNotSave is set.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units    import inch
        from reportlab.lib          import colors
        from reportlab.platypus     import Paragraph, Frame
        from reportlab.lib.styles   import ParagraphStyle
        from reportlab.lib.enums    import TA_CENTER, TA_LEFT
        from reportlab.pdfgen       import canvas as rl_canvas
    except ImportError:
        st.error("ReportLab not installed. Run:  pip install reportlab")
        return None

    labels = []      # (row, is_bg_label)
    for row, qty in label_data:
        for _ in range(qty):
            labels.append((row, False))
        # Add one background info label per seed (not per qty)
        if include_background and (row.get("BackgroundInfo") or "").strip():
            labels.append((row, True))
    if not labels:
        return None

    PAGE_W, PAGE_H  = letter
    MARGIN_TOP      = 0.50 * inch
    MARGIN_LEFT     = 0.16 * inch
    MARGIN_RIGHT    = 0.16 * inch
    LABEL_W         = (PAGE_W - MARGIN_LEFT - MARGIN_RIGHT) / 2
    LABEL_H         = 2.00  * inch
    COLS, ROWS      = 2, 5
    PER_PAGE        = COLS * ROWS

    PAD_L, PAD_R, PAD_T, PAD_B = 6, 4, 4, 3
    TITLE_H         = 28
    LEFT_FRAC       = 2 / 3

    BORDER  = colors.HexColor("#000000")
    DIVIDER = colors.HexColor("#888888")
    GREEN   = colors.HexColor("#225522")

    title_sty = ParagraphStyle("ttl", fontSize=11, fontName="Helvetica-Bold",
        textColor=GREEN, alignment=TA_CENTER, leading=13, spaceAfter=0)
    fam_sty = ParagraphStyle("fam", fontSize=10, fontName="Helvetica-Bold",
        textColor=colors.red, alignment=TA_LEFT, leading=12, spaceAfter=1)
    var_sty = ParagraphStyle("var", fontSize=10, fontName="Helvetica-Oblique",
        textColor=colors.black, alignment=TA_LEFT, leading=12, spaceAfter=2)
    cmt_sty = ParagraphStyle("cmt", fontSize=9, fontName="Helvetica",
        textColor=colors.black, alignment=TA_LEFT, leading=11, spaceAfter=0)
    rgt_sty = ParagraphStyle("rgt", fontSize=9, fontName="Helvetica",
        textColor=colors.black, alignment=TA_CENTER, leading=11, spaceAfter=1)
    rit_sty = ParagraphStyle("rit", fontSize=9, fontName="Helvetica-Oblique",
        textColor=colors.black, alignment=TA_CENTER, leading=11, spaceAfter=1)
    svr_sty = ParagraphStyle("svr", fontSize=7, fontName="Helvetica-Bold",
        textColor=colors.black, alignment=TA_CENTER, leading=9,
        spaceAfter=1, wordWrap="LTR")
    grm_sty = ParagraphStyle("grm", fontSize=8, fontName="Helvetica",
        textColor=colors.black, alignment=TA_CENTER, leading=10, spaceAfter=0)

    buf = io.BytesIO()
    c   = rl_canvas.Canvas(buf, pagesize=letter)

    page_idx = 0
    while page_idx * PER_PAGE < len(labels):
        page_labels = labels[page_idx * PER_PAGE : (page_idx + 1) * PER_PAGE]

        for slot, (row, is_bg) in enumerate(page_labels):
            col_num = slot % COLS
            row_num = slot // COLS
            lx = MARGIN_LEFT + col_num * LABEL_W
            ly = PAGE_H - MARGIN_TOP - (row_num + 1) * LABEL_H

            # Extract fields (needed for both label types)
            family   = (row.get("Family")          or "").strip()
            variety  = (row.get("Variety")         or "").strip()
            season   = (row.get("Season")          or "").strip()
            numseeds = (row.get("NumSeeds")        or "").strip()
            edible   = (row.get("Edible")          or "").strip()
            year_val = (row.get("Year")            or "").strip()
            comment  = " ".join((row.get("Comments") or "").split())[:300]
            saver    = (row.get("SeedSaverLevel")  or "").strip()
            germ     = (row.get("Germination")     or "").strip()
            soil_t   = (row.get("SoilTemperature") or "").strip()
            hybrid   = (row.get("HybridDoNotSave") or "").strip()
            bg_info  = " ".join((row.get("BackgroundInfo") or "").split())[:300]

            # No borders on any label
            # Common layout measurements
            tx     = lx + PAD_L
            tw     = LABEL_W - PAD_L - PAD_R
            body_y = ly + PAD_B
            body_x = lx + PAD_L
            body_w = LABEL_W - PAD_L - PAD_R

            if is_bg:
                # ── Background Info label — clean, no dividers, full width ──
                # Generous padding for readability
                BG_PAD = 10
                full_w = LABEL_W - BG_PAD * 2
                full_h = LABEL_H - BG_PAD * 2

                # Title: "Family — Background Info"
                bg_title_sty = ParagraphStyle("bgtitle",
                    fontSize=10, fontName="Helvetica-Bold",
                    textColor=colors.black, alignment=TA_LEFT,
                    leading=13, spaceAfter=4)
                bg_body_sty = ParagraphStyle("bgbody",
                    fontSize=9, fontName="Helvetica",
                    textColor=colors.black, alignment=TA_LEFT,
                    leading=12, spaceAfter=0)

                all_bg = [
                    Paragraph(f"{family}", bg_title_sty),
                    Paragraph(f"{variety} — Background Information", bg_title_sty),
                    Paragraph(bg_info, bg_body_sty),
                ]
                Frame(lx + BG_PAD, ly + BG_PAD, full_w, full_h,
                      leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0,
                      showBoundary=0).addFromList(all_bg, c)

            else:
                # ── Standard seed label ────────────────────────────
                TITLE_H_USE = TITLE_H
                ty     = ly + LABEL_H - PAD_T - TITLE_H_USE
                body_h = LABEL_H - PAD_T - TITLE_H_USE - 3 - PAD_B
                left_w = body_w * LEFT_FRAC
                right_w = body_w * (1 - LEFT_FRAC)
                vdiv_x = body_x + left_w + 2

                # Header
                Frame(tx, ty, tw, TITLE_H_USE, leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0, showBoundary=0).addFromList(
                    [Paragraph("Cochise County Master Gardener Association"
                               "<br/>Seed Library", title_sty)], c)

                # Thin horizontal divider under header
                div_y = ly + LABEL_H - PAD_T - TITLE_H_USE - 1
                c.setStrokeColor(DIVIDER)
                c.setLineWidth(0.5)
                c.line(lx + 2, div_y, lx + LABEL_W - 2, div_y)

                # Vertical divider between left and right cells
                c.line(vdiv_x, ly + PAD_B + 2, vdiv_x, div_y - 2)

                # Left cell
                left_items = [Paragraph(family, fam_sty)]
                if variety: left_items.append(Paragraph(variety, var_sty))
                if hybrid:  left_items.append(Paragraph(
                    f"* HYBRID — DO NOT SAVE SEEDS *",
                    ParagraphStyle("hyb", fontSize=7,
                    fontName="Helvetica-Bold",
                    textColor=colors.HexColor("#b71c1c"),
                    alignment=TA_LEFT, leading=9)))
                if comment: left_items.append(Paragraph(comment, cmt_sty))
                Frame(body_x, body_y, left_w - 4, body_h,
                      leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0, showBoundary=0
                      ).addFromList(left_items, c)

                # Right cell
                right_items = []
                if year_val: right_items.append(Paragraph(year_val, rgt_sty))
                if edible:   right_items.append(Paragraph(edible.upper(), rgt_sty))
                if season:   right_items.append(Paragraph(season, rit_sty))
                if numseeds: right_items.append(Paragraph(f"{numseeds} Seeds", rgt_sty))
                if saver:    right_items.append(Paragraph(saver, svr_sty))
                germ_text = germ
                if soil_t:
                    germ_text += f"\n@ {soil_t}" if germ else soil_t
                if germ_text:
                    right_items.append(Paragraph(f"Germ: {germ_text}", grm_sty))
                Frame(vdiv_x + 3, body_y, right_w - 4, body_h,
                      leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0, showBoundary=0
                      ).addFromList(right_items, c)

        c.showPage()
        page_idx += 1

    c.save()
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────
# SHARED UI HELPERS
# ─────────────────────────────────────────────────────────────
def page_header(title: str, subtitle: str = ""):
    st.markdown(f"""
    <div class="ccmga-title">
        <h1>🌹 {title}</h1>
        {"<p>" + subtitle + "</p>" if subtitle else ""}
    </div>
    """, unsafe_allow_html=True)


FIELD_LABELS = {
    "FileNumber":      "File Number",
    "Family":          "Family",
    "Variety":         "Variety",
    "SeedSource":      "Seed Source",
    "Comments":        "Comments",
    "NumSeeds":        "# of Seeds",
    "Season":          "Season",
    "SeedSaverLevel":  "Seed Saver Level",
    "HybridDoNotSave": "Hybrid-Do Not Save",
    "Edible":          "Edible",
    "WhereGrown":      "Where Grown",
    "PerennialAnnual": "Perennial/Annual",
    "GrownBy":         "Grown By",
    "Year":            "Year",
    "SoilTemperature": "Soil Temperature",
    "Germination":     "Germination",
    "BackgroundInfo":  "Background Info",
}

SEASON_OPTS   = ["", "Cool Season", "Warm Season", "Hot Season",
                 "All Season", "Decorative"]
SAVER_OPTS    = ["", "Beginner Seed Saver", "Easy Seed Saver",
                 "Intermediate Seed Saver", "Advanced Seed Saver"]
PERAN_OPTS    = ["", "Annual", "Perennial", "Perennial/Annual"]


# ─────────────────────────────────────────────────────────────
# PAGE: HOME
# ─────────────────────────────────────────────────────────────
def page_home():
    page_header(
        "Cochise County Master Gardener Association",
        "Seed Library Database",
    )
    get_db()   # ensure DB is loaded
    status = st.session_state.get("db_status", "")
    msg    = st.session_state.get("db_msg", "")
    if status == "ok":
        st.success(msg)
    elif status == "warning":
        st.warning(msg)
    elif status == "error":
        st.error(msg)

    count = db_count()
    st.markdown(f"### 🌱 {count:,} seeds in the library")
    st.markdown("---")

    st.markdown("""
**Use the navigation menu on the left sidebar to move between pages.**

| | |
|---|---|
| **Version** | 1.0 |
| **Built for** | Cochise County Master Gardener Association |
| **Labels** | Avery 94207  (2″ × 4″, 10 per sheet) |
| **Platform** | Python · Streamlit · ReportLab |
| **Credits** | Claude AI (Anthropic) + Alan Borhauer |
    """)

    # ── Seeds with comments or background info over 300 chars ───────
    conn = get_db()
    over_limit = conn.execute("""
        SELECT FileNumber, Family, Variety,
               LENGTH(Comments)      AS clen,
               LENGTH(BackgroundInfo) AS blen
        FROM seeds
        WHERE LENGTH(Comments) > 300
           OR LENGTH(BackgroundInfo) > 300
        ORDER BY Family, Variety
    """).fetchall()

    if over_limit:
        st.markdown("---")
        st.warning(f"⚠️ **{len(over_limit)} seed(s) have text exceeding the "
                   "300-character label limit.** Only the first 300 characters "
                   "will print. Edit these records to shorten the text.")
        rows_display = []
        for r in over_limit:
            issues = []
            if r["clen"] and r["clen"] > 300:
                issues.append(f"Comments: {r['clen']} chars ({r['clen']-300} over)")
            if r["blen"] and r["blen"] > 300:
                issues.append(f"Background Info: {r['blen']} chars ({r['blen']-300} over)")
            rows_display.append({
                "File #":   r["FileNumber"],
                "Family":   r["Family"],
                "Variety":  r["Variety"],
                "Issue":    "  |  ".join(issues),
            })
        import pandas as pd
        st.dataframe(
            pd.DataFrame(rows_display),
            use_container_width=True,
            hide_index=True,
        )


# ─────────────────────────────────────────────────────────────
# PAGE: BROWSE
# ─────────────────────────────────────────────────────────────
def page_browse():
    page_header("Browse Seeds", "Search, sort, view details, and edit records")

    # Search bar
    col_s, col_b1, col_b2 = st.columns([4, 1, 1])
    with col_s:
        term = st.text_input("Search", placeholder="Family, variety, or file number…",
                             label_visibility="collapsed",
                             key="browse_search")
    with col_b1:
        search_clicked = st.button("Search", use_container_width=True)
    with col_b2:
        show_all = st.button("Show All", use_container_width=True)
    if show_all:
        st.session_state.browse_term = ""
    elif search_clicked:
        st.session_state.browse_term = term

    active_term = st.session_state.get("browse_term", "")
    rows = db_search(active_term)

    # Deduplicate by Family+Variety — keep first occurrence, count duplicates
    seen      = {}
    unique    = []
    count_map = {}
    for r in rows:
        key = (r["Family"].strip().lower(), r["Variety"].strip().lower())
        count_map[key] = count_map.get(key, 0) + 1
    for r in rows:
        key = (r["Family"].strip().lower(), r["Variety"].strip().lower())
        if key not in seen:
            seen[key] = True
            unique.append(r)

    st.caption(f"{len(unique)} unique varieties  ({len(rows)} total records)")

    if not unique:
        st.info("No seeds found.")
        return

    # Display table with import pandas trick-free approach
    import pandas as pd
    display_cols = ["FileNumber", "Family", "Variety", "Count",
                    "Season", "NumSeeds", "SeedSaverLevel",
                    "PerennialAnnual", "GrownBy", "Year"]

    table_data = []
    for r in unique:
        key = (r["Family"].strip().lower(), r["Variety"].strip().lower())
        row_d = {c: r.get(c, "") for c in display_cols if c != "Count"}
        row_d["Count"] = count_map[key]
        table_data.append(row_d)

    df = pd.DataFrame(table_data)[
        ["FileNumber", "Family", "Variety", "Count",
         "Season", "NumSeeds", "SeedSaverLevel", "PerennialAnnual",
         "GrownBy", "Year"]
    ]
    df.columns = ["File #", "Family", "Variety", "Count",
                  "Season", "# Seeds", "Saver Level",
                  "Perennial/Annual", "Grown By", "Year"]

    st.dataframe(df, use_container_width=True, hide_index=True,
                 height=320)

    st.markdown("---")

    # ── Detail / Edit panel ─────────────────────────────────────
    st.markdown("#### View or Edit a Record")
    fn_options = {f"#{r['FileNumber']}  {r['Family']} — {r['Variety']}": r["FileNumber"]
                  for r in unique}
    chosen_label = st.selectbox("Select seed", list(fn_options.keys()),
                                key="browse_select")
    chosen_fn = fn_options[chosen_label]
    chosen_row = next((r for r in rows if r["FileNumber"] == chosen_fn), None)

    if chosen_row:
        action = st.radio(
            "Action",
            ["View", "Edit", "Duplicate as New Record"],
            horizontal=True,
            key="browse_action",
        )
        st.markdown("---")
        if action == "View":
            _browse_detail(chosen_row)
        elif action == "Edit":
            _browse_edit_form(chosen_row, is_duplicate=False)
        elif action == "Duplicate as New Record":
            _browse_duplicate_form(chosen_row)


def _browse_detail(row: dict):
    """Read-only detail view."""
    col1, col2 = st.columns(2)
    left_fields  = ["Family", "Variety", "Comments", "SeedSource",
                    "GrownBy", "WhereGrown"]
    right_fields = ["FileNumber", "Year", "Season", "NumSeeds", "Edible",
                    "PerennialAnnual", "SeedSaverLevel",
                    "SoilTemperature", "Germination", "HybridDoNotSave"]
    with col1:
        for f in left_fields:
            val = row.get(f, "") or "—"
            # Flag comments over 300 chars
            if f == "Comments" and len(val) > 300:
                st.markdown(f"**{FIELD_LABELS[f]}:** {val}")
                st.warning(f"⚠️ Comments are {len(val)} characters "
                           f"({len(val)-300} over the 300-char label limit). "
                           "Only the first 300 characters will print on the label.")
            else:
                st.markdown(f"**{FIELD_LABELS[f]}:** {val}")
    with col2:
        for f in right_fields:
            st.markdown(f"**{FIELD_LABELS[f]}:** {row.get(f,'') or '—'}")

    # Background Info — always shown in full with its own section
    bg = (row.get("BackgroundInfo") or "").strip()
    if bg:
        st.markdown("---")
        st.markdown("**Background Information**")
        st.markdown(bg)
        if len(bg) > 300:
            st.warning(f"⚠️ Background Info is {len(bg)} characters "
                       f"({len(bg)-300} over the 300-char label limit). "
                       "Only the first 300 characters will print on the label.")


def _browse_edit_form(row: dict, is_duplicate: bool = False):
    """Editable form for the selected row."""
    fn = row["FileNumber"]
    st.markdown(f"**Editing File #{fn}**")
    with st.form(key=f"edit_form_{fn}_{is_duplicate}"):
        c1, c2 = st.columns(2)
        with c1:
            family  = st.text_input("Family",       value=row.get("Family",""))
            variety = st.text_input("Variety",       value=row.get("Variety",""))
            source  = st.text_input("Seed Source",   value=row.get("SeedSource",""))
            comments= st.text_area("Comments",       value=row.get("Comments",""), height=100,
                                   help="Max 300 chars for label printing", max_chars=300)
            grown_by= st.text_input("Grown By",      value=row.get("GrownBy",""))
            where   = st.text_input("Where Grown",   value=row.get("WhereGrown",""))
        with c2:
            year    = st.text_input("Year",          value=row.get("Year",""))
            numseeds= st.text_input("# of Seeds",    value=row.get("NumSeeds",""))
            edible  = st.text_input("Edible",        value=row.get("Edible",""))
            season_v= row.get("Season","")
            season  = st.selectbox("Season", SEASON_OPTS,
                                   index=SEASON_OPTS.index(season_v)
                                   if season_v in SEASON_OPTS else 0)
            saver_v = row.get("SeedSaverLevel","")
            saver   = st.selectbox("Seed Saver Level", SAVER_OPTS,
                                   index=SAVER_OPTS.index(saver_v)
                                   if saver_v in SAVER_OPTS else 0)
            peran_v = row.get("PerennialAnnual","")
            peran   = st.selectbox("Perennial/Annual", PERAN_OPTS,
                                   index=PERAN_OPTS.index(peran_v)
                                   if peran_v in PERAN_OPTS else 0)
            hybrid  = st.text_input("Hybrid-Do Not Save", value=row.get("HybridDoNotSave",""))
            soil_t  = st.text_input("Soil Temperature",   value=row.get("SoilTemperature",""))
            germ    = st.text_input("Germination",        value=row.get("Germination",""))
        bg_info = st.text_area("Background Info",
                               value=row.get("BackgroundInfo",""), height=80,
                               help="Max 300 chars for label printing", max_chars=300)

        if st.form_submit_button("💾  Save Changes", use_container_width=True):
            db_update(fn, {
                "Family": family, "Variety": variety,
                "SeedSource": source, "Comments": comments,
                "NumSeeds": numseeds, "Season": season,
                "SeedSaverLevel": saver, "HybridDoNotSave": hybrid,
                "Edible": edible, "WhereGrown": where,
                "PerennialAnnual": peran, "GrownBy": grown_by,
                "Year": year, "SoilTemperature": soil_t,
                "Germination": germ, "BackgroundInfo": bg_info,
            })
            st.success(f"Seed #{fn} updated successfully.")
            st.rerun()


def _browse_duplicate_form(source_row: dict):
    """Duplicate a seed record with a new file number."""
    next_fn = db_next_fn()
    st.info(f"Duplicating **#{source_row['FileNumber']} {source_row['Family']} — "
            f"{source_row['Variety']}** as new record **#{next_fn}**. "
            "Edit any fields then save.")
    with st.form(key=f"dup_form_{source_row['FileNumber']}"):
        c1, c2 = st.columns(2)
        with c1:
            fn      = st.number_input("File Number *", value=next_fn,
                                      min_value=1, step=1)
            family  = st.text_input("Family",     value=source_row.get("Family",""))
            variety = st.text_input("Variety",    value=source_row.get("Variety",""))
            source  = st.text_input("Seed Source",value=source_row.get("SeedSource",""))
            comments= st.text_area("Comments",    value=source_row.get("Comments",""), height=80)
            grown_by= st.text_input("Grown By",   value=source_row.get("GrownBy",""))
            where   = st.text_input("Where Grown",value=source_row.get("WhereGrown",""))
        with c2:
            year    = st.text_input("Year",       value=source_row.get("Year",""))
            numseeds= st.text_input("# of Seeds", value=source_row.get("NumSeeds",""))
            edible  = st.text_input("Edible",     value=source_row.get("Edible",""))
            season_v = source_row.get("Season","")
            season  = st.selectbox("Season", SEASON_OPTS,
                                   index=SEASON_OPTS.index(season_v)
                                   if season_v in SEASON_OPTS else 0)
            saver_v = source_row.get("SeedSaverLevel","")
            saver   = st.selectbox("Seed Saver Level", SAVER_OPTS,
                                   index=SAVER_OPTS.index(saver_v)
                                   if saver_v in SAVER_OPTS else 0)
            peran_v = source_row.get("PerennialAnnual","")
            peran   = st.selectbox("Perennial/Annual", PERAN_OPTS,
                                   index=PERAN_OPTS.index(peran_v)
                                   if peran_v in PERAN_OPTS else 0)
            hybrid  = st.text_input("Hybrid-Do Not Save",
                                    value=source_row.get("HybridDoNotSave",""))
            soil_t  = st.text_input("Soil Temperature",
                                    value=source_row.get("SoilTemperature",""))
            germ    = st.text_input("Germination",
                                    value=source_row.get("Germination",""))
        bg_info = st.text_area("Background Info",
                               value=source_row.get("BackgroundInfo",""), height=80)

        if st.form_submit_button("💾  Save as New Record", use_container_width=True):
            fn = int(fn)
            conn = get_db()
            existing = conn.execute(
                "SELECT 1 FROM seeds WHERE FileNumber=?", (fn,)).fetchone()
            if existing:
                st.error(f"File #{fn} already exists. Choose a different number.")
            else:
                db_add({
                    "FileNumber": fn, "Family": family, "Variety": variety,
                    "SeedSource": source, "Comments": comments,
                    "NumSeeds": numseeds, "Season": season,
                    "SeedSaverLevel": saver, "HybridDoNotSave": hybrid,
                    "Edible": edible, "WhereGrown": where,
                    "PerennialAnnual": peran, "GrownBy": grown_by,
                    "Year": year, "SoilTemperature": soil_t,
                    "Germination": germ, "BackgroundInfo": bg_info,
                })
                st.success(f"✅ New seed #{fn} saved as a duplicate of "
                           f"#{source_row['FileNumber']}.")
                st.rerun()


# ─────────────────────────────────────────────────────────────
# PAGE: ADD SEEDS
# ─────────────────────────────────────────────────────────────
def page_add():
    page_header("Add Seeds", "Enter a new seed record into the library")

    next_fn = db_next_fn()
    st.info(f"Next available File Number: **{next_fn}**")

    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            fn      = st.number_input("File Number *", value=next_fn,
                                      min_value=1, step=1)
            family  = st.text_input("Family")
            variety = st.text_input("Variety")
            source  = st.text_input("Seed Source")
            comments= st.text_area("Comments", height=100,
                                   help="Maximum 300 characters for label printing",
                                   max_chars=300)
            grown_by= st.text_input("Grown By")
            where   = st.text_input("Where Grown")
        with c2:
            year    = st.text_input("Year")
            numseeds= st.text_input("# of Seeds")
            edible  = st.text_input("Edible (type 'Edible' if applicable)")
            season  = st.selectbox("Season",           SEASON_OPTS)
            saver   = st.selectbox("Seed Saver Level", SAVER_OPTS)
            peran   = st.selectbox("Perennial/Annual", PERAN_OPTS)
            hybrid  = st.text_input("Hybrid-Do Not Save")
            soil_t  = st.text_input("Soil Temperature")
            germ    = st.text_input("Germination")
        bg_info = st.text_area("Background Info", height=80,
                               help="Maximum 300 characters for label printing",
                               max_chars=300)

        submitted = st.form_submit_button("💾  Save Seed", use_container_width=True)

    if submitted:
        fn = int(fn)
        if not family:
            st.error("Family is required.")
        else:
            # Check duplicate
            conn = get_db()
            existing = conn.execute(
                "SELECT 1 FROM seeds WHERE FileNumber=?", (fn,)).fetchone()
            if existing:
                st.error(f"File #{fn} already exists. Choose a different number.")
            else:
                db_add({
                    "FileNumber": fn, "Family": family, "Variety": variety,
                    "SeedSource": source, "Comments": comments,
                    "NumSeeds": numseeds, "Season": season,
                    "SeedSaverLevel": saver, "HybridDoNotSave": hybrid,
                    "Edible": edible, "WhereGrown": where,
                    "PerennialAnnual": peran, "GrownBy": grown_by,
                    "Year": year, "SoilTemperature": soil_t,
                    "Germination": germ, "BackgroundInfo": bg_info,
                })
                st.success(f"✅ Seed #{fn} — {family} added successfully!")


# ─────────────────────────────────────────────────────────────
# PAGE: REMOVE SEEDS
# ─────────────────────────────────────────────────────────────
def page_remove():
    page_header("Remove Seeds", "Search for and permanently delete seed records")

    col_s, col_b1, col_b2 = st.columns([4, 1, 1])
    with col_s:
        term = st.text_input("Search", placeholder="Family, variety, or file number…",
                             label_visibility="collapsed", key="remove_search")
    with col_b1:
        if st.button("Search", use_container_width=True):
            st.session_state.remove_term = term
    with col_b2:
        if st.button("Show All", use_container_width=True):
            st.session_state.remove_term = ""

    active_term = st.session_state.get("remove_term", "")
    rows = db_search(active_term)

    if not rows:
        st.info("No seeds found.")
        return

    import pandas as pd
    df = pd.DataFrame([{
        "Select": False,
        "File #": r["FileNumber"],
        "Family": r["Family"],
        "Variety": r["Variety"],
        "Season": r["Season"],
        "Year": r["Year"],
    } for r in rows])

    st.caption(f"{len(rows)} records found. Check boxes to select for deletion.")

    edited = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        height=380,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Select", help="Check to mark for deletion", default=False),
        },
        disabled=["File #", "Family", "Variety", "Season", "Year"],
        key="remove_editor",
    )

    selected_fns = [
        int(edited.iloc[i]["File #"])
        for i in range(len(edited))
        if edited.iloc[i]["Select"]
    ]
    n = len(selected_fns)

    if n > 0:
        st.warning(f"**{n} record(s) selected for deletion.**")
        confirm = st.checkbox(
            f"I confirm I want to permanently delete {n} seed record(s)",
            key="remove_confirm")
        if confirm:
            if st.button(f"🗑  Delete {n} Selected Record(s)",
                         type="primary", use_container_width=True):
                db_delete(selected_fns)
                st.success(f"✅ {n} record(s) deleted.")
                st.session_state.remove_term = active_term
                st.rerun()
    else:
        st.info("Check the Select box on one or more rows to delete them.")


# ─────────────────────────────────────────────────────────────
# PAGE: PRINT LABELS
# ─────────────────────────────────────────────────────────────
def page_labels():
    page_header("Print Seed Labels",
                "Avery 94207 — 2″ × 4″ labels, 10 per sheet (2 cols × 5 rows)")

    # Search
    col_s, col_b1, col_b2 = st.columns([4, 1, 1])
    with col_s:
        term = st.text_input("Search", placeholder="Family, variety, or file number…",
                             label_visibility="collapsed", key="label_search")
    with col_b1:
        if st.button("Search", use_container_width=True, key="lbl_search_btn"):
            st.session_state.label_term = term
    with col_b2:
        if st.button("Load All", use_container_width=True):
            st.session_state.label_term = ""

    active_term = st.session_state.get("label_term", "")
    rows = db_search(active_term)

    if not rows:
        st.info("No seeds found.")
        return

    import pandas as pd

    # Build label selection table with qty column
    if "label_qtys" not in st.session_state:
        st.session_state.label_qtys = {}

    df = pd.DataFrame([{
        "Print": st.session_state.label_qtys.get(r["FileNumber"], 0) > 0,
        "File #": r["FileNumber"],
        "Family": r["Family"],
        "Variety": r["Variety"],
        "Season": r["Season"],
        "# Seeds": r["NumSeeds"],
        "Qty": st.session_state.label_qtys.get(r["FileNumber"], 0),
    } for r in rows])

    st.caption("Set **Qty** to 1 or more to include in print job. "
               "Uncheck **Print** or set Qty to 0 to exclude.")
    include_bg = st.checkbox(
        "Also print Background Info as a separate label for each selected seed",
        key="label_include_bg",
    )

    edited = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        height=380,
        column_config={
            "Print": st.column_config.CheckboxColumn(
                "Print", default=False),
            "Qty": st.column_config.NumberColumn(
                "Qty", min_value=0, max_value=99, step=1, default=0),
            "File #": st.column_config.NumberColumn("File #", disabled=True),
        },
        disabled=["File #", "Family", "Variety", "Season", "# Seeds"],
        key="label_editor",
    )

    # Persist qty changes
    for i in range(len(edited)):
        fn  = int(edited.iloc[i]["File #"])
        qty = int(edited.iloc[i]["Qty"])
        if edited.iloc[i]["Print"] and qty == 0:
            qty = 1
        if not edited.iloc[i]["Print"]:
            qty = 0
        st.session_state.label_qtys[fn] = qty

    # Summary
    label_data = []
    row_lookup = {r["FileNumber"]: r for r in rows}
    total_labels = 0
    for fn, qty in st.session_state.label_qtys.items():
        if qty > 0 and fn in row_lookup:
            label_data.append((row_lookup[fn], qty))
            total_labels += qty

    n_seeds = len(label_data)
    st.info(f"**{n_seeds}** seed(s) selected — **{total_labels}** total labels")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("Set All to 1", use_container_width=True):
            for r in rows:
                st.session_state.label_qtys[r["FileNumber"]] = 1
            st.rerun()
    with col_b:
        if st.button("Clear All", use_container_width=True):
            st.session_state.label_qtys = {}
            st.rerun()

    st.markdown("---")

    if n_seeds == 0:
        st.warning("Set Qty > 0 on at least one seed to generate a PDF.")
    else:
        if st.button("🖨  Generate & Download PDF",
                     type="primary", use_container_width=True):
            with st.spinner("Generating PDF…"):
                pdf_bytes = generate_labels_pdf(
                    label_data,
                    include_background=st.session_state.get("label_include_bg", False))
            if pdf_bytes:
                st.download_button(
                    label="⬇️  Download seed_labels.pdf",
                    data=pdf_bytes,
                    file_name="seed_labels.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
                st.success(
                    f"PDF ready! {total_labels} labels across "
                    f"{-(-total_labels // 10)} page(s). "
                    "Print at **Actual Size** (100%) for correct Avery alignment."
                )


# ─────────────────────────────────────────────────────────────
# SIDEBAR NAVIGATION
# ─────────────────────────────────────────────────────────────
def sidebar_nav():
    PAGES = ["Home", "Browse Seeds", "Add Seeds", "Remove Seeds", "Print Labels"]

    # If a home-page button set a nav_target, use it as the default index
    target = st.session_state.pop("nav_target", None)
    if target and target in PAGES:
        default_idx = PAGES.index(target)
        st.session_state["_nav_index"] = default_idx
    current_idx = st.session_state.get("_nav_index", 0)

    with st.sidebar:
        st.markdown("## 🌹 CCMGA\n### Seed Library")
        st.markdown("---")
        page = st.radio(
            "Navigate",
            PAGES,
            index=current_idx,
            key="nav_radio",
            label_visibility="collapsed",
        )
        # Keep index in sync with radio selection
        st.session_state["_nav_index"] = PAGES.index(page)
        st.markdown("---")
        st.markdown(
            "<small>Cochise County Master Gardener Association<br/>"
            "v1.0 — Claude AI + Alan Borhauer</small>",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        if st.button("🔒  Log Out", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()
    return page


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    # Gate — must authenticate before anything else renders
    check_password()

    selected = sidebar_nav()

    if selected == "Home":
        page_home()
    elif selected == "Browse Seeds":
        page_browse()
    elif selected == "Add Seeds":
        page_add()
    elif selected == "Remove Seeds":
        page_remove()
    elif selected == "Print Labels":
        page_labels()


if __name__ == "__main__":
    main()
