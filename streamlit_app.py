#!/usr/bin/env python3
"""
Cochise County Master Gardener Association -- Seed Library
Streamlit Web Application
Run with:  streamlit run streamlit_app.py
"""

import os
import io
import sys
import sqlite3
import json
import tempfile
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import streamlit as st

# -------------------------------------------------------------
# PAGE CONFIG (must be first Streamlit call)
# -------------------------------------------------------------
st.set_page_config(
    page_title="CCMGA Seed Library",
    page_icon="🌹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------------------
# PASSWORD PROTECTION
# -------------------------------------------------------------
def check_password():
    """
    Full auth gate:
      - Existing users: email + password login
      - New users: register -> email verify -> wait for admin approval
      - Admins: access admin panel in sidebar
    Returns True if authenticated and approved.
    """
    # Already authenticated this session
    if st.session_state.get("authenticated"):
        return True

    # Auth step router
    step = st.session_state.get("auth_step", "login")

    # ── Centered card ────────────────────────────────────────────────
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style="background:#1b5e20;padding:24px 32px;border-radius:12px;
                    text-align:center;margin-bottom:16px;">
          <h2 style="color:white;margin:0;">🌹 CCMGA Seed Library</h2>
          <p style="color:#c8e6c9;margin:4px 0 0 0;">
            Cochise County Master Gardener Association</p>
        </div>""", unsafe_allow_html=True)

        if step == "login":
            _auth_login(col)
        elif step == "register":
            _auth_register(col)
        elif step == "verify":
            _auth_verify(col)

    st.stop()
    return False


def _auth_login(col):
    st.markdown("#### Sign In")
    email    = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_pw")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Log In", use_container_width=True, type="primary"):
            if not email or not password:
                st.error("Please enter email and password.")
            else:
                user = user_login(email, password)
                if user is None:
                    st.error("Invalid email or password.")
                elif not user["is_verified"]:
                    st.warning("Email not verified. Check your inbox.")
                    st.session_state.auth_email = email
                    st.session_state.auth_step  = "verify"
                    st.rerun()
                elif not user["is_approved"]:
                    st.warning(
                        "🔒 Account verified but awaiting admin approval. "
                        "You will be notified when access is granted.")
                else:
                    update_last_login(email)
                    st.session_state.authenticated = True
                    st.session_state.user_email    = email
                    st.session_state.user_name     = user["full_name"]
                    st.session_state.user_role     = user["role"]
                    st.session_state.pop("current_page", None)
                    st.session_state.pop("_prev_selected", None)
                    st.rerun()
    with c2:
        if st.button("Register", use_container_width=True):
            st.session_state.auth_step = "register"
            st.rerun()


def _auth_register(col):
    st.markdown("#### Create Account")
    name     = st.text_input("Full Name",            key="reg_name")
    email    = st.text_input("Email",                key="reg_email")
    password = st.text_input("Password",             key="reg_pw",   type="password")
    confirm  = st.text_input("Confirm Password",     key="reg_pw2",  type="password")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Sign Up", use_container_width=True, type="primary"):
            if not all([name, email, password, confirm]):
                st.error("All fields are required.")
            elif password != confirm:
                st.error("Passwords do not match.")
            elif len(password) < 8:
                st.error("Password must be at least 8 characters.")
            else:
                with st.spinner("Creating account..."):
                    result = user_register(email, name, password)
                if result == "ok":
                    st.session_state.auth_email = email.lower().strip()
                    st.session_state.auth_step  = "verify"
                    st.success("Account created! Check your email for the verification code.")
                    st.rerun()
                elif result == "duplicate":
                    st.error("That email is already registered. Try logging in.")
                elif result.startswith("email_failed"):
                    detail = result.replace("email_failed: ", "")
                    st.warning(f"Account created but email failed: {detail}\n\nCheck SMTP secrets. For Gmail use an App Password.")
                    st.session_state.auth_email = email.lower().strip()
                    st.session_state.auth_step  = "verify"
                    st.rerun()
                else:
                    st.error(f"Registration error: {result}")
    with c2:
        if st.button("Back to Login", use_container_width=True):
            st.session_state.auth_step = "login"
            st.rerun()


def _auth_verify(col):
    email = st.session_state.get("auth_email", "")
    st.markdown("#### Verify Your Email")
    st.info(f"A 6-digit code was sent to **{email}**")
    code = st.text_input("Enter 6-digit code", key="verify_code", max_chars=6)

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Verify", use_container_width=True, type="primary"):
            if not code or len(code) != 6:
                st.error("Enter the 6-digit code.")
            else:
                result = user_verify(email, code.strip())
                if result == "ok":
                    st.success(
                        "✅ Email verified! Your account is pending "
                        "admin approval. You will receive an email when approved.")
                    st.session_state.auth_step = "login"
                    st.rerun()
                elif result == "expired":
                    st.error("Code expired. Request a new one.")
                else:
                    st.error("Invalid code. Please try again.")
                    
    with c2:
        # Fixed: Changed width="stretch" to use_container_width=True
        if st.button("Resend Code", use_container_width=True):
            with st.spinner("Sending..."):
                success = user_resend_code(email)
            # Fixed: Moved the success check inside the button scope
            if success:
                st.success("New code sent!")
            else:
                st.error("Failed to send. Contact admin.")
        
    with c3:
        if st.button("Back to Login", use_container_width=True):
            st.session_state.auth_step = "login"
            st.rerun()


# -------------------------------------------------------------
# GLOBAL STYLES
# -------------------------------------------------------------
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


# -------------------------------------------------------------
# DATABASE -- loaded once per session into st.session_state
# -------------------------------------------------------------
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

# -------------------------------------------------------------
# POSTGRESQL DATABASE LAYER
# -------------------------------------------------------------

def get_pg_conn():
    """Return a psycopg2 connection using st.secrets["DATABASE_URL"]."""
    import psycopg2
    import psycopg2.extras
    url = st.secrets["DATABASE_URL"]
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


CREATE_USERS_SQL = """
    CREATE TABLE IF NOT EXISTS app_users (
        id             SERIAL PRIMARY KEY,
        email          TEXT UNIQUE NOT NULL,
        full_name      TEXT,
        password_hash  TEXT NOT NULL,
        is_verified    BOOLEAN DEFAULT FALSE,
        is_approved    BOOLEAN DEFAULT FALSE,
        verify_code    TEXT,
        verify_expires TIMESTAMP,
        created_at     TIMESTAMP DEFAULT NOW(),
        last_login     TIMESTAMP,
        role           TEXT DEFAULT 'user'
    )
"""


def _ensure_table():
    """Create the seeds and app_users tables if they don't exist."""
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute(CREATE_SQL)
    cur.execute(CREATE_USERS_SQL)
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
        st.session_state["db_msg"] = f"[x] Initial load error: {e}"


def init_db():
    """Called once per session -- ensures table exists and has data."""
    if st.session_state.get("db_ready"):
        return
    try:
        _ensure_table()
        if not _seed_table_populated():
            _load_from_xlsx_to_pg()
        else:
            count = db_count()
            st.session_state["db_status"] = "ok"
            st.session_state["db_msg"] = f"✅ Connected -- {count:,} seeds in PostgreSQL."
        st.session_state["db_ready"] = True
    except Exception as e:
        st.session_state["db_status"] = "error"
        st.session_state["db_msg"] = f"[x] Database connection error: {e}"


# -- CRUD -----------------------------------------------------
def sf(row: dict, key: str) -> str:
    """Safely get a string field from a PostgreSQL row -- never returns None."""
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
    # Coerce None ? "" but keep FileNumber as int
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
    for download. No file writing needed -- PG is the source of truth.
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


# =============================================================
# USER AUTHENTICATION FUNCTIONS
# =============================================================

def _hash_password(plain: str) -> str:
    import bcrypt
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _check_password_hash(plain: str, hashed: str) -> bool:
    import bcrypt
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _send_verification_email(to_email: str, code: str) -> tuple:
    """Send 6-digit code via SMTP. Returns (success, error_message)."""
    required = ["SMTP_SERVER", "SMTP_PORT", "EMAIL_FROM", "EMAIL_PASSWORD"]
    missing = [k for k in required if k not in st.secrets]
    if missing:
        return False, f"Missing secrets: {', '.join(missing)}"
    try:
        msg = MIMEText(
            f"Your 6-digit verification code for the CCMGA Seed Library is:\n\n"
            f"    {code}\n\nThis code expires in 15 minutes."
        )
        msg["Subject"] = "Verify Your CCMGA Seed Library Account"
        msg["From"]    = st.secrets["EMAIL_FROM"]
        msg["To"]      = to_email
        with smtplib.SMTP(st.secrets["SMTP_SERVER"],
                          int(st.secrets["SMTP_PORT"])) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(st.secrets["EMAIL_FROM"], st.secrets["EMAIL_PASSWORD"])
            server.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)


def user_login(email: str, password: str) -> dict | None:
    """Return user dict if credentials valid, else None."""
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute(
        "SELECT * FROM app_users WHERE email = %s", (email.lower().strip(),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    user = dict(row)
    if not _check_password_hash(password, user["password_hash"]):
        return None
    return user


def user_register(email: str, full_name: str, password: str) -> str:
    """
    Insert new unverified user. Returns 'ok', 'duplicate', or 'error'.
    """
    code    = str(random.randint(100000, 999999))
    expires = (datetime.now() + timedelta(minutes=15)).isoformat()
    try:
        conn = get_pg_conn()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO app_users
                (email, full_name, password_hash,
                 is_verified, is_approved, verify_code, verify_expires, role)
            VALUES (%s, %s, %s, FALSE, FALSE, %s, %s, 'user')
        """, (email.lower().strip(), full_name,
              _hash_password(password), code, expires))
        conn.commit()
        _send_admin_notification(
    full_name,
    email
)
        cur.close()
        conn.close()
        # Send email
        ok, err = _send_verification_email(email, code)
        if ok:
            return "ok"
        return f"email_failed: {err}"
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return "duplicate"
        return f"error: {e}"


def user_verify(email: str, code: str) -> str:
    """
    Verify the 6-digit code. Returns 'ok', 'expired', or 'invalid'.
    """
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM app_users WHERE email = %s",
                (email.lower().strip(),))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return "invalid"
    user = dict(row)
    if user["verify_code"] != code:
        cur.close(); conn.close()
        return "invalid"
    # Use timezone-aware comparison to handle PostgreSQL timestamptz
    from datetime import timezone
    expires_raw = user["verify_expires"]
    if expires_raw is not None:
        if hasattr(expires_raw, "tzinfo") and expires_raw.tzinfo is not None:
            now = datetime.now(timezone.utc)
        else:
            now = datetime.now()
        if expires_raw < now:
            cur.close(); conn.close()
            return "expired"
    cur.execute(
        """
        UPDATE app_users
        SET
            is_verified = TRUE,
            verify_code = NULL,
            verify_expires = NULL
        WHERE email = %s
        """,
        (email.lower().strip(),)
    )
    conn.commit()
    cur.close()
    conn.close()
    return "ok"
    

def user_resend_code(email: str) -> bool:
    """Generate a new code and resend verification email."""
    code    = str(random.randint(100000, 999999))
    expires = (datetime.now() + timedelta(minutes=15)).isoformat()
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE app_users
        SET verify_code = %s, verify_expires = %s
        WHERE email = %s
    """, (code, expires, email.lower().strip()))
    conn.commit()
    cur.close()
    conn.close()
    success, _ = _send_verification_email(
        email,
        code
)
    return success

def admin_get_pending() -> list[dict]:
    """Return all verified-but-not-approved users."""
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, email, full_name, created_at
        FROM app_users
        WHERE is_verified = TRUE AND is_approved = FALSE
        ORDER BY created_at
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def admin_get_all_users() -> list[dict]:
    """Return all users for admin management."""
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, email, full_name, is_verified, is_approved,
               role, created_at, last_login
        FROM app_users ORDER BY created_at DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def admin_approve(user_id: int):
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE app_users SET is_approved = TRUE WHERE id = %s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()


def admin_revoke(user_id: int):
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE app_users SET is_approved = FALSE WHERE id = %s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()


def admin_delete_user(user_id: int):
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM app_users WHERE id = %s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()


def update_last_login(email: str):
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE app_users SET last_login = NOW() WHERE email = %s",
        (email.lower().strip(),))
    conn.commit()
    cur.close()
    conn.close()

def _send_admin_notification(name,email):

    admin_email = st.secrets["ADMIN_EMAIL"]

    msg = MIMEText(
        f"""
New account awaiting approval

Name:

{name}

Email:

{email}

Login to admin panel.
"""
    )

    msg["Subject"]="New User Registration"

    msg["From"]=st.secrets["EMAIL_FROM"]

    msg["To"]=admin_email

    try:

        with smtplib.SMTP(
            st.secrets["SMTP_SERVER"],
            int(st.secrets["SMTP_PORT"])
        ) as srv:

            srv.starttls()

            srv.login(
                st.secrets["EMAIL_FROM"],
                st.secrets["EMAIL_PASSWORD"]
            )

            srv.send_message(msg)

    except:

        pass
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
    MARGIN_LEFT     = 0.1875 * inch
    MARGIN_RIGHT    = 0.1875 * inch
    GUTTER_W = 0.125 * inch
    LABEL_W = (PAGE_W - MARGIN_LEFT - MARGIN_RIGHT - GUTTER_W) / 2
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
                # -- Background Info label -- clean, no dividers, full width --
                # Generous padding for readability
                BG_PAD = 10
                full_w = LABEL_W - BG_PAD * 2
                full_h = LABEL_H - BG_PAD * 2

                # Title: "Family -- Background Info"
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
                    Paragraph(f"{variety} -- Background Information", bg_title_sty),
                    Paragraph(bg_info, bg_body_sty),
                ]
                Frame(lx + BG_PAD, ly + BG_PAD, full_w, full_h,
                      leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0,
                      showBoundary=0).addFromList(all_bg, c)

            else:
                # -- Standard seed label ----------------------------
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
                    f"* HYBRID -- DO NOT SAVE SEEDS *",
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


# -------------------------------------------------------------
# SHARED UI HELPERS
# -------------------------------------------------------------
def show_download_bar():
    """Show download button if updated xlsx bytes are available."""
    xlsx_bytes = st.session_state.get("xlsx_download_bytes")
    if xlsx_bytes:
        st.download_button(
            label="  Download Updated _SEED_LIBRARY_PARSED.xlsx",
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


# -------------------------------------------------------------
# PAGE: HOME
# -------------------------------------------------------------
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
| **Built for** | Cochise County Master Gardener Association |
| **Labels** | For use with Avery 94207 Labels (2" x 4", 10 per sheet) |
| **Version** | 2.1 6.8.2026 |
    """)

    # -- Seeds with comments or background info over 300 chars -------
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


# -------------------------------------------------------------
# PAGE: BROWSE
# -------------------------------------------------------------
def page_browse():
    page_header("Browse Seeds", "Search, sort, view details, and edit records")

    # Search bar
    col_s, col_b1, col_b2 = st.columns([4, 1, 1])
    with col_s:
        term = st.text_input("Search", placeholder="Family, variety, or file number...",
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

    # Deduplicate by Family+Variety -- keep first occurrence, count duplicates
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

    # -- Detail / Edit panel -------------------------------------
    st.markdown("#### View or Edit a Record")
    fn_options = {f"#{r['FileNumber']}  {r['Family']} -- {r['Variety']}": r["FileNumber"]
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
            val = row.get(f, "") or "--"
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
            st.markdown(f"**{FIELD_LABELS[f]}:** {row.get(f,'') or '--'}")

    # Background Info -- always shown in full with its own section
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

        if st.form_submit_button("Save Changes", use_container_width=True):
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
    st.info(f"Duplicating **#{source_row['FileNumber']} {source_row['Family']} -- "
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

        if st.form_submit_button("Save as New Record", use_container_width=True):
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


# -------------------------------------------------------------
# PAGE: ADD SEEDS
# -------------------------------------------------------------
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

        submitted = st.form_submit_button("Save Seed", use_container_width=True)

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
                st.success(f"✅ Seed #{fn} -- {family} added successfully!")
                show_download_bar()


# -------------------------------------------------------------
# PAGE: REMOVE SEEDS
# -------------------------------------------------------------
def page_remove():
    page_header("Remove Seeds", "Search for and permanently delete seed records")

    col_s, col_b1, col_b2 = st.columns([4, 1, 1])
    with col_s:
        term = st.text_input("Search", placeholder="Family, variety, or file number...",
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
            if st.button(f"Delete {n} Selected Record(s)",
                         type="primary", use_container_width=True):
                db_delete(selected_fns)
                st.success(f"✅ {n} record(s) deleted.")
                show_download_bar()
                st.session_state.remove_term = active_term
                st.rerun()
    else:
        st.info("Check the Select box on one or more rows to delete them.")


# -------------------------------------------------------------
# PAGE: PRINT LABELS
# -------------------------------------------------------------
def page_labels():
    page_header("Print Seed Labels",
                "Avery 94207 -- 2 inch x 4 inch labels, 10 per sheet (2 cols x 5 rows)")

    # Search bar
    col_s, col_b1, col_b2 = st.columns([4, 1, 1])
    with col_s:
        term = st.text_input("Search", placeholder="Family, variety, or file number...",
                             label_visibility="collapsed", key="label_search")
    with col_b1:
        if st.button("Search", use_container_width=True, key="lbl_search_btn"):
            st.session_state.label_term = term
            st.rerun()
    with col_b2:
        if st.button("Load All", use_container_width=True):
            st.session_state.label_term = ""
            st.rerun()

    # Auto-init on first visit
    if "label_term" not in st.session_state:
        st.session_state.label_term = ""
    if "label_qtys" not in st.session_state:
        st.session_state.label_qtys = {}

    rows = db_search(st.session_state.label_term)

    if not rows:
        if st.session_state.label_term:
            st.info(f"No seeds match. Click Load All.")
        else:
            st.warning("No seeds found in database.")
        return

    st.caption(f"{len(rows)} seed(s) loaded. Set Qty >= 1 to include in print job.")

    include_bg = st.checkbox(
        "Also print Background Info as a separate label (only for seeds that have it)",
        key="label_include_bg",
    )

    # Per-seed rows: checkbox + qty number input
    st.markdown("**Select seeds and quantities:**")
    hdr = st.columns([1, 4, 4, 2, 2])
    hdr[0].markdown("**Print**")
    hdr[1].markdown("**Family**")
    hdr[2].markdown("**Variety**")
    hdr[3].markdown("**Season**")
    hdr[4].markdown("**Qty**")
    st.divider()

    for r in rows:
        fn      = int(r["FileNumber"])
        cur_qty = st.session_state.label_qtys.get(fn, 0)
        cols    = st.columns([1, 4, 4, 2, 2])
        checked = cols[0].checkbox(
            "", value=cur_qty > 0,
            key=f"lbl_chk_{fn}",
            label_visibility="collapsed")
        cols[1].write(sf(r, "Family"))
        cols[2].write(sf(r, "Variety"))
        cols[3].write(sf(r, "Season"))
        new_qty = cols[4].number_input(
            "", min_value=0, max_value=99,
            value=max(cur_qty, 1 if checked else 0),
            step=1, key=f"lbl_qty_{fn}",
            label_visibility="collapsed")
        if checked and new_qty == 0:
            new_qty = 1
        if not checked:
            new_qty = 0
        st.session_state.label_qtys[fn] = new_qty

    # Summary
    st.divider()
    label_data   = []
    row_lookup   = {int(r["FileNumber"]): r for r in rows}
    total_labels = 0
    for fn, qty in st.session_state.label_qtys.items():
        if qty > 0 and fn in row_lookup:
            label_data.append((row_lookup[fn], qty))
            total_labels += qty

    n_seeds = len(label_data)
    st.info(f"**{n_seeds}** seed(s) selected -- **{total_labels}** total labels")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Set All to 1", use_container_width=True):
            for r in rows:
                st.session_state.label_qtys[int(r["FileNumber"])] = 1
            st.rerun()
    with col_b:
        if st.button("Clear All", use_container_width=True):
            st.session_state.label_qtys = {}
            st.rerun()

    st.markdown("---")
    if n_seeds == 0:
        st.warning("Set Qty to 1 or more on at least one seed.")
    else:
        if st.button("Generate & Download PDF",
                     type="primary", use_container_width=True):
            with st.spinner("Generating PDF..."):
                pdf_bytes = generate_labels_pdf(
                    label_data,
                    include_background=st.session_state.get("label_include_bg", False))
            if pdf_bytes:
                st.download_button(
                    label="Download seed_labels.pdf",
                    data=pdf_bytes,
                    file_name="seed_labels.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
                st.success(
                    f"PDF ready -- {total_labels} labels across "
                    f"{-(-total_labels // 10)} page(s). "
                    "Print at Actual Size (100%).")


def page_admin():
    """Admin panel -- manage user approvals and accounts."""
    if st.session_state.get("user_role") != "admin":
        st.error("Access denied.")
        return

    page_header("Admin Panel", "Manage user accounts and approvals")

    tab1, tab2 = st.tabs(["Pending Approvals", "All Users"])

    with tab1:
        pending = admin_get_pending()
        if not pending:
            st.success("No accounts waiting for approval.")
        else:
            st.warning(f"{len(pending)} account(s) awaiting approval.")
            for u in pending:
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.markdown(
                    f"**{u['full_name']}**  \n{u['email']}  \n"
                    f"*Registered: {str(u.get('created_at',''))[:10]}*")
                if c2.button("Approve", key=f"apr_{u['id']}",
                             use_container_width=True, type="primary"):
                    admin_approve(u["id"])
                    st.session_state["current_page"] = "admin"
                    # Notify user by email
                    try:
                        msg = MIMEText(
                            f"Hello {u['full_name']},\n\n"
                            "Your CCMGA Seed Library account has been approved!\n"
                            "You can now log in at the app URL.\n\n"
                            "Cochise County Master Gardener Association")
                        msg["Subject"] = "CCMGA Seed Library -- Account Approved"
                        msg["From"]    = st.secrets["EMAIL_FROM"]
                        msg["To"]      = u["email"]
                        with smtplib.SMTP(st.secrets["SMTP_SERVER"],
                                          int(st.secrets["SMTP_PORT"])) as srv:
                            srv.starttls()
                            srv.login(st.secrets["EMAIL_FROM"],
                                      st.secrets["EMAIL_PASSWORD"])
                            srv.send_message(msg)
                    except Exception:
                        pass
                    st.rerun()
                if c3.button("Deny", key=f"deny_{u['id']}",
                             use_container_width=True):
                    admin_delete_user(u["id"])
                    st.session_state["current_page"] = "admin"
                    st.rerun()
                st.divider()

    with tab2:
        all_users = admin_get_all_users()
        import pandas as pd
        df = pd.DataFrame([{
            "Name":       u.get("full_name",""),
            "Email":      u.get("email",""),
            "Role":       u.get("role","user"),
            "Verified":   "Yes" if u.get("is_verified") else "No",
            "Approved":   "Yes" if u.get("is_approved") else "No",
            "Registered": str(u.get("created_at",""))[:10],
            "Last Login":  str(u.get("last_login",""))[:10] if u.get("last_login") else "Never",
        } for u in all_users])
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Manage User")
        emails = [u["email"] for u in all_users]
        sel_email = st.selectbox("Select user", emails, key="admin_sel")
        sel_user  = next((u for u in all_users if u["email"] == sel_email), None)
        if sel_user:
            c1, c2, c3 = st.columns(3)
            if sel_user["is_approved"]:
                if c1.button("Revoke Access", use_container_width=True):
                    admin_revoke(sel_user["id"])
                    st.rerun()
            else:
                if c1.button("Approve", use_container_width=True,
                             type="primary"):
                    admin_approve(sel_user["id"])
                    st.rerun()
            new_role = c2.selectbox(
                "Role", ["user","admin"],
                index=0 if sel_user["role"] == "user" else 1,
                key="role_sel")
            if c2.button("Set Role", use_container_width=True):
                conn = get_pg_conn()
                cur  = conn.cursor()
                cur.execute(
                    "UPDATE app_users SET role = %s WHERE id = %s",
                    (new_role, sel_user["id"]))
                conn.commit(); cur.close(); conn.close()
                st.rerun()
            if c3.button("Delete User", use_container_width=True):
                if sel_user["role"] != "admin":
                    admin_delete_user(sel_user["id"])
                    st.rerun()
                else:
                    st.error("Cannot delete an admin account.")


def sidebar_nav():
    PAGES = ["Home", "Browse Seeds", "Add Seeds", "Remove Seeds", "Print Labels"]

    target = st.session_state.pop("nav_target", None)
    if target and target in PAGES:
        st.session_state["_nav_index"] = PAGES.index(target)
    current_idx = st.session_state.get("_nav_index", 0)

    with st.sidebar:
        st.markdown("## 🌹 CCMGA\n### Seed Library")
        # Show logged-in user
        uname = st.session_state.get("user_name", "")
        urole = st.session_state.get("user_role", "user")
        if uname:
            st.markdown(f"**{uname}**  "
                        f"{'(Admin)' if urole == 'admin' else ''}")
        st.markdown("---")

        page = st.radio(
            "Navigate",
            PAGES,
            index=current_idx,
            key="nav_radio",
            label_visibility="collapsed",
        )
        st.session_state["_nav_index"] = PAGES.index(page)
        st.markdown("---")

        # Admin panel link
        if urole == "admin":
            is_on_admin = st.session_state.get("current_page") == "admin"
            if st.button("Admin Panel" + (" (active)" if is_on_admin else ""),
                         use_container_width=True):
                st.session_state["current_page"] = "admin"
                st.rerun()

        st.markdown(
            "<small>Cochise County Master Gardener Association<br/>"
            "v3.0 6.9.2026 Alan Borhauer</small>",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        if st.button("🔒 Log Out", use_container_width=True):
            for k in ["authenticated","user_email","user_name",
                      "user_role","auth_step","auth_email"]:
                st.session_state.pop(k, None)
            st.rerun()
    return page


# -------------------------------------------------------------
# MAIN
# -------------------------------------------------------------
def main():
    # Gate -- must authenticate before anything else renders
    check_password()

    selected = sidebar_nav()

    # "current_page" persists until user clicks a sidebar radio item
    # Clicking a radio item clears current_page so we go back to normal nav
    # We detect a radio change by storing the previous selection
    prev = st.session_state.get("_prev_selected", selected)
    if selected != prev:
        # User clicked a different radio item -- leave admin mode
        st.session_state.pop("current_page", None)
    st.session_state["_prev_selected"] = selected

    current_page = st.session_state.get("current_page", "")
    if current_page == "admin":
        page_admin()
        return

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
