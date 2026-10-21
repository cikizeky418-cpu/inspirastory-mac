# -*- coding: utf-8 -*-
"""InspiraStory — aplikasi manajemen studio wedding & foto (macOS, online+offline).

Python 3 + tkinter + sqlite3 (stdlib saja). Siap di-build dengan PyInstaller
(windowed, .app bundle macOS).
"""

import hashlib
import json
import os
import shutil
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, date

import db as dbmod
import sync as syncmod

# ---------------------------------------------------------------- brand
APP_NAME = 'InspiraStory'
APP_TAGLINE = 'Wedding & Photography Studio'
BUNDLE_ID = 'com.inspirastory.app'

# Font sesuai platform (macOS tidak punya Segoe UI / Consolas)
_IS_MAC = sys.platform == 'darwin'
FONT_UI = 'Helvetica Neue' if _IS_MAC else 'Segoe UI'
FONT_SERIF = 'Didot' if _IS_MAC else 'Times New Roman'
FONT_MONO = 'Menlo' if _IS_MAC else 'Consolas'

# Hash password admin default. Password awal dikomunikasikan TERPISAH ke
# pemilik brand dan TIDAK disimpan di repo — segera ganti di menu Pengaturan.
_DEFAULT_ADMIN_HASH = 'c89f7d296004cb28f306ca222feeafef0b0186e3847dbd5a128b78bfa0d41e24'


# ---------------------------------------------------------------- paths
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))


def resource_path(name):
    """Path aman untuk file bawaan (mendukung PyInstaller onefile)."""
    base = getattr(sys, '_MEIPASS', APP_DIR)
    return os.path.join(base, name)


_DATA_DIR = os.path.join(os.path.expanduser('~'), 'Library',
                         'Application Support', 'InspiraStory') if _IS_MAC else APP_DIR
os.makedirs(_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(_DATA_DIR, 'inspirastory.db')
CFG_PATH = os.path.join(APP_DIR, 'firebase_config.json')

# ---------------------------------------------------------------- konstanta
LAYANAN = [
    ('pas-biru', 'Pas Foto Latar Biru'),
    ('pas-merah', 'Pas Foto Latar Merah'),
    ('cetak-foto', 'Cetak Foto'),
    ('undangan-digital', 'Undangan Digital'),
    ('undangan-fisik', 'Undangan Fisik'),
    ('prewedding', 'Prewedding'),
    ('wedding', 'Wedding'),
    ('foto-only', 'Foto Only'),
    ('video-only', 'Video Only'),
    ('ultah', 'Ulang Tahun'),
    ('keluarga', 'Foto Keluarga'),
    ('grup', 'Foto Grup'),
    ('lainnya', 'Lainnya'),
]
LAYANAN_LABEL = dict(LAYANAN)

UKURAN_CETAK = ['8R', '8RP', '12R', '12RP', '16R', '16RP', '20R', '20RP', '24R', '24RP']
UKURAN_HARGA = {'8R': 15000, '8RP': 18000, '12R': 35000, '12RP': 40000,
                '16R': 75000, '16RP': 85000, '20R': 125000, '20RP': 140000,
                '24R': 200000, '24RP': 225000}

EXP_CATS = [
    ('konten-kreator', 'Bayar Konten Kreator'), ('host-live', 'Bayar Host Live'),
    ('fotografer', 'Bayar Fotografer'), ('editor', 'Bayar Editor'),
    ('sewa-alat', 'Sewa Alat'), ('service-alat', 'Service Alat'),
    ('cetak', 'Bayar Cetakan'), ('utang', 'Bayar Utang'), ('cashout', 'Cashout'),
    ('adobe', 'Bayar Adobe'), ('google-drive', 'Google Drive'),
    ('makan', 'Bayar Makan'), ('makan-minum', 'Makan & Minuman'),
    ('stok-studio', 'Stok Kebutuhan Studio'), ('listrik', 'Bayar Listrik'),
    ('wifi', 'Bayar Wifi'), ('maintenance', 'Maintenance'),
    ('lainnya', 'Lainnya'),
]
EXP_LABEL = dict(EXP_CATS)

JENIS_JADWAL = [('foto', 'Foto'), ('video', 'Video'), ('foto-video', 'Foto + Video')]
TEMPAT_JADWAL = [('studio', 'Di Studio'), ('luar', 'Di Luar')]
STATUS_JADWAL = ['terjadwal', 'selesai', 'batal']
STATUS_DEADLINE = ['antri', 'proses', 'selesai']
STATUS_CETAK = ['diproses', 'selesai', 'diambil']

BG = '#0d0d0d'
BG2 = '#161616'
BG3 = '#202020'
BORDER = '#2e2a1e'
FG = '#f7f4ec'
GOLD = '#c8a24a'
GOLD2 = '#e6c876'
MUTED = '#a29b88'
GREEN = '#5fd97a'
RED = '#f06666'


# ---------------------------------------------------------------- util
def rp(n):
    try:
        return 'Rp' + format(int(round(float(n or 0))), ',').replace(',', '.')
    except Exception:
        return 'Rp0'


def hash_pass(pw):
    return hashlib.sha256(('ins::' + pw).encode('utf-8')).hexdigest()


def today_iso():
    return date.today().isoformat()


def month_iso():
    return date.today().strftime('%Y-%m')


def fmt_tgl(s):
    try:
        d = datetime.strptime(s[:10], '%Y-%m-%d')
        return d.strftime('%d/%m/%Y')
    except Exception:
        return s or '-'


NAMA_BULAN = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
              'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']


def nama_bulan(mk):
    try:
        y, m = mk.split('-')
        return NAMA_BULAN[int(m) - 1] + ' ' + y
    except Exception:
        return mk


# ---------------------------------------------------------------- aplikasi
class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry('1120x700')
        self.root.minsize(1000, 620)
        self.root.configure(bg=BG)
        self.dbs = dbmod.DB(DB_PATH)
        self.cfg = self._load_cfg()
        self.user = None
        self.online = None
        self._style()
        self._build_login()

    def _load_cfg(self):
        for p in (CFG_PATH, resource_path('firebase_config.json')):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                continue
        return {}

    # ------------------------------ tema ------------------------------
    def _style(self):
        s = ttk.Style()
        try:
            s.theme_use('clam')
        except Exception:
            pass
        s.configure('.', background=BG, foreground=FG, fieldbackground=BG2,
                    font=(FONT_UI, 10))
        s.configure('TFrame', background=BG)
        s.configure('Card.TFrame', background='#1b1b1b', relief='solid',
                    borderwidth=1, bordercolor=BORDER)
        s.configure('TLabel', background=BG, foreground=FG, font=(FONT_UI, 10))
        s.configure('Card.TLabel', background='#1b1b1b', foreground=FG)
        s.configure('Muted.TLabel', background=BG, foreground=MUTED, font=(FONT_UI, 9))
        s.configure('CardMuted.TLabel', background='#1b1b1b', foreground=MUTED,
                    font=(FONT_UI, 9))
        s.configure('Title.TLabel', background=BG, foreground=GOLD2,
                    font=(FONT_UI, 16, 'bold'))
        s.configure('CardTitle.TLabel', background='#1b1b1b', foreground=GOLD2,
                    font=(FONT_UI, 13, 'bold'))
        s.configure('Big.TLabel', background='#1b1b1b', foreground=FG,
                    font=(FONT_UI, 24, 'bold'))
        s.configure('TButton', background=BG3, foreground=FG, font=(FONT_UI, 10),
                    padding=8, borderwidth=0)
        s.map('TButton', background=[('active', '#333333')], foreground=[('active', GOLD2)])
        s.configure('Gold.TButton', background=GOLD, foreground='#141414',
                    font=(FONT_UI, 10, 'bold'), padding=8)
        s.map('Gold.TButton', background=[('active', GOLD2)])
        s.configure('Danger.TButton', background='#5a1f1f', foreground='#ffb3b3')
        s.configure('TEntry', fieldbackground=BG3, foreground=FG, borderwidth=1,
                    insertcolor=FG, padding=6)
        s.configure('TCombobox', fieldbackground=BG3, foreground=FG, padding=6,
                    arrowcolor=GOLD)
        s.configure('Treeview', background=BG2, fieldbackground=BG2, foreground=FG,
                    rowheight=26, borderwidth=0, font=(FONT_UI, 10))
        s.configure('Treeview.Heading', background=BG3, foreground=GOLD2,
                    font=(FONT_UI, 10, 'bold'))
        s.map('Treeview', background=[('selected', '#3a3220')],
              foreground=[('selected', GOLD2)])
        s.configure('TNotebook', background=BG, borderwidth=0)
        s.configure('TNotebook.Tab', background=BG3, foreground=MUTED,
                    font=(FONT_UI, 10, 'bold'), padding=(12, 8))
        s.map('TNotebook.Tab', background=[('selected', '#2a2417')],
              foreground=[('selected', GOLD2)])
        s.configure('TProgressbar', background=GOLD, troughcolor=BG3, borderwidth=0)
        s.configure('TCheckbutton', background=BG, foreground=FG)
        self.root.option_add('*TCombobox*Listbox.background', BG3)
        self.root.option_add('*TCombobox*Listbox.foreground', FG)
        self.root.option_add('*TCombobox*Listbox.selectBackground', '#3a3220')

    # ------------------------------ login ------------------------------
    def _build_login(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=BG)
        f = ttk.Frame(self.root, style='Card.TFrame', padding=40)
        f.place(relx=0.5, rely=0.5, anchor='center')
        ttk.Label(f, text='\u2014 INSPIRASTORY \u2014', style='CardTitle.TLabel',
                  font=(FONT_SERIF, 26)).pack()
        ttk.Label(f, text=APP_TAGLINE, style='CardMuted.TLabel').pack(pady=(0, 20))
        ttk.Label(f, text='Username', style='Card.TLabel').pack(anchor='w')
        self.li_user = ttk.Entry(f, width=32)
        self.li_user.pack(pady=(2, 10))
        ttk.Label(f, text='Password', style='Card.TLabel').pack(anchor='w')
        self.li_pass = ttk.Entry(f, width=32, show='*')
        self.li_pass.pack(pady=(2, 16))
        self.li_pass.bind('<Return>', lambda e: self.do_login())
        ttk.Button(f, text='MASUK', style='Gold.TButton', width=30,
                   command=self.do_login).pack()
        self.li_user.focus()

    def _ensure_admin(self):
        if not self.dbs.user_by_username('admin'):
            self.dbs.user_save({'username': 'admin', 'passHash': _DEFAULT_ADMIN_HASH,
                                'name': 'Admin', 'role': 'admin'})

    def do_login(self):
        self._ensure_admin()
        u = self.li_user.get().strip().lower()
        p = self.li_pass.get()
        row = self.dbs.user_by_username(u)
        if row and row['passHash'] == hash_pass(p):
            self.user = {'username': row['username'], 'name': row['name'] or row['username'],
                         'role': row['role'] or 'crew'}
            self._build_main()
        else:
            messagebox.showerror('Gagal', 'Username atau password salah.')

    def is_admin(self):
        return self.user and self.user.get('role') == 'admin'

    # ------------------------------ kerangka utama ------------------------------
    def _build_main(self):
        for w in self.root.winfo_children():
            w.destroy()
        # header
        hdr = ttk.Frame(self.root, padding=(18, 12))
        hdr.pack(fill='x')
        brand = ttk.Label(hdr, text='— INSPIRASTORY —', background=BG,
                          foreground=GOLD2, font=(FONT_SERIF, 22))
        brand.pack(side='left')
        self.net_lbl = ttk.Label(hdr, text='...', style='Muted.TLabel')
        self.net_lbl.pack(side='right', padx=(12, 0))
        ttk.Button(hdr, text='Sinkronisasi', style='Gold.TButton',
                   command=self.do_sync).pack(side='right')
        ttk.Label(hdr, text='%s (%s)' % (self.user['name'], self.user['role']),
                  style='Muted.TLabel').pack(side='right', padx=12)
        ttk.Button(hdr, text='Keluar', command=self._build_login).pack(side='right')
        tk.Frame(self.root, bg='#3a2f18', height=2).pack(fill='x', padx=18)
        # notebook
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        self.pages = {}
        for key, label in [('dash', 'Dashboard'), ('cust', 'Customer'),
                           ('inc', 'Pemasukan'), ('exp', 'Pengeluaran'),
                           ('sch', 'Jadwal Foto'), ('ddl', 'Deadline Edit'),
                           ('prt', 'Cetak Foto'), ('rep', 'Laporan'),
                           ('tgt', 'Target'), ('set', 'Pengaturan')]:
            fr = ttk.Frame(self.nb, padding=12)
            self.nb.add(fr, text=label)
            self.pages[key] = fr
        self._build_dashboard(self.pages['dash'])
        self._build_customers(self.pages['cust'])
        self._build_income(self.pages['inc'])
        self._build_expenses(self.pages['exp'])
        self._build_schedules(self.pages['sch'])
        self._build_deadlines(self.pages['ddl'])
        self._build_prints(self.pages['prt'])
        self._build_report(self.pages['rep'])
        self._build_targets(self.pages['tgt'])
        self._build_settings(self.pages['set'])
        self.nb.bind('<<NotebookTabChanged>>', lambda e: self.refresh_page())
        self.refresh_page()
        threading.Thread(target=self._check_net, daemon=True).start()

    # ------------------------------ util GUI ------------------------------
    def card(self, parent, title=None):
        c = ttk.Frame(parent, style='Card.TFrame', padding=18)
        if title:
            ttk.Label(c, text=title, style='CardTitle.TLabel').pack(anchor='w', pady=(0, 10))
        return c

    def tree(self, parent, cols, widths=None):
        tw = ttk.Treeview(parent, columns=cols, show='headings', height=14)
        for i, c in enumerate(cols):
            tw.heading(c, text=c)
            tw.column(c, width=(widths[i] if widths else 120), anchor='w')
        sb = ttk.Scrollbar(parent, orient='vertical', command=tw.yview)
        tw.configure(yscrollcommand=sb.set)
        tw.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        return tw

    def entry_row(self, parent, label, default='', width=30, password=False):
        ttk.Label(parent, text=label, style='Card.TLabel').pack(anchor='w', pady=(6, 0))
        e = ttk.Entry(parent, width=width, show='*' if password else '')
        e.insert(0, str(default))
        e.pack(anchor='w', fill='x')
        return e

    def combo_row(self, parent, label, values, default=''):
        ttk.Label(parent, text=label, style='Card.TLabel').pack(anchor='w', pady=(6, 0))
        cb = ttk.Combobox(parent, values=values, state='readonly', width=28)
        if default in values:
            cb.set(default)
        elif values:
            cb.set(values[0])
        cb.pack(anchor='w', fill='x')
        return cb

    def _check_net(self):
        on = syncmod.is_online()
        self.online = on
        self.root.after(0, lambda: self.net_lbl.config(
            text='ONLINE' if on else 'OFFLINE',
            foreground=GREEN if on else RED))

    def do_sync(self):
        if not self.cfg:
            messagebox.showwarning('Sinkron', 'firebase_config.json tidak ditemukan.')
            return
        self.net_lbl.config(text='Sinkron...', foreground=GOLD2)
        threading.Thread(target=self._sync_bg, daemon=True).start()

    def _sync_bg(self):
        msgs = []
        try:
            ok, total = syncmod.sync_all(self.dbs, self.cfg, log=msgs.append)
            txt = 'OK: %d ditarik, %d dikirim, %d dihapus' % (
                total['pulled'], total['pushed'], total['deleted'])
        except Exception as e:
            txt = 'Gagal: %s' % e
            ok = False
        self.root.after(0, lambda: self._sync_done(ok, txt))

    def _sync_done(self, ok, txt):
        self.net_lbl.config(text='ONLINE' if ok else 'OFFLINE',
                            foreground=GREEN if ok else RED)
        messagebox.showinfo('Sinkronisasi', txt)
        self.refresh_page()

    def refresh_page(self):
        try:
            idx = self.nb.index(self.nb.select())
        except Exception:
            return
        key = ['dash', 'cust', 'inc', 'exp', 'sch', 'ddl', 'prt', 'rep', 'tgt', 'set'][idx]
        fn = getattr(self, '_refresh_' + key, None)
        if fn:
            fn()

    # ============================== DASHBOARD ==============================
    def _build_dashboard(self, p):
        self.dash_cards = ttk.Frame(p)
        self.dash_cards.pack(fill='x')
        self.dash_lists = ttk.Frame(p)
        self.dash_lists.pack(fill='both', expand=True, pady=(12, 0))
        lc = self.card(self.dash_lists, 'Jadwal Hari Ini')
        lc.pack(side='left', fill='both', expand=True, padx=(0, 6))
        self.dash_sch = tk.Listbox(lc, bg=BG3, fg=FG, font=(FONT_UI, 10),
                                   relief='flat', highlightthickness=0)
        self.dash_sch.pack(fill='both', expand=True)
        rc = self.card(self.dash_lists, 'Deadline Dekat')
        rc.pack(side='left', fill='both', expand=True, padx=(6, 0))
        self.dash_ddl = tk.Listbox(rc, bg=BG3, fg=FG, font=(FONT_UI, 10),
                                   relief='flat', highlightthickness=0)
        self.dash_ddl.pack(fill='both', expand=True)

    def _refresh_dash(self):
        for w in self.dash_cards.winfo_children():
            w.destroy()
        mk = month_iso()
        inc = self.dbs.income_sum_month(mk)
        exp = self.dbs.expense_sum_month(mk)
        for title, val, col in [('Omzet ' + nama_bulan(mk), rp(inc), GOLD2),
                               ('Pengeluaran', rp(exp), RED),
                               ('Laba Bersih', rp(inc - exp), GREEN),
                               ('Customer', str(len(self.dbs.customer_list())), FG)]:
            c = self.card(self.dash_cards)
            c.pack(side='left', fill='both', expand=True, padx=6)
            ttk.Label(c, text=title, style='CardMuted.TLabel').pack(anchor='w')
            ttk.Label(c, text=val, style='Big.TLabel', foreground=col).pack(anchor='w')
        # target bulan ini
        t = self.dbs.target_month_get(mk)
        if t and t['target']:
            pct = min(100, inc / t['target'] * 100) if t['target'] else 0
            c = self.card(self.dash_cards)
            c.pack(side='left', fill='both', expand=True, padx=6)
            ttk.Label(c, text='Target ' + nama_bulan(mk), style='CardMuted.TLabel').pack(anchor='w')
            ttk.Label(c, text='%d%% (%s / %s)' % (pct, rp(inc), rp(t['target'])),
                      style='Big.TLabel', foreground=GOLD2).pack(anchor='w')
            pb = ttk.Progressbar(c, length=180, mode='determinate', value=pct)
            pb.pack(anchor='w', pady=(6, 0))
        self.dash_sch.delete(0, 'end')
        for s in self.dbs.schedule_today():
            self.dash_sch.insert('end', '%s - %s (%s)' % (s['jam'] or '-', s['customer'], s['jenis']))
        if not self.dbs.schedule_today():
            self.dash_sch.insert('end', 'Tidak ada jadwal hari ini.')
        self.dash_ddl.delete(0, 'end')
        for d in self.dbs.deadline_list(active_only=True)[:10]:
            self.dash_ddl.insert('end', '%s - %s [%s]' % (
                fmt_tgl(d['deadline']), d['project'], d['status']))
        if not self.dbs.deadline_list(active_only=True):
            self.dash_ddl.insert('end', 'Tidak ada deadline aktif.')

    # ============================== CUSTOMER ==============================
    def _build_customers(self, p):
        top = ttk.Frame(p)
        top.pack(fill='x', pady=(0, 8))
        ttk.Label(top, text='Cari:').pack(side='left')
        self.cust_q = ttk.Entry(top, width=30)
        self.cust_q.pack(side='left', padx=6)
        self.cust_q.bind('<KeyRelease>', lambda e: self._refresh_cust())
        ttk.Button(top, text='+ Tambah Customer', style='Gold.TButton',
                   command=lambda: self._cust_form()).pack(side='right')
        ttk.Button(top, text='Edit', command=self._cust_edit).pack(side='right', padx=6)
        ttk.Button(top, text='Hapus', style='Danger.TButton',
                   command=self._cust_del).pack(side='right')
        self.cust_tree = self.tree(p, ['Nama', 'WA', 'Total', 'DP', 'Sisa', 'Status'],
                                   [180, 120, 120, 120, 120, 100])
        self.cust_tree.bind('<Double-1>', lambda e: self._cust_edit())

    def _cust_status(self, r):
        items = self.dbs.customer_items(r)
        total = sum((it.get('jumlah') or 0) * (it.get('harga') or 0) for it in items)
        dp = r['dpDibayar'] or 0
        return total, dp, ('LUNAS' if total > 0 and dp >= total else
                          ('DP %s' % rp(dp) if dp > 0 else 'Belum Bayar'))

    def _refresh_cust(self):
        tw = self.cust_tree
        tw.delete(*tw.get_children())
        for r in self.dbs.customer_list(self.cust_q.get().strip()):
            total, dp, st = self._cust_status(r)
            tw.insert('', 'end', iid=str(r['id']),
                      values=(r['nama'], r['wa'], rp(total), rp(dp), rp(total - dp), st))

    def _cust_edit(self):
        sel = self.cust_tree.selection()
        if not sel:
            messagebox.showinfo('Customer', 'Pilih customer dulu.')
            return
        self._cust_form(self.dbs.customer_get(int(sel[0])))

    def _cust_del(self):
        sel = self.cust_tree.selection()
        if not sel:
            return
        if messagebox.askyesno('Hapus', 'Hapus customer ini?'):
            self.dbs.customer_delete(int(sel[0]))
            self._refresh_cust()

    def _cust_form(self, r=None):
        r = r or {}
        win = tk.Toplevel(self.root)
        win.title('Customer Baru' if not r else 'Edit Customer')
        win.geometry('560x640')
        win.configure(bg=BG)
        win.transient(self.root)
        body = ttk.Frame(win, padding=16)
        body.pack(fill='both', expand=True)
        e_nama = self.entry_row(body, 'Nama *', r.get('nama', ''))
        e_wa = self.entry_row(body, 'WA', r.get('wa', ''))
        e_alamat = self.entry_row(body, 'Alamat', r.get('alamat', ''))
        e_cat = self.entry_row(body, 'Catatan', r.get('catatan', ''))
        ttk.Label(body, text='Layanan', style='Card.TLabel').pack(anchor='w', pady=(10, 0))
        items_fr = ttk.Frame(body)
        items_fr.pack(fill='x')
        item_rows = []

        def add_item(it=None):
            it = it or {}
            fr = ttk.Frame(items_fr)
            fr.pack(fill='x', pady=2)
            cb = ttk.Combobox(fr, values=[l for _, l in LAYANAN], state='readonly', width=22)
            cb.set(LAYANAN_LABEL.get(it.get('jenis', ''), 'Lainnya'))
            cb.pack(side='left', padx=(0, 4))
            ttk.Label(fr, text='Jml').pack(side='left')
            e_j = ttk.Entry(fr, width=5)
            e_j.insert(0, str(it.get('jumlah', 1) or 1))
            e_j.pack(side='left', padx=4)
            ttk.Label(fr, text='Harga').pack(side='left')
            e_h = ttk.Entry(fr, width=12)
            e_h.insert(0, str(it.get('harga', 0) or 0))
            e_h.pack(side='left', padx=4)
            ttk.Button(fr, text='x', width=3,
                       command=lambda: (fr.destroy(), item_rows.remove((cb, e_j, e_h)),
                                        calc())).pack(side='left')
            item_rows.append((cb, e_j, e_h))
            for w in (e_j, e_h):
                w.bind('<KeyRelease>', lambda e: calc())
            cb.bind('<<ComboboxSelected>>', lambda e: calc())
            # JANGAN panggil calc() di sini: lbl_total/lbl_sisa/e_dp belum dibuat
            # saat add_item() dipanggil pertama kali (form build) -> NameError.
            # calc() dipanggil eksplisit di akhir form setelah semua widget ada.

        def calc():
            total = 0
            for cb, e_j, e_h in item_rows:
                try:
                    total += float(e_j.get() or 0) * float(e_h.get() or 0)
                except ValueError:
                    pass
            lbl_total.config(text=rp(total))
            try:
                dp = float(e_dp.get() or 0)
            except ValueError:
                dp = 0
            lbl_sisa.config(text=rp(total - dp))
            return total

        for it in self.dbs.customer_items(r):
            add_item(it)
        if not item_rows:
            add_item()
        ttk.Button(body, text='+ Tambah Layanan', command=lambda: add_item()).pack(
            anchor='w', pady=4)
        sum_fr = ttk.Frame(body)
        sum_fr.pack(fill='x', pady=6)
        ttk.Label(sum_fr, text='Total:', style='Card.TLabel').pack(side='left')
        lbl_total = ttk.Label(sum_fr, text='Rp0', style='CardTitle.TLabel')
        lbl_total.pack(side='left', padx=8)
        ttk.Label(sum_fr, text='Sisa:', style='Card.TLabel').pack(side='left', padx=(16, 0))
        lbl_sisa = ttk.Label(sum_fr, text='Rp0', style='CardTitle.TLabel')
        lbl_sisa.pack(side='left', padx=8)
        e_dp = self.entry_row(body, 'DP Dibayar (Rp)', r.get('dpDibayar', 0) or 0)
        e_dp.bind('<KeyRelease>', lambda e: calc())
        calc()  # hitung awal setelah semua widget (lbl_total/lbl_sisa/e_dp) ada

        def save():
            nama = e_nama.get().strip()
            if not nama:
                messagebox.showwarning('Customer', 'Nama wajib diisi.', parent=win)
                return
            items = []
            for cb, e_j, e_h in item_rows:
                jenis = [k for k, l in LAYANAN if l == cb.get()]
                try:
                    jml = float(e_j.get() or 0)
                    hrg = float(e_h.get() or 0)
                except ValueError:
                    jml, hrg = 0, 0
                if jml > 0 and hrg > 0:
                    items.append({'jenis': jenis[0] if jenis else 'lainnya',
                                  'attire': '', 'ukuran': '-',
                                  'jumlah': jml, 'harga': hrg})
            total = sum(i['jumlah'] * i['harga'] for i in items)
            try:
                dp = float(e_dp.get() or 0)
            except ValueError:
                dp = 0
            old_dp = float(r.get('dpDibayar') or 0)
            data = {'nama': nama, 'wa': e_wa.get().strip(), 'alamat': e_alamat.get().strip(),
                    'catatan': e_cat.get().strip(), 'items': json.dumps(items, ensure_ascii=False),
                    'totalHarga': total, 'dpDibayar': dp,
                    'tglDp': r.get('tglDp') or today_iso(),
                    'jamDp': r.get('jamDp') or datetime.now().strftime('%H:%M'),
                    'createdAt': r.get('createdAt') or datetime.now().isoformat(timespec='seconds')}
            cid = self.dbs.customer_save(data, r.get('id'))
            # DP (baru maupun tambahan) otomatis masuk pemasukan
            if dp > old_dp:
                self.dbs.income_save({'tanggal': today_iso(),
                                      'jam': datetime.now().strftime('%H:%M'),
                                      'customer': nama, 'jumlah': dp - old_dp,
                                      'keterangan': 'DP - ' + nama, 'tipe': 'dp',
                                      'customerId': '', 'printId': '',
                                      'createdAt': datetime.now().isoformat(timespec='seconds')})
            win.destroy()
            self._refresh_cust()

        ttk.Button(body, text='SIMPAN', style='Gold.TButton', command=save).pack(
            fill='x', pady=12)
        calc()

    # ============================== PEMASUKAN ==============================
    def _build_income(self, p):
        top = ttk.Frame(p)
        top.pack(fill='x', pady=(0, 8))
        ttk.Label(top, text='Bulan:').pack(side='left')
        self.inc_month = ttk.Entry(top, width=10)
        self.inc_month.insert(0, month_iso())
        self.inc_month.pack(side='left', padx=6)
        ttk.Button(top, text='Tampilkan', command=self._refresh_inc).pack(side='left')
        self.inc_total_lbl = ttk.Label(top, text='', style='Title.TLabel',
                                       font=(FONT_UI, 12, 'bold'))
        self.inc_total_lbl.pack(side='left', padx=16)
        ttk.Button(top, text='+ Tambah', style='Gold.TButton',
                   command=lambda: self._income_form()).pack(side='right')
        ttk.Button(top, text='Edit', command=self._income_edit).pack(side='right', padx=6)
        ttk.Button(top, text='Hapus', style='Danger.TButton',
                   command=self._income_del).pack(side='right')
        self.inc_tree = self.tree(p, ['Tanggal', 'Customer', 'Keterangan', 'Tipe', 'Jumlah'],
                                  [100, 160, 260, 80, 130])
        self.inc_tree.bind('<Double-1>', lambda e: self._income_edit())

    def _refresh_inc(self):
        mk = self.inc_month.get().strip() or month_iso()
        tw = self.inc_tree
        tw.delete(*tw.get_children())
        total = 0
        for r in self.dbs.income_list(mk):
            total += r['jumlah'] or 0
            tw.insert('', 'end', iid=str(r['id']),
                      values=(fmt_tgl(r['tanggal']), r['customer'], r['keterangan'],
                              r['tipe'], rp(r['jumlah'])))
        self.inc_total_lbl.config(text='Total: ' + rp(total))

    def _income_edit(self):
        sel = self.inc_tree.selection()
        if not sel:
            messagebox.showinfo('Pemasukan', 'Pilih data dulu.')
            return
        self._income_form(self.dbs.income_get(int(sel[0])))

    def _income_del(self):
        sel = self.inc_tree.selection()
        if sel and messagebox.askyesno('Hapus', 'Hapus pemasukan ini?'):
            self.dbs.income_delete(int(sel[0]))
            self._refresh_inc()

    def _income_form(self, r=None):
        r = r or {}
        win, body = self._modal('Pemasukan Baru' if not r else 'Edit Pemasukan')
        e_tgl = self.entry_row(body, 'Tanggal (YYYY-MM-DD)', r.get('tanggal', today_iso()))
        custs = [c['nama'] for c in self.dbs.customer_list()]
        cb_c = self.combo_row(body, 'Customer', [''] + custs, r.get('customer', ''))
        e_jml = self.entry_row(body, 'Jumlah (Rp) *', r.get('jumlah', '') or '')
        e_ket = self.entry_row(body, 'Keterangan', r.get('keterangan', ''))

        def save():
            try:
                jml = float(e_jml.get() or 0)
            except ValueError:
                jml = 0
            if not jml:
                messagebox.showwarning('Pemasukan', 'Jumlah wajib diisi.', parent=win)
                return
            self.dbs.income_save(
                {'tanggal': e_tgl.get().strip() or today_iso(),
                 'jam': r.get('jam') or datetime.now().strftime('%H:%M'),
                 'customer': cb_c.get(), 'jumlah': jml,
                 'keterangan': e_ket.get().strip(), 'tipe': r.get('tipe', 'manual'),
                 'customerId': r.get('customerId', ''), 'printId': r.get('printId', ''),
                 'createdAt': r.get('createdAt') or datetime.now().isoformat(timespec='seconds')},
                r.get('id'))
            win.destroy()
            self._refresh_inc()

        ttk.Button(body, text='SIMPAN', style='Gold.TButton', command=save).pack(
            fill='x', pady=12)

    # ============================== PENGELUARAN ==============================
    def _build_expenses(self, p):
        top = ttk.Frame(p)
        top.pack(fill='x', pady=(0, 8))
        ttk.Label(top, text='Bulan:').pack(side='left')
        self.exp_month = ttk.Entry(top, width=10)
        self.exp_month.insert(0, month_iso())
        self.exp_month.pack(side='left', padx=6)
        ttk.Button(top, text='Tampilkan', command=self._refresh_exp).pack(side='left')
        self.exp_total_lbl = ttk.Label(top, text='', style='Title.TLabel',
                                       font=(FONT_UI, 12, 'bold'))
        self.exp_total_lbl.pack(side='left', padx=16)
        ttk.Button(top, text='+ Tambah', style='Gold.TButton',
                   command=lambda: self._expense_form()).pack(side='right')
        ttk.Button(top, text='Edit', command=self._expense_edit).pack(side='right', padx=6)
        ttk.Button(top, text='Hapus', style='Danger.TButton',
                   command=self._expense_del).pack(side='right')
        self.exp_tree = self.tree(p, ['Tanggal', 'Kategori', 'Keterangan', 'Jumlah'],
                                  [100, 170, 280, 130])
        self.exp_tree.bind('<Double-1>', lambda e: self._expense_edit())

    def _refresh_exp(self):
        mk = self.exp_month.get().strip() or month_iso()
        tw = self.exp_tree
        tw.delete(*tw.get_children())
        total = 0
        for r in self.dbs.expense_list(mk):
            total += r['jumlah'] or 0
            tw.insert('', 'end', iid=str(r['id']),
                      values=(fmt_tgl(r['tanggal']), EXP_LABEL.get(r['kategori'], r['kategori']),
                              r['keterangan'], rp(r['jumlah'])))
        self.exp_total_lbl.config(text='Total: ' + rp(total))

    def _expense_edit(self):
        sel = self.exp_tree.selection()
        if not sel:
            messagebox.showinfo('Pengeluaran', 'Pilih data dulu.')
            return
        self._expense_form(self.dbs.expense_get(int(sel[0])))

    def _expense_del(self):
        sel = self.exp_tree.selection()
        if sel and messagebox.askyesno('Hapus', 'Hapus pengeluaran ini?'):
            self.dbs.expense_delete(int(sel[0]))
            self._refresh_exp()

    def _expense_form(self, r=None):
        r = r or {}
        win, body = self._modal('Pengeluaran Baru' if not r else 'Edit Pengeluaran')
        e_tgl = self.entry_row(body, 'Tanggal (YYYY-MM-DD)', r.get('tanggal', today_iso()))
        cb_k = self.combo_row(body, 'Kategori', [l for _, l in EXP_CATS],
                              EXP_LABEL.get(r.get('kategori', ''), 'Lainnya'))
        e_jml = self.entry_row(body, 'Jumlah (Rp) *', r.get('jumlah', '') or '')
        e_ket = self.entry_row(body, 'Keterangan', r.get('keterangan', ''))

        def save():
            try:
                jml = float(e_jml.get() or 0)
            except ValueError:
                jml = 0
            if not jml:
                messagebox.showwarning('Pengeluaran', 'Jumlah wajib diisi.', parent=win)
                return
            kat = [k for k, l in EXP_CATS if l == cb_k.get()]
            self.dbs.expense_save(
                {'tanggal': e_tgl.get().strip() or today_iso(),
                 'jam': r.get('jam') or datetime.now().strftime('%H:%M'),
                 'kategori': kat[0] if kat else 'lainnya', 'jumlah': jml,
                 'keterangan': e_ket.get().strip(),
                 'createdAt': r.get('createdAt') or datetime.now().isoformat(timespec='seconds')},
                r.get('id'))
            win.destroy()
            self._refresh_exp()

        ttk.Button(body, text='SIMPAN', style='Gold.TButton', command=save).pack(
            fill='x', pady=12)

    # ------------------------------ modal generik ------------------------------
    def _modal(self, title, h=520, w=480):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry('%dx%d' % (w, h))
        win.configure(bg=BG)
        win.transient(self.root)
        win.grab_set()
        body = ttk.Frame(win, padding=16)
        body.pack(fill='both', expand=True)
        return win, body

    # ============================== JADWAL FOTO ==============================
    def _build_schedules(self, p):
        top = ttk.Frame(p)
        top.pack(fill='x', pady=(0, 8))
        ttk.Button(top, text='+ Tambah Jadwal', style='Gold.TButton',
                   command=lambda: self._schedule_form()).pack(side='right')
        ttk.Button(top, text='Edit', command=self._schedule_edit).pack(side='right', padx=6)
        ttk.Button(top, text='Hapus', style='Danger.TButton',
                   command=self._schedule_del).pack(side='right')
        self.sch_tree = self.tree(p, ['Tanggal', 'Jam', 'Customer', 'Jenis', 'Tempat',
                                      'Crew', 'Status'],
                                  [100, 70, 160, 100, 100, 130, 100])
        self.sch_tree.bind('<Double-1>', lambda e: self._schedule_edit())

    def _refresh_sch(self):
        tw = self.sch_tree
        tw.delete(*tw.get_children())
        for r in self.dbs.schedule_list():
            tw.insert('', 'end', iid=str(r['id']),
                      values=(fmt_tgl(r['tanggal']), r['jam'], r['customer'],
                              dict(JENIS_JADWAL).get(r['jenis'], r['jenis']),
                              dict(TEMPAT_JADWAL).get(r['tempat'], r['tempat']),
                              r['crew'], r['status']))

    def _schedule_edit(self):
        sel = self.sch_tree.selection()
        if not sel:
            messagebox.showinfo('Jadwal', 'Pilih jadwal dulu.')
            return
        self._schedule_form(self.dbs.schedule_get(int(sel[0])))

    def _schedule_del(self):
        sel = self.sch_tree.selection()
        if sel and messagebox.askyesno('Hapus', 'Hapus jadwal ini?'):
            self.dbs.schedule_delete(int(sel[0]))
            self._refresh_sch()

    def _schedule_form(self, r=None):
        r = r or {}
        win, body = self._modal('Jadwal Baru' if not r else 'Edit Jadwal', h=620)
        e_tgl = self.entry_row(body, 'Tanggal (YYYY-MM-DD) *', r.get('tanggal', today_iso()))
        e_jam = self.entry_row(body, 'Jam (HH:MM)', r.get('jam', ''))
        custs = [c['nama'] for c in self.dbs.customer_list()]
        cb_c = self.combo_row(body, 'Customer', [''] + custs, r.get('customer', ''))
        cb_j = self.combo_row(body, 'Jenis', [l for _, l in JENIS_JADWAL],
                              dict(JENIS_JADWAL).get(r.get('jenis', ''), 'Foto'))
        cb_t = self.combo_row(body, 'Tempat', [l for _, l in TEMPAT_JADWAL],
                              dict(TEMPAT_JADWAL).get(r.get('tempat', ''), 'Di Studio'))
        e_crew = self.entry_row(body, 'Fotografer / Videografer', r.get('crew', ''))
        e_lok = self.entry_row(body, 'Lokasi', r.get('lokasi', ''))
        e_paket = self.entry_row(body, 'Paket', r.get('paket', ''))
        e_cat = self.entry_row(body, 'Catatan', r.get('attire', ''))
        cb_s = self.combo_row(body, 'Status', STATUS_JADWAL, r.get('status', 'terjadwal'))

        def save():
            if not e_tgl.get().strip():
                messagebox.showwarning('Jadwal', 'Tanggal wajib diisi.', parent=win)
                return
            jenis = [k for k, l in JENIS_JADWAL if l == cb_j.get()]
            tempat = [k for k, l in TEMPAT_JADWAL if l == cb_t.get()]
            self.dbs.schedule_save(
                {'tanggal': e_tgl.get().strip(), 'jam': e_jam.get().strip(),
                 'customer': cb_c.get(),
                 'jenis': jenis[0] if jenis else 'foto',
                 'tempat': tempat[0] if tempat else 'studio',
                 'crew': e_crew.get().strip(), 'crewWa': r.get('crewWa', ''),
                 'lokasi': e_lok.get().strip(), 'maps': r.get('maps', ''),
                 'paket': e_paket.get().strip(), 'attire': e_cat.get().strip(),
                 'status': cb_s.get(),
                 'createdAt': r.get('createdAt') or datetime.now().isoformat(timespec='seconds')},
                r.get('id'))
            win.destroy()
            self._refresh_sch()

        ttk.Button(body, text='SIMPAN', style='Gold.TButton', command=save).pack(
            fill='x', pady=12)

    # ============================== DEADLINE EDIT ==============================
    def _build_deadlines(self, p):
        top = ttk.Frame(p)
        top.pack(fill='x', pady=(0, 8))
        ttk.Button(top, text='+ Tambah Deadline', style='Gold.TButton',
                   command=lambda: self._deadline_form()).pack(side='right')
        ttk.Button(top, text='Edit', command=self._deadline_edit).pack(side='right', padx=6)
        ttk.Button(top, text='Tandai Selesai', command=self._deadline_done).pack(
            side='right', padx=6)
        ttk.Button(top, text='Hapus', style='Danger.TButton',
                   command=self._deadline_del).pack(side='right')
        self.ddl_tree = self.tree(p, ['Project', 'Customer', 'Deadline', 'Progress', 'Status'],
                                  [200, 160, 110, 90, 100])
        self.ddl_tree.bind('<Double-1>', lambda e: self._deadline_edit())

    def _refresh_ddl(self):
        tw = self.ddl_tree
        tw.delete(*tw.get_children())
        for r in self.dbs.deadline_list():
            tw.insert('', 'end', iid=str(r['id']),
                      values=(r['project'], r['customer'], fmt_tgl(r['deadline']),
                              '%d%%' % (r['progress'] or 0), r['status']))

    def _deadline_edit(self):
        sel = self.ddl_tree.selection()
        if not sel:
            messagebox.showinfo('Deadline', 'Pilih deadline dulu.')
            return
        self._deadline_form(self.dbs.deadline_get(int(sel[0])))

    def _deadline_done(self):
        sel = self.ddl_tree.selection()
        if not sel:
            return
        r = self.dbs.deadline_get(int(sel[0]))
        r['status'] = 'selesai'
        r['progress'] = 100
        self.dbs.deadline_save(r, r['id'])
        self._refresh_ddl()

    def _deadline_del(self):
        sel = self.ddl_tree.selection()
        if sel and messagebox.askyesno('Hapus', 'Hapus deadline ini?'):
            self.dbs.deadline_delete(int(sel[0]))
            self._refresh_ddl()

    def _deadline_form(self, r=None):
        r = r or {}
        win, body = self._modal('Deadline Baru' if not r else 'Edit Deadline')
        e_proj = self.entry_row(body, 'Nama Project *', r.get('project', ''))
        custs = [c['nama'] for c in self.dbs.customer_list()]
        cb_c = self.combo_row(body, 'Customer', [''] + custs, r.get('customer', ''))
        e_ddl = self.entry_row(body, 'Deadline (YYYY-MM-DD)', r.get('deadline', today_iso()))
        e_prog = self.entry_row(body, 'Progress (0-100)', r.get('progress', 0) or 0)
        cb_s = self.combo_row(body, 'Status', STATUS_DEADLINE, r.get('status', 'antri'))

        def save():
            if not e_proj.get().strip():
                messagebox.showwarning('Deadline', 'Nama project wajib diisi.', parent=win)
                return
            try:
                prog = max(0, min(100, int(e_prog.get() or 0)))
            except ValueError:
                prog = 0
            self.dbs.deadline_save(
                {'project': e_proj.get().strip(), 'customer': cb_c.get(),
                 'deadline': e_ddl.get().strip() or today_iso(),
                 'jam': r.get('jam') or datetime.now().strftime('%H:%M'),
                 'status': 'selesai' if prog >= 100 else cb_s.get(),
                 'progress': prog,
                 'createdAt': r.get('createdAt') or datetime.now().isoformat(timespec='seconds')},
                r.get('id'))
            win.destroy()
            self._refresh_ddl()

        ttk.Button(body, text='SIMPAN', style='Gold.TButton', command=save).pack(
            fill='x', pady=12)

    # ============================== CETAK FOTO ==============================
    def _build_prints(self, p):
        top = ttk.Frame(p)
        top.pack(fill='x', pady=(0, 8))
        ttk.Label(top, text='Cari:').pack(side='left')
        self.prt_q = ttk.Entry(top, width=24)
        self.prt_q.pack(side='left', padx=6)
        self.prt_q.bind('<KeyRelease>', lambda e: self._refresh_prt())
        ttk.Button(top, text='+ Order Cetak', style='Gold.TButton',
                   command=lambda: self._print_form()).pack(side='right')
        ttk.Button(top, text='Edit', command=self._print_edit).pack(side='right', padx=6)
        ttk.Button(top, text='Hapus', style='Danger.TButton',
                   command=self._print_del).pack(side='right')
        self.prt_tree = self.tree(p, ['Tanggal', 'Customer', 'Ukuran', 'Jumlah',
                                      'Total', 'DP', 'Status'],
                                  [100, 160, 80, 70, 120, 120, 100])
        self.prt_tree.bind('<Double-1>', lambda e: self._print_edit())

    def _refresh_prt(self):
        tw = self.prt_tree
        tw.delete(*tw.get_children())
        for r in self.dbs.print_list(self.prt_q.get().strip()):
            tw.insert('', 'end', iid=str(r['id']),
                      values=(fmt_tgl(r['tanggal']), r['customer'], r['ukuran'],
                              int(r['jumlah'] or 0), rp(r['totalHarga']),
                              rp(r['dpDibayar']), r['status']))

    def _print_edit(self):
        sel = self.prt_tree.selection()
        if not sel:
            messagebox.showinfo('Cetak', 'Pilih order dulu.')
            return
        self._print_form(self.dbs.print_get(int(sel[0])))

    def _print_del(self):
        sel = self.prt_tree.selection()
        if sel and messagebox.askyesno('Hapus', 'Hapus order cetak ini?'):
            self.dbs.print_delete(int(sel[0]))
            self._refresh_prt()

    def _print_form(self, r=None):
        r = r or {}
        win, body = self._modal('Order Cetak Baru' if not r else 'Edit Order Cetak', h=620)
        e_tgl = self.entry_row(body, 'Tanggal (YYYY-MM-DD)', r.get('tanggal', today_iso()))
        custs = [c['nama'] for c in self.dbs.customer_list()]
        cb_c = self.combo_row(body, 'Customer *', [''] + custs, r.get('customer', ''))
        cb_u = self.combo_row(body, 'Ukuran', UKURAN_CETAK, r.get('ukuran', '8R'))
        e_jml = self.entry_row(body, 'Jumlah (lembar)', r.get('jumlah', 1) or 1)
        e_hrg = self.entry_row(body, 'Harga per lembar (Rp)', r.get('harga', '') or '')
        e_ddl = self.entry_row(body, 'Deadline (YYYY-MM-DD, opsional)', r.get('deadline', ''))
        e_dp = self.entry_row(body, 'DP Dibayar (Rp)', r.get('dpDibayar', 0) or 0)
        e_cat = self.entry_row(body, 'Catatan', r.get('catatan', ''))
        cb_s = self.combo_row(body, 'Status', STATUS_CETAK, r.get('status', 'diproses'))
        lbl_total = ttk.Label(body, text='Total: Rp0', style='CardTitle.TLabel')
        lbl_total.pack(anchor='w', pady=6)

        def calc(*a):
            try:
                j, h = float(e_jml.get() or 0), float(e_hrg.get() or 0)
            except ValueError:
                j, h = 0, 0
            lbl_total.config(text='Total: ' + rp(j * h))
            return j * h

        def on_ukuran(*a):
            if cb_u.get() in UKURAN_HARGA and not e_hrg.get().strip():
                e_hrg.delete(0, 'end')
                e_hrg.insert(0, str(UKURAN_HARGA[cb_u.get()]))
            calc()

        cb_u.bind('<<ComboboxSelected>>', on_ukuran)
        e_jml.bind('<KeyRelease>', calc)
        e_hrg.bind('<KeyRelease>', calc)
        on_ukuran()

        def save():
            if not cb_c.get():
                messagebox.showwarning('Cetak', 'Customer wajib diisi.', parent=win)
                return
            try:
                jml = float(e_jml.get() or 0)
                hrg = float(e_hrg.get() or 0)
            except ValueError:
                messagebox.showwarning('Cetak', 'Jumlah/harga tidak valid.', parent=win)
                return
            total = jml * hrg
            if total <= 0:
                messagebox.showwarning('Cetak', 'Jumlah dan harga wajib diisi.', parent=win)
                return
            try:
                dp = float(e_dp.get() or 0)
            except ValueError:
                dp = 0
            old_dp = float(r.get('dpDibayar') or 0)
            data = {'tanggal': e_tgl.get().strip() or today_iso(),
                    'jamOrder': r.get('jamOrder') or datetime.now().strftime('%H:%M'),
                    'deadline': e_ddl.get().strip(), 'jamDeadline': r.get('jamDeadline', ''),
                    'customer': cb_c.get(), 'ukuran': cb_u.get(), 'jumlah': jml,
                    'harga': hrg, 'totalHarga': total, 'dpDibayar': dp,
                    'tglDp': r.get('tglDp') or today_iso(),
                    'jamDp': r.get('jamDp') or datetime.now().strftime('%H:%M'),
                    'status': cb_s.get(), 'catatan': e_cat.get().strip(),
                    'createdAt': r.get('createdAt') or datetime.now().isoformat(timespec='seconds')}
            self.dbs.print_save(data, r.get('id'))
            if dp > old_dp:
                self.dbs.income_save(
                    {'tanggal': today_iso(), 'jam': datetime.now().strftime('%H:%M'),
                     'customer': cb_c.get(), 'jumlah': dp - old_dp,
                     'keterangan': 'DP Cetak Foto - ' + cb_c.get(), 'tipe': 'dp',
                     'customerId': '', 'printId': '',
                     'createdAt': datetime.now().isoformat(timespec='seconds')})
            win.destroy()
            self._refresh_prt()

        ttk.Button(body, text='SIMPAN', style='Gold.TButton', command=save).pack(
            fill='x', pady=12)

    # ============================== LAPORAN ==============================
    def _build_report(self, p):
        top = ttk.Frame(p)
        top.pack(fill='x', pady=(0, 8))
        ttk.Label(top, text='Bulan:').pack(side='left')
        self.rep_month = ttk.Entry(top, width=10)
        self.rep_month.insert(0, month_iso())
        self.rep_month.pack(side='left', padx=6)
        ttk.Button(top, text='Tampilkan', command=self._refresh_rep).pack(side='left')
        ttk.Button(top, text='Simpan sebagai .txt', style='Gold.TButton',
                   command=self._report_save).pack(side='right')
        self.rep_text = tk.Text(p, bg=BG2, fg=FG, font=(FONT_MONO, 10),
                                relief='flat', highlightthickness=0, wrap='word')
        self.rep_text.pack(fill='both', expand=True)

    def _report_text(self, mk):
        inc = self.dbs.income_list(mk)
        exp = self.dbs.expense_list(mk)
        t_inc = sum(r['jumlah'] or 0 for r in inc)
        t_exp = sum(r['jumlah'] or 0 for r in exp)
        kat = {}
        for r in exp:
            k = EXP_LABEL.get(r['kategori'], r['kategori'])
            kat[k] = kat.get(k, 0) + (r['jumlah'] or 0)
        lines = []
        lines.append('=' * 52)
        lines.append('LAPORAN BULANAN - INSPIRASTORY')
        lines.append('Periode: ' + nama_bulan(mk))
        lines.append('=' * 52)
        lines.append('Total Pemasukan   : %s (%d transaksi)' % (rp(t_inc), len(inc)))
        lines.append('Total Pengeluaran : %s (%d transaksi)' % (rp(t_exp), len(exp)))
        lines.append('Laba Bersih       : %s' % rp(t_inc - t_exp))
        lines.append('')
        lines.append('-' * 52)
        lines.append('RINCIAN PEMASUKAN')
        lines.append('-' * 52)
        for r in inc:
            lines.append('%-10s %-20s %15s' % (fmt_tgl(r['tanggal']),
                                              (r['keterangan'] or r['customer'])[:20],
                                              rp(r['jumlah'])))
        if not inc:
            lines.append('(belum ada pemasukan)')
        lines.append('')
        lines.append('-' * 52)
        lines.append('RINCIAN PENGELUARAN PER KATEGORI')
        lines.append('-' * 52)
        for k in sorted(kat, key=kat.get, reverse=True):
            lines.append('%-28s %15s' % (k[:28], rp(kat[k])))
        if not kat:
            lines.append('(belum ada pengeluaran)')
        lines.append('')
        lines.append('Dicetak: ' + datetime.now().strftime('%d/%m/%Y %H:%M'))
        return '\n'.join(lines)

    def _refresh_rep(self):
        mk = self.rep_month.get().strip() or month_iso()
        self.rep_text.delete('1.0', 'end')
        self.rep_text.insert('1.0', self._report_text(mk))

    def _report_save(self):
        mk = self.rep_month.get().strip() or month_iso()
        path = filedialog.asksaveasfilename(
            defaultextension='.txt',
            initialfile='Laporan-InspiraStory-%s.txt' % mk,
            filetypes=[('Text', '*.txt')])
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._report_text(mk))
            messagebox.showinfo('Laporan', 'Laporan disimpan:\n' + path)

    # ============================== TARGET ==============================
    def _build_targets(self, p):
        self.tgt_body = ttk.Frame(p)
        self.tgt_body.pack(fill='both', expand=True)

    def _refresh_tgt(self):
        for w in self.tgt_body.winfo_children():
            w.destroy()
        mk = month_iso()
        yk = mk[:4]
        inc_m = self.dbs.income_sum_month(mk)
        inc_y = sum(self.dbs.income_sum_month('%s-%02d' % (yk, m)) for m in range(1, 13))
        # target bulanan
        c1 = self.card(self.tgt_body, 'Target Bulanan - ' + nama_bulan(mk))
        c1.pack(fill='x', pady=6)
        tm = self.dbs.target_month_get(mk)
        tv = tm['target'] if tm else 0
        pct = min(100, inc_m / tv * 100) if tv else 0
        ttk.Label(c1, text='Target: %s   |   Tercapai: %s (%d%%)' % (rp(tv), rp(inc_m), pct),
                  style='Card.TLabel').pack(anchor='w')
        ttk.Progressbar(c1, length=400, mode='determinate', value=pct).pack(
            anchor='w', pady=6, fill='x')
        fr = ttk.Frame(c1)
        fr.pack(anchor='w')
        self.tgt_m_entry = ttk.Entry(fr, width=18)
        self.tgt_m_entry.insert(0, str(int(tv)) if tv else '')
        self.tgt_m_entry.pack(side='left')
        ttk.Button(fr, text='Set Target Bulan Ini', style='Gold.TButton',
                   command=self._target_set_month).pack(side='left', padx=8)
        # target tahunan
        c2 = self.card(self.tgt_body, 'Target Tahunan - ' + yk)
        c2.pack(fill='x', pady=6)
        ty = self.dbs.target_year_get(yk)
        yv = ty['target'] if ty else 0
        pcty = min(100, inc_y / yv * 100) if yv else 0
        ttk.Label(c2, text='Target: %s   |   Tercapai: %s (%d%%)' % (rp(yv), rp(inc_y), pcty),
                  style='Card.TLabel').pack(anchor='w')
        ttk.Progressbar(c2, length=400, mode='determinate', value=pcty).pack(
            anchor='w', pady=6, fill='x')
        fr2 = ttk.Frame(c2)
        fr2.pack(anchor='w')
        self.tgt_y_entry = ttk.Entry(fr2, width=18)
        self.tgt_y_entry.insert(0, str(int(yv)) if yv else '')
        self.tgt_y_entry.pack(side='left')
        ttk.Button(fr2, text='Set Target Tahun Ini', style='Gold.TButton',
                   command=self._target_set_year).pack(side='left', padx=8)

    def _target_set_month(self):
        if not self.is_admin():
            messagebox.showwarning('Target', 'Hanya admin yang bisa set target.')
            return
        try:
            v = float(self.tgt_m_entry.get() or 0)
        except ValueError:
            messagebox.showwarning('Target', 'Nominal tidak valid.')
            return
        mk = month_iso()
        ex = self.dbs.target_month_get(mk)
        self.dbs.target_save({'bulan': mk, 'tahun': '', 'target': v},
                             ex['id'] if ex else None)
        self._refresh_tgt()

    def _target_set_year(self):
        if not self.is_admin():
            messagebox.showwarning('Target', 'Hanya admin yang bisa set target.')
            return
        try:
            v = float(self.tgt_y_entry.get() or 0)
        except ValueError:
            messagebox.showwarning('Target', 'Nominal tidak valid.')
            return
        yk = month_iso()[:4]
        ex = self.dbs.target_year_get(yk)
        self.dbs.target_save({'bulan': '', 'tahun': yk, 'target': v},
                             ex['id'] if ex else None)
        self._refresh_tgt()

    # ============================== PENGATURAN ==============================
    def _build_settings(self, p):
        # ganti password
        c1 = self.card(p, 'Ganti Password')
        c1.pack(fill='x', pady=6)
        fr = ttk.Frame(c1)
        fr.pack(fill='x')
        self.set_old = ttk.Entry(fr, width=20, show='*')
        self.set_old.pack(side='left', padx=(0, 6))
        self.set_old.insert(0, '')
        ttk.Label(fr, text='Password lama', style='CardMuted.TLabel').pack(side='left')
        fr2 = ttk.Frame(c1)
        fr2.pack(fill='x', pady=6)
        self.set_new = ttk.Entry(fr2, width=20, show='*')
        self.set_new.pack(side='left', padx=(0, 6))
        ttk.Label(fr2, text='Password baru', style='CardMuted.TLabel').pack(side='left')
        self.set_new2 = ttk.Entry(fr2, width=20, show='*')
        self.set_new2.pack(side='left', padx=(12, 6))
        ttk.Label(fr2, text='Ulangi', style='CardMuted.TLabel').pack(side='left')
        self.pass_msg = ttk.Label(c1, text='', style='CardMuted.TLabel')
        self.pass_msg.pack(anchor='w')
        ttk.Button(c1, text='Ganti Password', style='Gold.TButton',
                   command=self._change_pass).pack(anchor='w', pady=(6, 0))
        # kelola user
        c2 = self.card(p, 'Kelola Akun')
        c2.pack(fill='x', pady=6)
        btn_fr = ttk.Frame(c2)
        btn_fr.pack(fill='x', pady=(0, 6))
        ttk.Button(btn_fr, text='+ Tambah Akun', command=self._user_add).pack(side='left')
        ttk.Button(btn_fr, text='Reset Password', command=self._user_reset).pack(
            side='left', padx=6)
        ttk.Button(btn_fr, text='Hapus', style='Danger.TButton',
                   command=self._user_del).pack(side='left')
        self.user_tree = ttk.Treeview(c2, columns=['Username', 'Nama', 'Role'],
                                      show='headings', height=4)
        for col in ['Username', 'Nama', 'Role']:
            self.user_tree.heading(col, text=col)
            self.user_tree.column(col, width=140)
        self.user_tree.pack(fill='x')
        # backup & data
        c3 = self.card(p, 'Backup & Data')
        c3.pack(fill='x', pady=6)
        ttk.Button(c3, text='Backup Database', style='Gold.TButton',
                   command=self._backup).pack(side='left')
        ttk.Button(c3, text='Sinkronisasi Sekarang', command=self.do_sync).pack(
            side='left', padx=8)
        self.pending_lbl = ttk.Label(c3, text='', style='CardMuted.TLabel')
        self.pending_lbl.pack(side='left', padx=12)
        ttk.Label(p, text='Lokasi database: ' + DB_PATH, style='Muted.TLabel',
                  wraplength=900).pack(anchor='w', pady=8)

    def _refresh_set(self):
        tw = self.user_tree
        tw.delete(*tw.get_children())
        for u in self.dbs.user_list():
            tw.insert('', 'end', iid=str(u['id']),
                      values=(u['username'], u['name'], u['role']))
        n = self.dbs.count_pending()
        self.pending_lbl.config(text='Menunggu sinkron: %d perubahan' % n)

    def _change_pass(self):
        old, new, new2 = self.set_old.get(), self.set_new.get(), self.set_new2.get()
        if not old or not new:
            self.pass_msg.config(text='Isi password lama dan baru.', foreground=RED)
            return
        if new != new2:
            self.pass_msg.config(text='Password baru tidak sama.', foreground=RED)
            return
        row = self.dbs.user_by_username(self.user['username'])
        if not row or row['passHash'] != hash_pass(old):
            self.pass_msg.config(text='Password lama salah.', foreground=RED)
            return
        row['passHash'] = hash_pass(new)
        self.dbs.user_save(row, row['id'])
        self.set_old.delete(0, 'end')
        self.set_new.delete(0, 'end')
        self.set_new2.delete(0, 'end')
        self.pass_msg.config(text='Password berhasil diganti.', foreground=GREEN)

    def _user_add(self):
        if not self.is_admin():
            messagebox.showwarning('Akun', 'Hanya admin.')
            return
        win, body = self._modal('Tambah Akun', h=380, w=420)
        e_u = self.entry_row(body, 'Username *', '')
        e_n = self.entry_row(body, 'Nama', '')
        cb_r = self.combo_row(body, 'Role', ['crew', 'admin'], 'crew')
        e_p = self.entry_row(body, 'Password *', '', password=True)

        def save():
            u = e_u.get().strip().lower()
            if not u or not e_p.get():
                messagebox.showwarning('Akun', 'Username & password wajib.', parent=win)
                return
            if self.dbs.user_by_username(u):
                messagebox.showwarning('Akun', 'Username sudah dipakai.', parent=win)
                return
            self.dbs.user_save({'username': u, 'passHash': hash_pass(e_p.get()),
                                'name': e_n.get().strip() or u, 'role': cb_r.get()})
            win.destroy()
            self._refresh_set()

        ttk.Button(body, text='SIMPAN', style='Gold.TButton', command=save).pack(
            fill='x', pady=12)

    def _user_reset(self):
        if not self.is_admin():
            messagebox.showwarning('Akun', 'Hanya admin.')
            return
        sel = self.user_tree.selection()
        if not sel:
            return
        u = self.dbs._row('SELECT * FROM users WHERE id=?', (int(sel[0]),))
        if u and messagebox.askyesno('Reset', 'Reset password "%s" ke password awal?' % u['username']):
            u['passHash'] = _DEFAULT_ADMIN_HASH
            self.dbs.user_save(u, u['id'])
            self._refresh_set()

    def _user_del(self):
        if not self.is_admin():
            messagebox.showwarning('Akun', 'Hanya admin.')
            return
        sel = self.user_tree.selection()
        if not sel:
            return
        uid = int(sel[0])
        u = self.dbs._row('SELECT * FROM users WHERE id=?', (uid,))
        if u and u['username'] == self.user['username']:
            messagebox.showwarning('Akun', 'Tidak bisa hapus akun sendiri.')
            return
        if messagebox.askyesno('Hapus', 'Hapus akun ini?'):
            self.dbs.user_delete(uid)
            self._refresh_set()

    def _backup(self):
        dst = filedialog.asksaveasfilename(
            defaultextension='.db',
            initialfile='backup-inspirastory-%s.db' % date.today().strftime('%Y%m%d'),
            filetypes=[('Database', '*.db')])
        if dst:
            try:
                shutil.copy2(DB_PATH, dst)
                messagebox.showinfo('Backup', 'Backup tersimpan:\n' + dst)
            except Exception as e:
                messagebox.showerror('Backup', 'Gagal: %s' % e)


# ---------------------------------------------------------------- main
def main():
    root = tk.Tk()
    try:
        root.iconbitmap(default='')
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
