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
import json
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

COL_HEADER_MAP = {
    "FileNumber":      "FileNumber",
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
SHEET_HEADERS = list(COL_HEADER_MAP.values())

CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS seeds (
        "FileNumber"      INTEGER PRIMARY KEY,
        "Family"          TEXT,
        "Variety"         TEXT,
        "SeedSource"      TEXT,
        "Comments"        TEXT,
        "NumSeeds"        TEXT,
        "Season"          TEXT,
        "SeedSaverLevel"  TEXT,
        "HybridDoNotSave" TEXT,
        "Edible"          TEXT,
        "WhereGrown"      TEXT,
        "PerennialAnnual" TEXT,
        "GrownBy"         TEXT,
        "Year"            TEXT,
        "SoilTemperature" TEXT,
        "Germination"     TEXT,
        "BackgroundInfo"  TEXT
    )
"""

# ─────────────────────────────────────────────────────────────
# POSTGRESQL DATABASE LAYER
# ─────────────────────────────────────────────────────────────

def get_pg_conn():
    """Return a psycopg2 connection using st.secrets["DATABASE_URL"]."""
    import psycopg2
    import psycopg2.extras
    url = st.secrets["DATABASE_URL"]
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


def _ensure_table():
    """Create the seeds table if it doesn't exist."""
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute(CREATE_SQL)
    conn.commit()
    cur.close()
    conn.close()


def _seed_table_populated() -> bool:
    """Return True if the seeds table has at least one row."""
    try:
        conn = get_pg_conn()
        cur  = conn.cursor()
        cur.execute('SELECT 1 FROM seeds LIMIT 1')
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row is not None
    except Exception:
        return False


def _load_from_xlsx_to_pg():
    """
    One-time seed load: read the local xlsx and INSERT into PostgreSQL.
    Only runs if the table is empty.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    xlsx_path  = None
    for d in [script_dir, os.path.dirname(script_dir), os.getcwd()]:
        cand = os.path.join(d, "_SEED_LIBRARY_PARSED.xlsx")
        if os.path.exists(cand):
            xlsx_path = cand
            break

    if not xlsx_path:
        st.session_state["db_status"] = "warning"
        st.session_state["db_msg"] = (
            "⚠️ PostgreSQL table is empty and no xlsx found to seed it. "
            "Upload _SEED_LIBRARY_PARSED.xlsx alongside the app for initial load.")
        return

    try:
        import openpyxl
        wb       = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        ws       = wb.active
        all_rows = list(ws.iter_rows(values_only=True))
        wb.close()

        if not all_rows:
            raise ValueError("Spreadsheet is empty.")

        headers = [str(h).strip() if h is not None else "" for h in all_rows[0]]

        def ci(name):
            try:    return headers.index(name)
            except: return -1

        idx = {k: ci(v) for k, v in COL_HEADER_MAP.items()}

        def gv(rv, key):
            i = idx.get(key, -1)
            if i < 0 or i >= len(rv): return ""
            v = rv[i]
            return str(v).strip() if v is not None else ""

        conn = get_pg_conn()
        cur  = conn.cursor()
        inserted = 0
        for rv in all_rows[1:]:
            fn_raw = gv(rv, "FileNumber")
            if not fn_raw or fn_raw == "None": continue
            try:    fn = int(float(fn_raw))
            except: continue
            yr = gv(rv, "Year")
            try:    yr = str(int(float(yr))) if yr and yr != "None" else ""
            except: pass
            cur.execute("""
                INSERT INTO seeds
                ("FileNumber","Family","Variety","SeedSource","Comments",
                 "NumSeeds","Season","SeedSaverLevel","HybridDoNotSave",
                 "Edible","WhereGrown","PerennialAnnual","GrownBy","Year",
                 "SoilTemperature","Germination","BackgroundInfo")
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT ("FileNumber") DO NOTHING
            """, (fn,
                  gv(rv,"Family"),      gv(rv,"Variety"),
                  gv(rv,"SeedSource"),  gv(rv,"Comments"),
                  gv(rv,"NumSeeds"),    gv(rv,"Season"),
                  gv(rv,"SeedSaverLevel"), gv(rv,"HybridDoNotSave"),
                  gv(rv,"Edible"),      gv(rv,"WhereGrown"),
                  gv(rv,"PerennialAnnual"), gv(rv,"GrownBy"), yr,
                  gv(rv,"SoilTemperature"), gv(rv,"Germination"),
                  gv(rv,"BackgroundInfo")))
            inserted += 1
        conn.commit()
        cur.close()
        conn.close()
        st.session_state["db_status"] = "ok"
        st.session_state["db_msg"] = f"✅ Loaded {inserted} seeds into PostgreSQL."
    except Exception as e:
        import traceback; traceback.print_exc()
        st.session_state["db_status"] = "error"
        st.session_state["db_msg"] = f"❌ Initial load error: {e}"


def init_db():
    """Called once per session — ensures table exists and has data."""
    if st.session_state.get("db_ready"):
        return
    try:
        _ensure_table()
        if not _seed_table_populated():
            _load_from_xlsx_to_pg()
        else:
            count = db_count()
            st.session_state["db_status"] = "ok"
            st.session_state["db_msg"] = f"✅ Connected — {count:,} seeds in PostgreSQL."
        st.session_state["db_ready"] = True
    except Exception as e:
        st.session_state["db_status"] = "error"
        st.session_state["db_msg"] = f"❌ Database connection error: {e}"


# ── CRUD ─────────────────────────────────────────────────────
def sf(row: dict, key: str) -> str:
    """Safely get a string field from a PostgreSQL row — never returns None."""
    v = row.get(key) if isinstance(row, dict) else None
    return str(v).strip() if v is not None else ""


def db_search(term: str = "") -> list[dict]:
    conn = get_pg_conn()
    cur  = conn.cursor()
    if term:
        t = f"%{term.lower()}%"
        cur.execute("""
            SELECT * FROM seeds
            WHERE LOWER(CAST("FileNumber" AS TEXT)) LIKE %s
               OR LOWER("Family")  LIKE %s
               OR LOWER("Variety") LIKE %s
            ORDER BY "FileNumber"
        """, (t, t, t))
    else:
        cur.execute('SELECT * FROM seeds ORDER BY "FileNumber"')
    # Coerce None → "" but keep FileNumber as int
    def clean_row(r):
        d = dict(r)
        return {k: (int(v) if k == "FileNumber" and v is not None
                    else str(v).strip() if v is not None else "")
                for k, v in d.items()}
    rows = [clean_row(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def db_add(data: dict):
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO seeds
        ("FileNumber","Family","Variety","SeedSource","Comments",
         "NumSeeds","Season","SeedSaverLevel","HybridDoNotSave",
         "Edible","WhereGrown","PerennialAnnual","GrownBy","Year",
         "SoilTemperature","Germination","BackgroundInfo")
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, tuple(data.get(c, "") for c in COLS))
    conn.commit()
    cur.close()
    conn.close()


def db_update(fn: int, data: dict):
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE seeds SET
            "Family"=%s, "Variety"=%s, "SeedSource"=%s, "Comments"=%s,
            "NumSeeds"=%s, "Season"=%s, "SeedSaverLevel"=%s,
            "HybridDoNotSave"=%s, "Edible"=%s, "WhereGrown"=%s,
            "PerennialAnnual"=%s, "GrownBy"=%s, "Year"=%s,
            "SoilTemperature"=%s, "Germination"=%s, "BackgroundInfo"=%s
        WHERE "FileNumber"=%s
    """, (
        data.get("Family",""),        data.get("Variety",""),
        data.get("SeedSource",""),    data.get("Comments",""),
        data.get("NumSeeds",""),      data.get("Season",""),
        data.get("SeedSaverLevel",""),data.get("HybridDoNotSave",""),
        data.get("Edible",""),        data.get("WhereGrown",""),
        data.get("PerennialAnnual",""),data.get("GrownBy",""),
        data.get("Year",""),          data.get("SoilTemperature",""),
        data.get("Germination",""),   data.get("BackgroundInfo",""),
        fn,
    ))
    conn.commit()
    cur.close()
    conn.close()


def db_delete(file_numbers: list[int]):
    conn = get_pg_conn()
    cur  = conn.cursor()
    for fn in file_numbers:
        cur.execute('DELETE FROM seeds WHERE "FileNumber"=%s', (fn,))
    conn.commit()
    cur.close()
    conn.close()


def db_next_fn() -> int:
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute('SELECT MAX("FileNumber") FROM seeds')
    row = cur.fetchone()
    cur.close()
    conn.close()
    val = row["max"] if row else None
    return (val + 1) if val else 1001


def db_count() -> int:
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM seeds")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["count"] if row else 0


def db_over_limit() -> list[dict]:
    """Return seeds where Comments or BackgroundInfo exceeds 300 chars."""
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT "FileNumber", "Family", "Variety",
               LENGTH("Comments")       AS clen,
               LENGTH("BackgroundInfo") AS blen
        FROM seeds
        WHERE LENGTH("Comments") > 300
           OR LENGTH("BackgroundInfo") > 300
        ORDER BY "Family", "Variety"
    """)
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        rows.append({
            "FileNumber": d.get("FileNumber"),
            "Family":     str(d.get("Family") or ""),
            "Variety":    str(d.get("Variety") or ""),
            "clen":       int(d.get("clen") or 0),
            "blen":       int(d.get("blen") or 0),
        })
    cur.close()
    conn.close()
    return rows


def save_to_xlsx():
    """
    Build an in-memory xlsx from PostgreSQL data and store in session
    for download. No file writing needed — PG is the source of truth.
    """
    try:
        import openpyxl
        rows = db_search("")
        wb   = openpyxl.Workbook()
        ws   = wb.active
        ws.title = "Seeds"
        ws.append(SHEET_HEADERS)
        for row in rows:
            ws.append([row.get(k, "") for k in COL_HEADER_MAP.keys()])
        buf = io.BytesIO()
        wb.save(buf)
        st.session_state["xlsx_download_bytes"] = buf.getvalue()
    except Exception as e:
        print(f"xlsx build error: {e}")


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
        # Add same qty of background labels as seed labels (only if bg info exists)
        if include_background and (row.get("BackgroundInfo") or "").strip():
            for _ in range(qty):
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
def show_download_bar():
    """Show download button if updated xlsx bytes are available."""
    xlsx_bytes = st.session_state.get("xlsx_download_bytes")
    if xlsx_bytes:
        st.download_button(
            label="⬇️  Download Updated _SEED_LIBRARY_PARSED.xlsx",
            data=xlsx_bytes,
            file_name="_SEED_LIBRARY_PARSED.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Download and replace your local xlsx file to keep changes permanent.",
            use_container_width=True,
        )


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
    init_db()  # ensure DB is loaded
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
    show_download_bar()
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
    over_limit = db_over_limit()

    if over_limit:
        st.markdown("---")
        st.warning(f"⚠️ **{len(over_limit)} seed(s) have text exceeding the "
                   "300-character label limit.** Only the first 300 characters "
                   "will print. Edit these records to shorten the text.")
        rows_display = []
        for r in over_limit:
            issues = []
            clen = int(r.get("clen") or 0)
            blen = int(r.get("blen") or 0)
            if clen > 300:
                issues.append(f"Comments: {clen} chars ({clen-300} over)")
            if blen > 300:
                issues.append(f"Background Info: {blen} chars ({blen-300} over)")
            rows_display.append({
                "File #":  r.get("FileNumber", ""),
                "Family":  sf(r, "Family"),
                "Variety": sf(r, "Variety"),
                "Issue":   "  |  ".join(issues),
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
        key = (sf(r,"Family").lower(), sf(r,"Variety").lower())
        count_map[key] = count_map.get(key, 0) + 1
    for r in rows:
        key = (sf(r,"Family").lower(), sf(r,"Variety").lower())
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
        key = (sf(r,"Family").lower(), sf(r,"Variety").lower())
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
    bg = str(row.get("BackgroundInfo") or "").strip()
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
            _conn = get_pg_conn()
            _cur  = _conn.cursor()
            _cur.execute('SELECT 1 FROM seeds WHERE "FileNumber"=%s', (fn,))
            existing = _cur.fetchone()
            _cur.close()
            _conn.close()
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
                show_download_bar()
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
            _conn = get_pg_conn()
            _cur  = _conn.cursor()
            _cur.execute('SELECT 1 FROM seeds WHERE "FileNumber"=%s', (fn,))
            existing = _cur.fetchone()
            _cur.close()
            _conn.close()
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
                show_download_bar()


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
        "Family": sf(r,"Family"),
        "Variety": sf(r,"Variety"),
        "Season": sf(r,"Season"),
        "Year": sf(r,"Year"),
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
                show_download_bar()
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
        "Family": sf(r,"Family"),
        "Variety": sf(r,"Variety"),
        "Season": sf(r,"Season"),
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
    row_lookup = {int(r["FileNumber"]): r for r in rows}
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
