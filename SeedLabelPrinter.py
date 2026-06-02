#!/usr/bin/env python3
"""
Cochise County Master Gardener Seed Library
Seed Label PDF Generator - Companion Script
Generates 4x2 seed labels on standard US Letter paper
"""

import sys
import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import textwrap

# Find reportlab across ALL possible install locations (Mac pip3.8, pip3, homebrew, etc.)
import site, glob, subprocess

def _add_all_site_paths():
    search = []
    try: search += site.getsitepackages()
    except Exception: pass
    try: search += [site.getusersitepackages()]
    except Exception: pass
    # Mac common patterns for all Python versions
    for pat in [
        '/Library/Python/*/site-packages',
        '/Library/Python/*/lib/python/site-packages',
        os.path.expanduser('~/Library/Python/*/site-packages'),
        os.path.expanduser('~/Library/Python/*/lib/python/site-packages'),
        '/usr/local/lib/python*/site-packages',
        '/usr/local/lib/python*/dist-packages',
        '/opt/homebrew/lib/python*/site-packages',
        '/opt/homebrew/lib/python*/dist-packages',
        '/opt/homebrew/opt/python*/lib/python*/site-packages',
    ]:
        search += glob.glob(pat)
    # Ask pip where reportlab lives — most reliable method
    for pip_cmd in ('pip3.8', 'pip3.9', 'pip3.10', 'pip3.11', 'pip3.12', 'pip3', 'pip'):
        try:
            out = subprocess.check_output(
                [pip_cmd, 'show', 'reportlab'],
                stderr=subprocess.DEVNULL, text=True, timeout=5)
            for line in out.splitlines():
                if line.lower().startswith('location:'):
                    loc = line.split(':', 1)[1].strip()
                    if loc not in search:
                        search.insert(0, loc)
            break  # found it, stop trying
        except Exception:
            pass
    for p in search:
        if p and p not in sys.path:
            sys.path.insert(0, p)

_add_all_site_paths()

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, PageBreak)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    HAS_REPORTLAB = True
    print(f"ReportLab found OK")
except ImportError as _e:
    HAS_REPORTLAB = False
    print(f"ReportLab not found: {_e}")

# Try to import pandas for data loading
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


# ─────────────────────────────────────────────────────────────
# DATA LAYER  (SQLite in-memory, seeded from ODS or CSV)
# ─────────────────────────────────────────────────────────────
class SeedDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._create_table()
        self._load_data()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS seeds (
                FileNumber INTEGER PRIMARY KEY,
                Family TEXT,
                Variety TEXT,
                SeedSource TEXT,
                Comments TEXT,
                NumSeeds TEXT,
                Season TEXT,
                SeedSaverLevel TEXT,
                HybridDoNotSave TEXT,
                Edible TEXT,
                WhereGrown TEXT,
                PerennialAnnual TEXT,
                GrownBy TEXT,
                Year TEXT,
                SoilTemperature TEXT,
                Germination TEXT
            )
        """)
        self.conn.commit()

    def _load_data(self):
        """Load _SEED_LIBRARY_PARSED.xlsx using openpyxl."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        xlsx_path = None
        for d in [script_dir, os.path.dirname(script_dir), os.getcwd()]:
            candidate = os.path.join(d, "_SEED_LIBRARY_PARSED.xlsx")
            if os.path.exists(candidate):
                xlsx_path = candidate
                print(f"Found xlsx at: {xlsx_path}")
                break

        loaded = False

        # ── Primary: openpyxl ────────────────────────────────────────
        if xlsx_path:
            try:
                import openpyxl
                wb  = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
                ws  = wb.active
                all_rows = list(ws.iter_rows(values_only=True))
                wb.close()

                if not all_rows:
                    raise ValueError("Spreadsheet is empty.")

                headers = [str(h).strip() if h is not None else "" for h in all_rows[0]]
                print(f"Headers: {headers}")

                def ci(name):
                    try: return headers.index(name)
                    except ValueError: return -1

                COL = {
                    'FileNumber':        ci('FileNumber'),
                    'Family':            ci('Family'),
                    'Variety':           ci('Variety'),
                    'Seed Source':       ci('Seed Source'),
                    'Comments':          ci('Comments'),
                    '# of Seeds':        ci('# of Seeds'),
                    'Season':            ci('Season'),
                    'Seed Saver Level':  ci('Seed Saver Level'),
                    'Hybrid-Do Not Save':ci('Hybrid-Do Not Save'),
                    'Edible':            ci('Edible'),
                    'Where Grown':       ci('Where Grown'),
                    'Perennial/Annual':  ci('Perennial/Annual'),
                    'Grown By':          ci('Grown By'),
                    'Year':              ci('Year'),
                    'Soil Temperature':  ci('Soil Temperature'),
                    'Germination':       ci('Germination'),
                }

                def get(row_vals, key):
                    idx = COL.get(key, -1)
                    if idx < 0 or idx >= len(row_vals): return ''
                    v = row_vals[idx]
                    return str(v).strip() if v is not None else ''

                inserted = 0
                for row_vals in all_rows[1:]:
                    fn_raw = get(row_vals, 'FileNumber')
                    if not fn_raw or fn_raw == 'None': continue
                    try: fn = int(float(fn_raw))
                    except: continue
                    yr_raw = get(row_vals, 'Year')
                    try: yr = str(int(float(yr_raw))) if yr_raw and yr_raw != 'None' else ''
                    except: yr = yr_raw
                    self.conn.execute(
                        "INSERT OR REPLACE INTO seeds VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (fn,
                         get(row_vals,'Family'),          get(row_vals,'Variety'),
                         get(row_vals,'Seed Source'),     get(row_vals,'Comments'),
                         get(row_vals,'# of Seeds'),      get(row_vals,'Season'),
                         get(row_vals,'Seed Saver Level'),get(row_vals,'Hybrid-Do Not Save'),
                         get(row_vals,'Edible'),          get(row_vals,'Where Grown'),
                         get(row_vals,'Perennial/Annual'),get(row_vals,'Grown By'),
                         yr,
                         get(row_vals,'Soil Temperature'),get(row_vals,'Germination')))
                    inserted += 1
                self.conn.commit()
                loaded = True
                print(f"Loaded {inserted} seeds from xlsx.")
            except ImportError:
                print("ERROR: openpyxl not installed. Run: pip3 install openpyxl")
            except Exception as e:
                import traceback
                print("xlsx load ERROR:", e)
                traceback.print_exc()

        # ── Fallback: CSV backup ─────────────────────────────────────
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seeds_backup.csv")
        if not loaded and os.path.exists(csv_path):
            try:
                import csv
                with open(csv_path, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    inserted = 0
                    for row in reader:
                        try: fn = int(float(row.get('FileNumber', 0)))
                        except: continue
                        yr_raw = row.get('Year', '').strip()
                        try: yr = str(int(float(yr_raw))) if yr_raw else ''
                        except: yr = yr_raw
                        self.conn.execute(
                            "INSERT OR REPLACE INTO seeds VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (fn,
                             row.get('Family',''),          row.get('Variety',''),
                             row.get('Seed Source',''),     row.get('Comments',''),
                             row.get('# of Seeds',''),      row.get('Season',''),
                             row.get('Seed Saver Level',''),row.get('Hybrid-Do Not Save',''),
                             row.get('Edible',''),          row.get('Where Grown',''),
                             row.get('Perennial/Annual',''),row.get('Grown By',''),
                             yr,
                             row.get('Soil Temperature',''),row.get('Germination','')))
                        inserted += 1
                self.conn.commit()
                loaded = True
                print(f"Loaded {inserted} seeds from CSV backup.")
            except Exception as e:
                print(f"CSV load error: {e}")

        if not loaded:
            print("WARNING: No seed data file found. Starting with empty database.")


    def search(self, term=''):
        if not term:
            cur = self.conn.execute(
                "SELECT * FROM seeds ORDER BY FileNumber")
        else:
            t = f"%{term.lower()}%"
            cur = self.conn.execute("""
                SELECT * FROM seeds
                WHERE LOWER(CAST(FileNumber AS TEXT)) LIKE ?
                   OR LOWER(Family) LIKE ?
                   OR LOWER(Variety) LIKE ?
                ORDER BY FileNumber
            """, (t, t, t))
        return cur.fetchall()

    def add(self, data: dict):
        self.conn.execute("""
            INSERT INTO seeds VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            int(data['FileNumber']),
            data.get('Family',''), data.get('Variety',''),
            data.get('SeedSource',''), data.get('Comments',''),
            data.get('NumSeeds',''), data.get('Season',''),
            data.get('SeedSaverLevel',''), data.get('HybridDoNotSave',''),
            data.get('Edible',''), data.get('WhereGrown',''),
            data.get('PerennialAnnual',''), data.get('GrownBy',''),
            data.get('Year',''), data.get('SoilTemperature',''),
            data.get('Germination','')
        ))
        self.conn.commit()

    def delete(self, file_number: int):
        self.conn.execute("DELETE FROM seeds WHERE FileNumber=?", (file_number,))
        self.conn.commit()

    def exists(self, file_number: int) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM seeds WHERE FileNumber=?", (file_number,))
        return cur.fetchone() is not None

    def export_csv(self, path: str):
        import csv
        cur = self.conn.execute("SELECT * FROM seeds ORDER BY FileNumber")
        rows = cur.fetchall()
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'FileNumber','Family','Variety','Seed Source','Comments',
                '# of Seeds','Season','Seed Saver Level','Hybrid-Do Not Save',
                'Edible','Where Grown','Perennial/Annual','Grown By',
                'Year','Soil Temperature','Germination'
            ])
            for row in rows:
                writer.writerow(list(row))
        print(f"Exported {len(rows)} rows to {path}")


# ─────────────────────────────────────────────────────────────
# PDF GENERATION  (4 columns × 2 rows = 8 labels per page)
# ─────────────────────────────────────────────────────────────
def generate_labels_pdf(label_data: list, output_path: str) -> bool:
    """
    Avery 94207: 2 cols x 5 rows = 10 labels/sheet
    Layout per label:
      Row 1 (full width): Title bold 12pt centered
      Row 2: Left 2/3 = Family(red,10pt bold)+Variety(black,10pt)+Comments(9pt)
             Right 1/3 = Year, Edible, Season(italic), #Seeds, SeedSaver(bold), Germination
    """
    if not HAS_REPORTLAB:
        messagebox.showerror("Missing Library",
            "reportlab is required.\nInstall: pip3 install reportlab")
        return False

    labels = []
    for row, qty in label_data:
        for _ in range(qty):
            labels.append(row)
    if not labels:
        messagebox.showwarning("No Labels", "No labels selected.")
        return False

    # ── Dimensions ────────────────────────────────────────────────
    PAGE_W, PAGE_H   = letter
    MARGIN_TOP       = 0.50 * inch
    MARGIN_LEFT      = 0.16 * inch
    MARGIN_RIGHT     = 0.16 * inch
    LABEL_W          = (PAGE_W - MARGIN_LEFT - MARGIN_RIGHT) / 2
    LABEL_H          = 2.00  * inch
    COLS, ROWS       = 2, 5
    LABELS_PER_PAGE  = COLS * ROWS

    PAD_L, PAD_R, PAD_T, PAD_B = 6, 4, 4, 3
    TITLE_H          = 28      # pts for 2-line title
    DIVIDER_X_FRAC   = 2 / 3   # left cell = 2/3, right = 1/3

    BORDER_CLR       = colors.HexColor("#000000")
    DIVIDER_CLR      = colors.HexColor("#888888")

    # ── Styles ────────────────────────────────────────────────────
    title_sty = ParagraphStyle('ttl',
        fontSize=11, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#225522'), alignment=TA_CENTER,
        spaceAfter=0, leading=13)

    fam_sty = ParagraphStyle('fam',
        fontSize=10, fontName='Helvetica-Bold',
        textColor=colors.red, alignment=TA_LEFT,
        spaceAfter=1, leading=12)

    var_sty = ParagraphStyle('var',
        fontSize=10, fontName='Helvetica-Oblique',
        textColor=colors.black, alignment=TA_LEFT,
        spaceAfter=2, leading=12)

    comment_sty = ParagraphStyle('cmt',
        fontSize=9, fontName='Helvetica',
        textColor=colors.black, alignment=TA_LEFT,
        leading=11, spaceAfter=0)

    right_sty = ParagraphStyle('rgt',
        fontSize=9, fontName='Helvetica',
        textColor=colors.black, alignment=TA_CENTER,
        spaceAfter=1, leading=11)

    right_italic_sty = ParagraphStyle('rgti',
        fontSize=9, fontName='Helvetica-Oblique',
        textColor=colors.black, alignment=TA_CENTER,
        spaceAfter=1, leading=11)

    saver_sty = ParagraphStyle('svr',
        fontSize=7, fontName='Helvetica-Bold',
        textColor=colors.black, alignment=TA_CENTER,
        spaceAfter=1, leading=9, wordWrap='LTR')

    germ_sty = ParagraphStyle('grm',
        fontSize=8, fontName='Helvetica',
        textColor=colors.black, alignment=TA_CENTER,
        leading=10, spaceAfter=0)

    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus import Frame

    c = rl_canvas.Canvas(output_path, pagesize=letter)

    page_idx = 0
    while page_idx * LABELS_PER_PAGE < len(labels):
        page_labels = labels[page_idx * LABELS_PER_PAGE:
                             (page_idx + 1) * LABELS_PER_PAGE]

        for slot, row in enumerate(page_labels):
            col_num = slot % COLS
            row_num = slot // COLS

            lx = MARGIN_LEFT + col_num * LABEL_W
            ly = PAGE_H - MARGIN_TOP - (row_num + 1) * LABEL_H

            # Outer border
            c.setStrokeColor(BORDER_CLR)
            c.setLineWidth(0.75)
            c.rect(lx, ly, LABEL_W, LABEL_H, fill=0, stroke=1)

            # Extract fields
            family   = (row['Family']          or '').strip()
            variety  = (row['Variety']         or '').strip()
            season   = (row['Season']          or '').strip()
            numseeds = (row['NumSeeds']        or '').strip()
            edible   = (row['Edible']          or '').strip()
            perann   = (row['PerennialAnnual'] or '').strip()
            year_val = (row['Year']            or '').strip()
            comment  = ' '.join((row['Comments']       or '').split())
            saver    = (row['SeedSaverLevel']  or '').strip()
            germ     = (row['Germination']     or '').strip()
            soil_t   = (row['SoilTemperature'] or '').strip()

            # ── Title row (full width, top of label) ──────────────
            title_x = lx + PAD_L
            title_y = ly + LABEL_H - PAD_T - TITLE_H
            title_w = LABEL_W - PAD_L - PAD_R
            title_frame = Frame(title_x, title_y, title_w, TITLE_H,
                                leftPadding=0, rightPadding=0,
                                topPadding=0, bottomPadding=0,
                                showBoundary=0)
            title_frame.addFromList(
                [Paragraph("Cochise County Master Gardener Association<br/>Seed Library", title_sty)], c)

            # Horizontal divider under title
            div_y = ly + LABEL_H - PAD_T - TITLE_H - 1
            c.setStrokeColor(DIVIDER_CLR)
            c.setLineWidth(0.5)
            c.line(lx + 2, div_y, lx + LABEL_W - 2, div_y)

            # Body area below title
            body_y  = ly + PAD_B
            body_h  = LABEL_H - PAD_T - TITLE_H - 3 - PAD_B
            body_x  = lx + PAD_L
            body_w  = LABEL_W - PAD_L - PAD_R

            left_w  = body_w * DIVIDER_X_FRAC
            right_w = body_w * (1 - DIVIDER_X_FRAC)

            # Vertical divider between left and right cells
            vdiv_x = lx + PAD_L + left_w + 2
            c.setStrokeColor(DIVIDER_CLR)
            c.setLineWidth(0.5)
            c.line(vdiv_x, ly + PAD_B + 2, vdiv_x, div_y - 2)

            # ── LEFT cell — Family, Variety, Comments ─────────────
            left_items = [Paragraph(family, fam_sty)]
            if variety:
                left_items.append(Paragraph(variety, var_sty))
            if comment:
                left_items.append(Paragraph(comment, comment_sty))

            left_frame = Frame(body_x, body_y, left_w - 4, body_h,
                               leftPadding=0, rightPadding=0,
                               topPadding=0, bottomPadding=0,
                               showBoundary=0)
            left_frame.addFromList(left_items, c)

            # ── RIGHT cell — Year, Edible, Season, Seeds, Saver, Germ ──
            right_x = vdiv_x + 3
            right_items = []
            if year_val:
                right_items.append(Paragraph(year_val, right_sty))
            if edible:
                right_items.append(Paragraph(edible.upper(), right_sty))
            if season:
                right_items.append(Paragraph(season, right_italic_sty))
            if numseeds:
                right_items.append(Paragraph(f"{numseeds} Seeds", right_sty))
            if saver:
                right_items.append(Paragraph(saver, saver_sty))
            germ_text = germ
            if soil_t:
                germ_text += f"\n@ {soil_t}" if germ else soil_t
            if germ_text:
                right_items.append(Paragraph(f"Germ: {germ_text}", germ_sty))

            right_frame = Frame(right_x, body_y, right_w - 4, body_h,
                                leftPadding=0, rightPadding=0,
                                topPadding=0, bottomPadding=0,
                                showBoundary=0)
            right_frame.addFromList(right_items, c)

        c.showPage()
        page_idx += 1

    c.save()
    return True


# ─────────────────────────────────────────────────────────────
# GUI APPLICATION
# ─────────────────────────────────────────────────────────────
class SeedApp(tk.Tk):

    BG_GREEN  = "#1b5e20"
    BG_LIGHT  = "#f1f8e9"
    BG_WHITE  = "#ffffff"
    BTN_BLUE  = "#0076DB"
    BTN_HOVER = "#005aaa"

    def __init__(self):
        super().__init__()
        self.db = SeedDatabase()
        self.title("Cochise County Master Gardener Seed Database")
        self.resizable(True, True)
        self.configure(bg=self.BG_GREEN)
        # Set window icon
        try:
            import os
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     'seedapp_icon.png')
            if os.path.exists(icon_path):
                from PIL import Image, ImageTk
                ico = ImageTk.PhotoImage(Image.open(icon_path).resize((32,32)))
                self.wm_iconphoto(True, ico)
                self._icon_ref = ico  # keep reference
        except Exception:
            pass
        self._show_intro()

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _btn(self, parent, text, command, **kw):
        """Standard blue button."""
        cfg = dict(bg=self.BTN_BLUE, fg='white', relief='raised', bd=2,
                   font=('Helvetica', 10, 'bold'), padx=14, pady=6,
                   cursor='hand2', activebackground=self.BTN_HOVER,
                   activeforeground='white')
        cfg.update(kw)
        return tk.Button(parent, text=text, command=command, **cfg)

    def _nav_bar(self, exclude=None):
        """Pack a bottom nav bar. exclude = 'home'|'add'|'rem'|'lbl'|'browse'."""
        bar = tk.Frame(self, bg='#333333', pady=8, padx=10,
                       relief='raised', bd=3)
        bar.pack(fill='x', side='bottom')
        def nav_btn(text, cmd):
            # Use a tk.Label styled as a button for reliable text color on Mac
            lbl = tk.Label(bar, text=text,
                           bg=self.BTN_BLUE, fg='white',
                           font=('Helvetica', 11, 'bold'),
                           padx=16, pady=8, cursor='hand2',
                           relief='raised', bd=3)
            lbl.bind('<Button-1>', lambda e, c=cmd: c())
            lbl.bind('<Enter>',    lambda e: lbl.configure(bg='#003d80'))
            lbl.bind('<Leave>',    lambda e: lbl.configure(bg=self.BTN_BLUE))
            return lbl
        if exclude != 'home':
            nav_btn('Home',         self._show_intro ).pack(side='left', padx=6)
        if exclude != 'add':
            nav_btn('Add Seed',     self._show_add   ).pack(side='left', padx=6)
        if exclude != 'browse':
            nav_btn('Browse Seeds', self._show_browse).pack(side='left', padx=6)
        if exclude != 'rem':
            nav_btn('Remove Seeds', self._show_remove).pack(side='left', padx=6)
        if exclude != 'lbl':
            nav_btn('Print Labels', self._show_labels).pack(side='left', padx=6)

    # ── INTRO PAGE ─────────────────────────────────────────────
    def _show_intro(self):
        self._clear()
        self.geometry("460x420")
        self.configure(bg=self.BG_GREEN)

        frm = tk.Frame(self, bg=self.BG_GREEN)
        frm.pack(expand=True, fill='both', padx=50, pady=30)

        tk.Label(frm, text="Cochise County\nMaster Gardener",
                 font=('Helvetica', 22, 'bold'),
                 bg=self.BG_GREEN, fg='white').pack()
        tk.Label(frm, text="Seed Library Database",
                 font=('Helvetica', 14),
                 bg=self.BG_GREEN, fg='#c8e6c9').pack(pady=(4, 20))

        def home_btn(text, cmd):
            lbl = tk.Label(frm, text=text,
                           bg=self.BTN_BLUE, fg='white',
                           font=('Helvetica', 13, 'bold'),
                           padx=20, pady=10, cursor='hand2',
                           relief='raised', bd=3, width=22)
            lbl.bind('<Button-1>', lambda e, c=cmd: c())
            lbl.bind('<Enter>',    lambda e: lbl.configure(bg='#003d80'))
            lbl.bind('<Leave>',    lambda e: lbl.configure(bg=self.BTN_BLUE))
            return lbl
        home_btn('Add Seeds',         self._show_add   ).pack(pady=5, fill='x')
        home_btn('Browse Seeds',      self._show_browse).pack(pady=5, fill='x')
        home_btn('Remove Seeds',      self._show_remove).pack(pady=5, fill='x')
        home_btn('Print Seed Labels', self._show_labels).pack(pady=5, fill='x')

        cur = self.db.conn.execute("SELECT COUNT(*) FROM seeds")
        count = cur.fetchone()[0]
        tk.Label(frm, text=f"{count:,} seeds in library",
                 font=('Helvetica', 9), bg=self.BG_GREEN,
                 fg='#a5d6a7').pack(pady=(8, 0))
        def _about_btn():
            lbl = tk.Label(frm, text='About',
                           bg='#1b5e20', fg='#a5d6a7',
                           font=('Helvetica', 8, 'underline'),
                           cursor='hand2')
            lbl.bind('<Button-1>', lambda e: self._show_about())
            return lbl
        _about_btn().pack(pady=(4, 0))


    # ── BROWSE SEEDS PAGE ──────────────────────────────────────
    def _show_browse(self):
        self._clear()
        self.geometry("1000x620")
        self.configure(bg='#f5f5f5')

        hdr = tk.Frame(self, bg=self.BG_GREEN, pady=8)
        hdr.pack(fill='x', side='top')
        tk.Label(hdr, text="Browse Seeds",
                 font=('Helvetica', 16, 'bold'),
                 bg=self.BG_GREEN, fg='white').pack()

        # Nav bar before content
        self._nav_bar(exclude='browse')

        # Search/filter row
        ctrl = tk.Frame(self, bg='#f5f5f5', pady=6, padx=16)
        ctrl.pack(fill='x')
        tk.Label(ctrl, text="Search:", font=('Helvetica', 10),
                 bg='#f5f5f5', fg='black').pack(side='left')
        self._browse_search = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._browse_search,
                 font=('Helvetica', 10), width=40,
                 relief='solid', bd=1).pack(side='left', padx=6)
        def _br_btn(text, cmd):
            lbl = tk.Label(ctrl, text=text,
                           bg=self.BTN_BLUE, fg='white',
                           font=('Helvetica', 10, 'bold'),
                           padx=12, pady=4, cursor='hand2',
                           relief='raised', bd=3)
            lbl.bind('<Button-1>', lambda e, c=cmd: c())
            lbl.bind('<Enter>',    lambda e: lbl.configure(bg='#003d80'))
            lbl.bind('<Leave>',    lambda e: lbl.configure(bg=self.BTN_BLUE))
            return lbl
        _br_btn('Search',   self._do_browse_search       ).pack(side='left', padx=4)
        _br_btn('Show All', lambda: self._load_browse('')).pack(side='left', padx=4)
        # Edit mode toggle
        self._browse_edit_mode = tk.BooleanVar(value=False)
        edit_chk = tk.Checkbutton(ctrl,
            text='Edit Mode  (double-click row to edit)',
            variable=self._browse_edit_mode,
            bg='#f5f5f5', fg='#b71c1c',
            font=('Helvetica', 9, 'bold'),
            activebackground='#f5f5f5',
            selectcolor='#ffcccc')
        edit_chk.pack(side='left', padx=16)
        self._browse_count = tk.Label(ctrl, text="", font=('Helvetica', 9),
                                       bg='#f5f5f5', fg='#444')
        self._browse_count.pack(side='right', padx=10)

        # Main table
        cols = ('File#','Family','Variety','Count','Season','# Seeds',
                'Saver Level','Perennial/Annual','Grown By','Year','Source')
        tbl_frame = tk.Frame(self, bg='#f5f5f5')
        tbl_frame.pack(fill='both', expand=True, padx=16, pady=4)

        self._browse_tree = ttk.Treeview(tbl_frame, columns=cols,
                                          show='headings', height=22)
        col_widths = (55, 180, 170, 55, 80, 65, 130, 110, 100, 50, 120)
        for col, w in zip(cols, col_widths):
            self._browse_tree.heading(col, text=col,
                command=lambda c=col: self._browse_sort(c))
            self._browse_tree.column(col, width=w, stretch=False,
                anchor='center' if col in ('File#','Count','Season','# Seeds','Year') else 'w')

        vsb = ttk.Scrollbar(tbl_frame, orient='vertical',
                             command=self._browse_tree.yview)
        hsb = ttk.Scrollbar(tbl_frame, orient='horizontal',
                             command=self._browse_tree.xview)
        self._browse_tree.configure(yscrollcommand=vsb.set,
                                     xscrollcommand=hsb.set)
        self._browse_tree.grid(row=0, column=0, sticky='nsew')
        self._browse_tree.bind('<Double-ButtonRelease-1>', self._browse_edit)
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tbl_frame.grid_rowconfigure(0, weight=1)
        tbl_frame.grid_columnconfigure(0, weight=1)

        # Alternating row colors
        self._browse_tree.tag_configure('odd',  background='#ffffff')
        self._browse_tree.tag_configure('even', background='#e8f5e9')

        # Detail panel below
        detail_frame = tk.Frame(self, bg='#eeeeee', pady=6, padx=16,
                                 relief='sunken', bd=1)
        detail_frame.pack(fill='x', padx=16, pady=(0,4))
        tk.Label(detail_frame, text="Comments / Details:",
                 font=('Helvetica', 9, 'bold'),
                 bg='#eeeeee', fg='#333').pack(side='left')
        self._browse_detail = tk.Label(detail_frame, text="Click a row to see details",
                                        font=('Helvetica', 9),
                                        bg='#eeeeee', fg='#555',
                                        anchor='w', justify='left', wraplength=900)
        self._browse_detail.pack(side='left', padx=8, fill='x', expand=True)
        self._browse_tree.bind('<<TreeviewSelect>>', self._browse_show_detail)

        self._browse_sort_col = None
        self._browse_sort_rev = False
        self._browse_rows = []
        self._load_browse('')

    def _load_browse(self, term):
        self._browse_tree.delete(*self._browse_tree.get_children())
        rows = self.db.search(term)
        self._browse_rows = rows
        # Count how many seeds share each Family+Variety
        count_map = {}
        for r in rows:
            key = (r['Family'].strip().lower(), r['Variety'].strip().lower())
            count_map[key] = count_map.get(key, 0) + 1
        # Show only ONE row per unique Family+Variety combo
        seen = set()
        unique_rows = []
        for r in rows:
            key = (r['Family'].strip().lower(), r['Variety'].strip().lower())
            if key not in seen:
                seen.add(key)
                unique_rows.append((r, count_map[key]))
        for i, (r, cnt) in enumerate(unique_rows):
            tag = 'even' if i % 2 == 0 else 'odd'
            self._browse_tree.insert('', 'end', iid=str(r['FileNumber']),
                values=(r['FileNumber'], r['Family'], r['Variety'],
                        cnt,
                        r['Season'], r['NumSeeds'], r['SeedSaverLevel'],
                        r['PerennialAnnual'], r['GrownBy'], r['Year'],
                        r['SeedSource']),
                tags=(tag,))
        total_unique = len(unique_rows)
        total_seeds  = len(rows)
        self._browse_count.configure(
            text=f"{total_unique} unique varieties  ({total_seeds} total records)")

    def _do_browse_search(self):
        self._load_browse(self._browse_search.get())

    def _browse_show_detail(self, event):
        sel = self._browse_tree.selection()
        if not sel:
            return
        fn = int(sel[0])
        row = self.db.conn.execute(
            "SELECT * FROM seeds WHERE FileNumber=?", (fn,)).fetchone()
        if row:
            parts = []
            if row['Comments']:      parts.append(f"Comments: {row['Comments']}")
            if row['Germination']:   parts.append(f"Germination: {row['Germination']}")
            if row['SoilTemperature']: parts.append(f"Soil Temp: {row['SoilTemperature']}")
            if row['WhereGrown']:    parts.append(f"Where Grown: {row['WhereGrown']}")
            if row['Edible']:        parts.append(f"Edible: {row['Edible']}")
            if row['HybridDoNotSave']: parts.append(f"Hybrid: {row['HybridDoNotSave']}")
            self._browse_detail.configure(
                text="  |  ".join(parts) if parts else "No additional details")

    def _browse_sort(self, col):
        col_map = {
            'File#': 'FileNumber', 'Family': 'Family', 'Variety': 'Variety',
            'Season': 'Season', '# Seeds': 'NumSeeds', 'Saver Level': 'SeedSaverLevel',
            'Perennial/Annual': 'PerennialAnnual', 'Grown By': 'GrownBy',
            'Year': 'Year', 'Source': 'SeedSource', 'Count': 'FileNumber'
        }
        db_col = col_map.get(col, 'FileNumber')
        if self._browse_sort_col == col:
            self._browse_sort_rev = not self._browse_sort_rev
        else:
            self._browse_sort_col = col
            self._browse_sort_rev = False
        term = self._browse_search.get()
        order = "DESC" if self._browse_sort_rev else "ASC"
        rows = self.db.conn.execute(
            f'SELECT * FROM seeds WHERE LOWER(Family) LIKE ? OR LOWER(Variety) LIKE ? '
            f'OR CAST(FileNumber AS TEXT) LIKE ? ORDER BY "{db_col}" {order}',
            (f'%{term.lower()}%', f'%{term.lower()}%', f'%{term}%')).fetchall()
        self._browse_tree.delete(*self._browse_tree.get_children())
        sort_count_map = {}
        for r in rows:
            k = (r['Family'].strip().lower(), r['Variety'].strip().lower())
            sort_count_map[k] = sort_count_map.get(k, 0) + 1
        seen_sort = set()
        unique_sort = []
        for r in rows:
            k = (r['Family'].strip().lower(), r['Variety'].strip().lower())
            if k not in seen_sort:
                seen_sort.add(k)
                unique_sort.append((r, sort_count_map[k]))
        for i, (r, cnt) in enumerate(unique_sort):
            tag = 'even' if i % 2 == 0 else 'odd'
            self._browse_tree.insert('', 'end', iid=str(r['FileNumber']),
                values=(r['FileNumber'], r['Family'], r['Variety'],
                        cnt,
                        r['Season'], r['NumSeeds'], r['SeedSaverLevel'],
                        r['PerennialAnnual'], r['GrownBy'], r['Year'],
                        r['SeedSource']),
                tags=(tag,))

    # ── ADD SEEDS PAGE ─────────────────────────────────────────
    def _show_add(self):
        self._clear()
        self.geometry("680x660")
        self.configure(bg=self.BG_LIGHT)

        # Header
        hdr = tk.Frame(self, bg=self.BG_GREEN, pady=8)
        hdr.pack(fill='x', side='top')
        tk.Label(hdr, text="Add Seeds", font=('Helvetica', 16, 'bold'),
                 bg=self.BG_GREEN, fg='white').pack()

        # Nav bar BEFORE canvas so it always shows
        self._nav_bar(exclude='add')

        # Scrollable form
        scrollbar = ttk.Scrollbar(self, orient='vertical')
        canvas = tk.Canvas(self, bg=self.BG_LIGHT, highlightthickness=0,
                           yscrollcommand=scrollbar.set)
        scrollbar.configure(command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        inner = tk.Frame(canvas, bg=self.BG_LIGHT, padx=20, pady=10)
        win_id = canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

        fields = [
            ("File Number *",       "FileNumber",        False),
            ("Family",              "Family",            False),
            ("Variety",             "Variety",           False),
            ("Seed Source",         "SeedSource",        False),
            ("Comments",            "Comments",          True),
            ("# of Seeds",          "NumSeeds",          False),
            ("Season",              "Season",            False),
            ("Seed Saver Level",    "SeedSaverLevel",    False),
            ("Hybrid-Do Not Save",  "HybridDoNotSave",   False),
            ("Edible",              "Edible",            False),
            ("Where Grown",         "WhereGrown",        False),
            ("Perennial/Annual",    "PerennialAnnual",   False),
            ("Grown By",            "GrownBy",           False),
            ("Year",                "Year",              False),
            ("Soil Temperature",    "SoilTemperature",   False),
            ("Germination",         "Germination",       False),
        ]

        # Auto-compute next file number
        cur_max = self.db.conn.execute("SELECT MAX(FileNumber) FROM seeds").fetchone()[0]
        next_fn = (cur_max + 1) if cur_max else 1001

        self._add_entries = {}
        for label, key, multiline in fields:
            row_f = tk.Frame(inner, bg=self.BG_LIGHT)
            row_f.pack(fill='x', pady=3)
            tk.Label(row_f, text=label, font=('Helvetica', 9, 'bold'),
                     bg=self.BG_LIGHT, fg='#1b5e20',
                     width=20, anchor='w').pack(side='left')
            if multiline:
                txt = tk.Text(row_f, height=4, width=50,
                              font=('Helvetica', 9), relief='solid', bd=1)
                txt.pack(side='left', fill='x', expand=True)
                self._add_entries[key] = txt
            else:
                var = tk.StringVar()
                # Pre-fill File Number with next available number
                if key == 'FileNumber':
                    var.set(str(next_fn))
                tk.Entry(row_f, textvariable=var, font=('Helvetica', 9),
                         width=50, relief='solid', bd=1).pack(side='left', fill='x', expand=True)
                self._add_entries[key] = var

        btn_row = tk.Frame(inner, bg=self.BG_LIGHT, pady=10)
        btn_row.pack(fill='x')
        def _add_btn(text, cmd):
            lbl = tk.Label(btn_row, text=text,
                           bg=self.BTN_BLUE, fg='white',
                           font=('Helvetica', 11, 'bold'),
                           padx=16, pady=8, cursor='hand2',
                           relief='raised', bd=3)
            lbl.bind('<Button-1>', lambda e, c=cmd: c())
            lbl.bind('<Enter>',    lambda e: lbl.configure(bg='#003d80'))
            lbl.bind('<Leave>',    lambda e: lbl.configure(bg=self.BTN_BLUE))
            return lbl
        _add_btn('Save Seed', self._save_seed   ).pack(side='left', padx=6)
        _add_btn('Clear',     self._clear_add_form).pack(side='left', padx=6)

    def _get_add_val(self, key):
        w = self._add_entries[key]
        return w.get().strip() if isinstance(w, tk.StringVar) else w.get('1.0','end').strip()

    def _clear_add_form(self):
        for key, w in self._add_entries.items():
            if isinstance(w, tk.StringVar): w.set('')
            else: w.delete('1.0', 'end')

    def _save_seed(self):
        fn_str = self._get_add_val('FileNumber')
        if not fn_str:
            messagebox.showerror("Error", "File Number is required.")
            return
        try:    fn = int(fn_str)
        except: messagebox.showerror("Error", "File Number must be a whole number."); return
        if self.db.exists(fn):
            messagebox.showerror("Duplicate", f"File #{fn} already exists.")
            return
        data = {k: self._get_add_val(k) for k in self._add_entries}
        data['FileNumber'] = fn
        try:
            self.db.add(data)
            messagebox.showinfo("Saved", f"Seed #{fn} added successfully!")
            self._clear_add_form()
            # Update file number to next available
            cur_max = self.db.conn.execute("SELECT MAX(FileNumber) FROM seeds").fetchone()[0]
            next_fn2 = (cur_max + 1) if cur_max else 1001
            if 'FileNumber' in self._add_entries:
                self._add_entries['FileNumber'].set(str(next_fn2))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── REMOVE PAGE ────────────────────────────────────────────
    def _show_remove(self):
        self._clear()
        self.geometry("760x520")
        self.configure(bg='#fff8f8')

        hdr = tk.Frame(self, bg=self.BG_GREEN, pady=8)
        hdr.pack(fill='x', side='top')
        tk.Label(hdr, text="Remove Seeds", font=('Helvetica', 16, 'bold'),
                 bg=self.BG_GREEN, fg='white').pack()

        # Nav bar first
        self._nav_bar(exclude='rem')

        # Search bar
        ctrl = tk.Frame(self, bg='#fff8f8', pady=8, padx=16)
        ctrl.pack(fill='x')
        tk.Label(ctrl, text="Search:", font=('Helvetica', 10),
                 bg='#fff8f8', fg='black').pack(side='left')
        self._rem_search = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._rem_search,
                 font=('Helvetica', 10), width=40,
                 relief='solid', bd=1).pack(side='left', padx=6)
        def _rm_btn(text, cmd):
            lbl = tk.Label(ctrl, text=text,
                           bg=self.BTN_BLUE, fg='white',
                           font=('Helvetica', 10, 'bold'),
                           padx=12, pady=4, cursor='hand2',
                           relief='raised', bd=3)
            lbl.bind('<Button-1>', lambda e, c=cmd: c())
            lbl.bind('<Enter>',    lambda e: lbl.configure(bg='#003d80'))
            lbl.bind('<Leave>',    lambda e: lbl.configure(bg=self.BTN_BLUE))
            return lbl
        _rm_btn('Search',   self._do_remove_search            ).pack(side='left', padx=4)
        _rm_btn('Show All', lambda: self._load_remove_list('')).pack(side='left', padx=4)

        # Results table + confirm/delete on right
        mid = tk.Frame(self, bg='#fff8f8')
        mid.pack(fill='both', expand=True, padx=16, pady=4)

        cols = ('FileNumber','Family','Variety','Season','Year')
        self._rem_tree = ttk.Treeview(mid, columns=cols, show='headings', height=16,
                                       selectmode='extended')
        for col, w in zip(cols, (80, 250, 220, 100, 60)):
            self._rem_tree.heading(col, text=col)
            self._rem_tree.column(col, width=w, stretch=False)
        sb = ttk.Scrollbar(mid, orient='vertical', command=self._rem_tree.yview)
        self._rem_tree.configure(yscrollcommand=sb.set)
        self._rem_tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='left', fill='y')
        # Mac uses Command (Meta) for multi-select; also support Ctrl
        def _rem_ctrl_click(event):
            item = self._rem_tree.identify_row(event.y)
            if item:
                cur = list(self._rem_tree.selection())
                if item in cur:
                    cur.remove(item)
                else:
                    cur.append(item)
                self._rem_tree.selection_set(cur)
            return 'break'
        self._rem_tree.bind('<Control-Button-1>', _rem_ctrl_click)
        self._rem_tree.bind('<Meta-Button-1>',    _rem_ctrl_click)  # Mac Command key
        def _rem_shift_click(event):
            item = self._rem_tree.identify_row(event.y)
            if not item: return
            cur_sel = list(self._rem_tree.selection())
            all_items = self._rem_tree.get_children()
            if not cur_sel:
                self._rem_tree.selection_set([item])
                return 'break'
            anchor = cur_sel[0]
            idx_a = list(all_items).index(anchor)
            idx_b = list(all_items).index(item)
            lo, hi = min(idx_a, idx_b), max(idx_a, idx_b)
            self._rem_tree.selection_set(all_items[lo:hi+1])
            return 'break'
        self._rem_tree.bind('<Shift-Button-1>', _rem_shift_click)

        right = tk.Frame(mid, bg='#fff8f8', padx=12, pady=12)
        right.pack(side='left', fill='y')
        tk.Label(right,
                 text="Ctrl+Click or\nShift+Click for\nmultiple rows",
                 bg='#fff8f8', fg='#555',
                 font=('Helvetica', 8), justify='left').pack(anchor='w', pady=(0,8))
        self._rem_confirm = tk.BooleanVar()
        tk.Checkbutton(right,
                       text="Confirm removal\nof selected records",
                       variable=self._rem_confirm,
                       bg='#fff8f8', fg='#b71c1c',
                       font=('Helvetica', 9, 'bold'),
                       justify='left').pack(anchor='w', pady=(0,12))
        def _del_btn(text, cmd):
            lbl = tk.Label(right, text=text,
                           bg=self.BTN_BLUE, fg='white',
                           font=('Helvetica', 11, 'bold'),
                           padx=16, pady=8, cursor='hand2',
                           relief='raised', bd=3)
            lbl.bind('<Button-1>', lambda e, c=cmd: c())
            lbl.bind('<Enter>',    lambda e: lbl.configure(bg='#003d80'))
            lbl.bind('<Leave>',    lambda e: lbl.configure(bg=self.BTN_BLUE))
            return lbl
        _del_btn('Delete Selected', self._delete_seed).pack(fill='x')

        self._load_remove_list('')

    def _do_remove_search(self):
        self._load_remove_list(self._rem_search.get())

    def _load_remove_list(self, term):
        self._rem_tree.delete(*self._rem_tree.get_children())
        for r in self.db.search(term):
            self._rem_tree.insert('', 'end', iid=str(r['FileNumber']),
                                  values=(r['FileNumber'], r['Family'],
                                          r['Variety'], r['Season'], r['Year']))

    def _delete_seed(self):
        if not self._rem_confirm.get():
            messagebox.showwarning("Confirm", "Check the confirmation checkbox first.")
            return
        sel = self._rem_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select one or more rows first.")
            return
        n = len(sel)
        msg = (f"Permanently delete {n} seed records?" if n > 1
               else f"Permanently delete seed #{sel[0]}?")
        if messagebox.askyesno("Delete?", msg):
            for iid in sel:
                self.db.delete(int(iid))
            self.db.conn.commit()
            self._rem_confirm.set(False)
            self._load_remove_list(self._rem_search.get())
            messagebox.showinfo("Deleted", f"{n} seed record(s) removed.")

    # ── PRINT LABELS PAGE ──────────────────────────────────────
    def _show_labels(self):
        self._clear()
        self.geometry("860x640")
        self.configure(bg='#f0f4ff')

        hdr = tk.Frame(self, bg=self.BG_GREEN, pady=8)
        hdr.pack(fill='x', side='top')
        tk.Label(hdr, text="Print Seed Labels",
                 font=('Helvetica', 16, 'bold'),
                 bg=self.BG_GREEN, fg='white').pack()
        tk.Label(hdr, text='Avery 94207  -  2" x 4"  -  10 labels per sheet',
                 font=('Helvetica', 9), bg=self.BG_GREEN, fg='#c8e6c9').pack()

        # Nav bar first
        self._nav_bar(exclude='lbl')

        # Instructions
        info = tk.Frame(self, bg='#e3f2fd', pady=6, padx=16, relief='flat')
        info.pack(fill='x')
        tk.Label(info,
                 text="HOW TO USE:  1) Search/filter seeds below.  "
                      "2) Set the qty for each seed you want to print.  "
                      "3) Click Preview / Save PDF.",
                 font=('Helvetica', 9, 'bold'), bg='#e3f2fd', fg='#0d47a1').pack(side='left')

        # Filter row
        ctrl = tk.Frame(self, bg='#f0f4ff', pady=6, padx=16)
        ctrl.pack(fill='x')
        tk.Label(ctrl, text="Search:", font=('Helvetica', 9, 'bold'),
                 bg='#f0f4ff', fg='black').pack(side='left')
        self._lbl_filter = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._lbl_filter, font=('Helvetica', 9),
                 width=35, relief='solid', bd=1).pack(side='left', padx=6)
        def _ctrl_btn(text, cmd):
            lbl = tk.Label(ctrl, text=text,
                           bg=self.BTN_BLUE, fg='white',
                           font=('Helvetica', 10, 'bold'),
                           padx=12, pady=4, cursor='hand2',
                           relief='raised', bd=3)
            lbl.bind('<Button-1>', lambda e, c=cmd: c())
            lbl.bind('<Enter>',    lambda e: lbl.configure(bg='#003d80'))
            lbl.bind('<Leave>',    lambda e: lbl.configure(bg=self.BTN_BLUE))
            return lbl
        _ctrl_btn('Search',   self._filter_labels             ).pack(side='left', padx=4)
        _ctrl_btn('Load All', lambda: self._load_label_list('')).pack(side='left', padx=4)

        self._lbl_count_lbl = tk.Label(ctrl, text="",
                                        font=('Helvetica', 9, 'bold'),
                                        bg='#f0f4ff', fg=self.BTN_BLUE)
        self._lbl_count_lbl.pack(side='right', padx=10)

        # Column headers (manual, above the frame+canvas)
        hdr_row = tk.Frame(self, bg='#0076DB', pady=4, padx=16)
        hdr_row.pack(fill='x', padx=16)
        tk.Label(hdr_row, text="File #",   width=7,  bg='#0076DB', fg='white', font=('Helvetica',9,'bold'), anchor='center').pack(side='left')
        tk.Label(hdr_row, text="Family",   width=22, bg='#0076DB', fg='white', font=('Helvetica',9,'bold'), anchor='w').pack(side='left', padx=(4,0))
        tk.Label(hdr_row, text="Variety",  width=22, bg='#0076DB', fg='white', font=('Helvetica',9,'bold'), anchor='w').pack(side='left', padx=(4,0))
        tk.Label(hdr_row, text="Season",   width=10, bg='#0076DB', fg='white', font=('Helvetica',9,'bold'), anchor='center').pack(side='left', padx=(4,0))
        tk.Label(hdr_row, text="# Labels to Print",
                 width=16, bg='#0076DB', fg='white', font=('Helvetica',9,'bold'), anchor='center').pack(side='left', padx=(4,0))

        # Scrollable seed list with spinbox per row
        container = tk.Frame(self, bg='#f0f4ff')
        container.pack(fill='both', expand=True, padx=16, pady=(0,4))

        canvas = tk.Canvas(container, bg='#f0f4ff', highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        self._lbl_inner = tk.Frame(canvas, bg='#f0f4ff')
        self._lbl_win = canvas.create_window((0,0), window=self._lbl_inner, anchor='nw')
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(self._lbl_win, width=e.width))
        self._lbl_inner.bind('<Configure>',
                              lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        # Mouse wheel scroll
        canvas.bind_all('<MouseWheel>', lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))

        # Storage: {FileNumber_str: IntVar for qty}
        self._lbl_qty_vars = {}   # fn_str -> tk.IntVar (0 = not selected)
        self._lbl_rows_data = []  # list of row dicts

        btn_row = tk.Frame(self, bg='#333333', pady=8, padx=10,
                           relief='raised', bd=3)
        btn_row.pack(fill='x')
        def _lbl_btn(text, cmd):
            lbl = tk.Label(btn_row, text=text,
                           bg=self.BTN_BLUE, fg='white',
                           font=('Helvetica', 11, 'bold'),
                           padx=16, pady=8, cursor='hand2',
                           relief='raised', bd=3)
            lbl.bind('<Button-1>', lambda e, c=cmd: c())
            lbl.bind('<Enter>',    lambda e: lbl.configure(bg='#003d80'))
            lbl.bind('<Leave>',    lambda e: lbl.configure(bg=self.BTN_BLUE))
            return lbl
        _lbl_btn('Preview / Save PDF', self._generate_pdf).pack(side='left', padx=6)
        _lbl_btn('Set All to 1',       self._set_all_one  ).pack(side='left', padx=6)
        _lbl_btn('Clear All',          self._clear_all_qty).pack(side='left', padx=6)

        self._lbl_canvas = canvas
        self._load_label_list('')

    def _load_label_list(self, term):
        # Clear inner frame
        for w in self._lbl_inner.winfo_children():
            w.destroy()
        self._lbl_qty_vars.clear()
        self._lbl_rows_data.clear()

        rows = self.db.search(term)
        self._lbl_rows_data = list(rows)

        for i, r in enumerate(rows):
            fn_str = str(r['FileNumber'])
            qty_var = tk.IntVar(value=0)
            self._lbl_qty_vars[fn_str] = qty_var

            bg = '#ffffff' if i % 2 == 0 else '#e8f5e9'
            row_frame = tk.Frame(self._lbl_inner, bg=bg, pady=3, padx=4)
            row_frame.pack(fill='x')

            tk.Label(row_frame, text=str(r['FileNumber']),
                     width=7, bg=bg, fg='black',
                     font=('Helvetica', 9), anchor='center').pack(side='left')
            tk.Label(row_frame, text=r['Family'][:24],
                     width=22, bg=bg, fg='black',
                     font=('Helvetica', 9), anchor='w').pack(side='left', padx=(4,0))
            tk.Label(row_frame, text=r['Variety'][:24],
                     width=22, bg=bg, fg='black',
                     font=('Helvetica', 9), anchor='w').pack(side='left', padx=(4,0))
            tk.Label(row_frame, text=r['Season'][:12],
                     width=10, bg=bg, fg='black',
                     font=('Helvetica', 9), anchor='center').pack(side='left', padx=(4,0))

            # Spinbox: 0 = don't print, 1-99 = number of labels
            sp = tk.Spinbox(row_frame, from_=0, to=99,
                            textvariable=qty_var,
                            font=('Helvetica', 10, 'bold'),
                            width=5, justify='center',
                            relief='solid', bd=1,
                            bg='#fff9c4',   # yellow tint so it stands out
                            fg='black')
            sp.pack(side='left', padx=(8,0))
            tk.Label(row_frame, text="(0 = skip)",
                     bg=bg, fg='#888', font=('Helvetica', 7)).pack(side='left', padx=2)

            # Live total update
            qty_var.trace_add('write', lambda *a: self._update_label_count())

        self._update_label_count()

    def _filter_labels(self):
        self._load_label_list(self._lbl_filter.get())

    def _update_label_count(self):
        selected = [(fn, v.get()) for fn, v in self._lbl_qty_vars.items() if v.get() > 0]
        total = sum(q for _, q in selected)
        self._lbl_count_lbl.configure(
            text=f"{len(selected)} seeds selected  -  {total} total labels to print")

    def _set_all_one(self):
        for v in self._lbl_qty_vars.values():
            v.set(1)

    def _clear_all_qty(self):
        for v in self._lbl_qty_vars.values():
            v.set(0)

    def _generate_pdf(self):
        label_data = []
        for r in self._lbl_rows_data:
            fn_str = str(r['FileNumber'])
            qty = self._lbl_qty_vars.get(fn_str, tk.IntVar()).get()
            if qty > 0:
                label_data.append((r, qty))

        if not label_data:
            messagebox.showwarning("Nothing Selected",
                "Set the quantity (# Labels) to 1 or more for the seeds you want to print.")
            return

        total = sum(q for _, q in label_data)
        if not messagebox.askyesno("Confirm Print",
                f"Print {total} label(s) for {len(label_data)} seed(s)?"):
            return

        if not HAS_REPORTLAB:
            messagebox.showerror("ReportLab Not Found",
                "ReportLab is needed for PDF generation.\n\n"
                "Install it by running this in Terminal:\n\n"
                "    pip3 install reportlab\n\n"
                "Then restart the application.")
            return

        out_path = filedialog.asksaveasfilename(
            defaultextension='.pdf',
            filetypes=[('PDF Files', '*.pdf')],
            initialfile='seed_labels.pdf',
            title='Save Seed Labels PDF')
        if not out_path:
            return

        try:
            ok = generate_labels_pdf(label_data, out_path)
            if ok:
                messagebox.showinfo("PDF Saved",
                    f"Saved {total} label(s) to:\n{out_path}\n\nOpening PDF viewer...")
                import subprocess, platform
                try:
                    if platform.system() == 'Darwin':
                        subprocess.Popen(['open', out_path])
                    elif platform.system() == 'Windows':
                        os.startfile(out_path)
                    else:
                        subprocess.Popen(['xdg-open', out_path])
                except Exception:
                    pass
        except Exception as e:
            messagebox.showerror("PDF Error", str(e))


    def _browse_edit(self, event=None):
        """Open an edit dialog for the selected browse row."""
        if not getattr(self, '_browse_edit_mode', None) or not self._browse_edit_mode.get():
            return  # Edit mode not enabled
        sel = self._browse_tree.selection()
        if not sel:
            return
        fn = int(sel[0])
        row = self.db.conn.execute(
            "SELECT * FROM seeds WHERE FileNumber=?", (fn,)).fetchone()
        if not row:
            return

        top = tk.Toplevel(self)
        top.title(f"Edit Seed #{fn}")
        top.geometry("600x580")
        top.grab_set()
        top.configure(bg=self.BG_LIGHT)

        tk.Label(top, text=f"Edit Seed #{fn}",
                 font=('Helvetica', 14, 'bold'),
                 bg=self.BG_GREEN, fg='white').pack(fill='x', pady=0)

        # Scrollable form
        scrollbar = ttk.Scrollbar(top, orient='vertical')
        canvas = tk.Canvas(top, bg=self.BG_LIGHT, highlightthickness=0,
                           yscrollcommand=scrollbar.set)
        scrollbar.configure(command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        inner = tk.Frame(canvas, bg=self.BG_LIGHT, padx=16, pady=10)
        win_id = canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))
        inner.bind('<Configure>', lambda e: canvas.configure(
            scrollregion=canvas.bbox('all')))

        fields = [
            ("Family",             "Family",           False),
            ("Variety",            "Variety",          False),
            ("Seed Source",        "SeedSource",       False),
            ("Comments",           "Comments",         True),
            ("# of Seeds",         "NumSeeds",         False),
            ("Season",             "Season",           False),
            ("Seed Saver Level",   "SeedSaverLevel",   False),
            ("Hybrid-Do Not Save", "HybridDoNotSave",  False),
            ("Edible",             "Edible",           False),
            ("Where Grown",        "WhereGrown",       False),
            ("Perennial/Annual",   "PerennialAnnual",  False),
            ("Grown By",           "GrownBy",          False),
            ("Year",               "Year",             False),
            ("Soil Temperature",   "SoilTemperature",  False),
            ("Germination",        "Germination",      False),
        ]

        col_map = {
            "Family": row["Family"], "Variety": row["Variety"],
            "SeedSource": row["SeedSource"], "Comments": row["Comments"],
            "NumSeeds": row["NumSeeds"], "Season": row["Season"],
            "SeedSaverLevel": row["SeedSaverLevel"],
            "HybridDoNotSave": row["HybridDoNotSave"],
            "Edible": row["Edible"], "WhereGrown": row["WhereGrown"],
            "PerennialAnnual": row["PerennialAnnual"],
            "GrownBy": row["GrownBy"], "Year": row["Year"],
            "SoilTemperature": row["SoilTemperature"],
            "Germination": row["Germination"],
        }

        edit_entries = {}
        for label, key, multiline in fields:
            row_f = tk.Frame(inner, bg=self.BG_LIGHT)
            row_f.pack(fill='x', pady=3)
            tk.Label(row_f, text=label, font=('Helvetica', 9, 'bold'),
                     bg=self.BG_LIGHT, fg='#1b5e20',
                     width=20, anchor='w').pack(side='left')
            val = col_map.get(key, '') or ''
            if multiline:
                txt = tk.Text(row_f, height=3, width=45,
                              font=('Helvetica', 9), relief='solid', bd=1)
                txt.insert('1.0', val)
                txt.pack(side='left', fill='x', expand=True)
                edit_entries[key] = txt
            else:
                var = tk.StringVar(value=val)
                tk.Entry(row_f, textvariable=var, font=('Helvetica', 9),
                         width=45, relief='solid', bd=1).pack(
                         side='left', fill='x', expand=True)
                edit_entries[key] = var

        def save_edits():
            updates = {}
            for key, widget in edit_entries.items():
                if isinstance(widget, tk.StringVar):
                    updates[key] = widget.get().strip()
                else:
                    updates[key] = widget.get('1.0', 'end').strip()
            try:
                self.db.conn.execute("""
                    UPDATE seeds SET
                        Family=?, Variety=?, SeedSource=?, Comments=?,
                        NumSeeds=?, Season=?, SeedSaverLevel=?, HybridDoNotSave=?,
                        Edible=?, WhereGrown=?, PerennialAnnual=?, GrownBy=?,
                        Year=?, SoilTemperature=?, Germination=?
                    WHERE FileNumber=?
                """, (
                    updates["Family"], updates["Variety"],
                    updates["SeedSource"], updates["Comments"],
                    updates["NumSeeds"], updates["Season"],
                    updates["SeedSaverLevel"], updates["HybridDoNotSave"],
                    updates["Edible"], updates["WhereGrown"],
                    updates["PerennialAnnual"], updates["GrownBy"],
                    updates["Year"], updates["SoilTemperature"],
                    updates["Germination"], fn
                ))
                self.db.conn.commit()
                messagebox.showinfo("Saved", f"Seed #{fn} updated.")
                top.destroy()
                self._load_browse(self._browse_search.get()
                                  if hasattr(self, '_browse_search') else '')
            except Exception as e:
                messagebox.showerror("Error", str(e))

        btn_row = tk.Frame(inner, bg=self.BG_LIGHT, pady=10)
        btn_row.pack(fill='x')
        def _eb(text, cmd):
            lbl = tk.Label(btn_row, text=text,
                           bg=self.BTN_BLUE, fg='white',
                           font=('Helvetica', 10, 'bold'),
                           padx=14, pady=6, cursor='hand2',
                           relief='raised', bd=3)
            lbl.bind('<Button-1>', lambda e, c=cmd: c())
            lbl.bind('<Enter>',    lambda e: lbl.configure(bg='#003d80'))
            lbl.bind('<Leave>',    lambda e: lbl.configure(bg=self.BTN_BLUE))
            return lbl
        _eb('Save Changes', save_edits      ).pack(side='left', padx=6)
        _eb('Cancel',       top.destroy     ).pack(side='left', padx=6)


    def _show_about(self):
        top = tk.Toplevel(self)
        top.title("About")
        top.resizable(False, False)
        top.configure(bg=self.BG_GREEN)
        top.grab_set()

        # Try to show icon in About window
        try:
            import os
            from PIL import Image, ImageTk
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     'seedapp_icon.png')
            if os.path.exists(icon_path):
                rose_img = ImageTk.PhotoImage(Image.open(icon_path).resize((120, 120),
                                              Image.LANCZOS))
                lbl_img = tk.Label(top, image=rose_img, bg=self.BG_GREEN)
                lbl_img.image = rose_img
                lbl_img.pack(pady=(20, 8))
        except Exception:
            tk.Label(top, text="🌹", font=('Helvetica', 48),
                     bg=self.BG_GREEN, fg='white').pack(pady=(20, 8))

        tk.Label(top, text="Cochise County Master Gardeners",
                 font=('Helvetica', 16, 'bold'),
                 bg=self.BG_GREEN, fg='white').pack()
        tk.Label(top, text="Seed Library Database",
                 font=('Helvetica', 12),
                 bg=self.BG_GREEN, fg='#c8e6c9').pack(pady=(2, 16))

        # Divider
        tk.Frame(top, bg='#4caf50', height=1).pack(fill='x', padx=30)

        info_frame = tk.Frame(top, bg=self.BG_GREEN, padx=30, pady=16)
        info_frame.pack(fill='x')

        credits = [
            ("Version",    "1.0"),
            ("Built for",  "Cochise County Master Gardener Association"),
            ("Purpose",    "Seed library management & label printing"),
            ("Designed by","Claude AI (Anthropic)  +  Alan Borhauer"),
            ("Platform",   "Python 3  /  tkinter  /  ReportLab"),
            ("Labels",     "Avery 94207  (2\u201d x 4\u201d, 10 per sheet)"),
        ]
        for label, value in credits:
            row = tk.Frame(info_frame, bg=self.BG_GREEN)
            row.pack(fill='x', pady=3)
            tk.Label(row, text=f"{label}:",
                     font=('Helvetica', 9, 'bold'),
                     bg=self.BG_GREEN, fg='#a5d6a7',
                     width=14, anchor='e').pack(side='left')
            tk.Label(row, text=value,
                     font=('Helvetica', 9),
                     bg=self.BG_GREEN, fg='white',
                     anchor='w').pack(side='left', padx=(8, 0))

        tk.Frame(top, bg='#4caf50', height=1).pack(fill='x', padx=30)

        def close_btn():
            lbl = tk.Label(top, text="Close",
                           bg=self.BTN_BLUE, fg='white',
                           font=('Helvetica', 10, 'bold'),
                           padx=20, pady=8, cursor='hand2',
                           relief='raised', bd=3)
            lbl.bind('<Button-1>', lambda e: top.destroy())
            lbl.bind('<Enter>',    lambda e: lbl.configure(bg='#003d80'))
            lbl.bind('<Leave>',    lambda e: lbl.configure(bg=self.BTN_BLUE))
            return lbl
        close_btn().pack(pady=16)


if __name__ == '__main__':
    app = SeedApp()
    app.mainloop()
