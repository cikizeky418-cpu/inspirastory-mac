# -*- coding: utf-8 -*-
"""Lapisan database SQLite lokal untuk InspiraStory (macOS).

Setiap tabel punya kolom:
  id          INTEGER PRIMARY KEY (lokal)
  fid         TEXT UNIQUE (id dokumen Firestore, NULL bila belum tersinkron)
  updated_at  TEXT ISO-8601 (terakhir diubah)
  sync_status TEXT ('synced' | 'dirty' | 'deleted')
"""

import json
import sqlite3
from datetime import datetime


def now_iso():
    return datetime.now().isoformat(timespec='seconds')


def today_iso():
    return datetime.now().strftime('%Y-%m-%d')


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fid TEXT UNIQUE,
    username TEXT UNIQUE NOT NULL,
    passHash TEXT NOT NULL,
    name TEXT DEFAULT '',
    role TEXT DEFAULT 'crew',
    updated_at TEXT DEFAULT '',
    sync_status TEXT DEFAULT 'dirty'
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fid TEXT UNIQUE,
    nama TEXT NOT NULL,
    wa TEXT DEFAULT '',
    alamat TEXT DEFAULT '',
    catatan TEXT DEFAULT '',
    items TEXT DEFAULT '[]',
    totalHarga REAL DEFAULT 0,
    dpDibayar REAL DEFAULT 0,
    tglDp TEXT DEFAULT '',
    jamDp TEXT DEFAULT '',
    createdAt TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    sync_status TEXT DEFAULT 'dirty'
);

CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fid TEXT UNIQUE,
    tanggal TEXT DEFAULT '',
    jam TEXT DEFAULT '',
    customer TEXT DEFAULT '',
    jumlah REAL DEFAULT 0,
    keterangan TEXT DEFAULT '',
    tipe TEXT DEFAULT 'manual',
    customerId TEXT DEFAULT '',
    printId TEXT DEFAULT '',
    createdAt TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    sync_status TEXT DEFAULT 'dirty'
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fid TEXT UNIQUE,
    tanggal TEXT DEFAULT '',
    jam TEXT DEFAULT '',
    kategori TEXT DEFAULT 'lainnya',
    jumlah REAL DEFAULT 0,
    keterangan TEXT DEFAULT '',
    createdAt TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    sync_status TEXT DEFAULT 'dirty'
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fid TEXT UNIQUE,
    tanggal TEXT DEFAULT '',
    jam TEXT DEFAULT '',
    customer TEXT DEFAULT '',
    jenis TEXT DEFAULT 'foto',
    tempat TEXT DEFAULT 'studio',
    crew TEXT DEFAULT '',
    crewWa TEXT DEFAULT '',
    lokasi TEXT DEFAULT '',
    maps TEXT DEFAULT '',
    paket TEXT DEFAULT '',
    attire TEXT DEFAULT '',
    status TEXT DEFAULT 'terjadwal',
    createdAt TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    sync_status TEXT DEFAULT 'dirty'
);

CREATE TABLE IF NOT EXISTS deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fid TEXT UNIQUE,
    project TEXT NOT NULL,
    customer TEXT DEFAULT '',
    deadline TEXT DEFAULT '',
    jam TEXT DEFAULT '',
    status TEXT DEFAULT 'antri',
    progress INTEGER DEFAULT 0,
    createdAt TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    sync_status TEXT DEFAULT 'dirty'
);

CREATE TABLE IF NOT EXISTS prints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fid TEXT UNIQUE,
    tanggal TEXT DEFAULT '',
    jamOrder TEXT DEFAULT '',
    deadline TEXT DEFAULT '',
    jamDeadline TEXT DEFAULT '',
    customer TEXT DEFAULT '',
    ukuran TEXT DEFAULT '',
    jumlah REAL DEFAULT 0,
    harga REAL DEFAULT 0,
    totalHarga REAL DEFAULT 0,
    dpDibayar REAL DEFAULT 0,
    tglDp TEXT DEFAULT '',
    jamDp TEXT DEFAULT '',
    status TEXT DEFAULT 'diproses',
    catatan TEXT DEFAULT '',
    createdAt TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    sync_status TEXT DEFAULT 'dirty'
);

CREATE TABLE IF NOT EXISTS targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fid TEXT UNIQUE,
    bulan TEXT DEFAULT '',
    tahun TEXT DEFAULT '',
    target REAL DEFAULT 0,
    updated_at TEXT DEFAULT '',
    sync_status TEXT DEFAULT 'dirty'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_targets_key ON targets(COALESCE(NULLIF(bulan,''), tahun));
"""

# Kolom data (tanpa id) per tabel, untuk konversi ke/dari Firestore
TABLE_FIELDS = {
    'users':      ['username', 'passHash', 'name', 'role'],
    'customers':  ['nama', 'wa', 'alamat', 'catatan', 'items', 'totalHarga', 'dpDibayar',
                   'tglDp', 'jamDp', 'createdAt'],
    'income':     ['tanggal', 'jam', 'customer', 'jumlah', 'keterangan', 'tipe',
                   'customerId', 'printId', 'createdAt'],
    'expenses':   ['tanggal', 'jam', 'kategori', 'jumlah', 'keterangan', 'createdAt'],
    'schedules':  ['tanggal', 'jam', 'customer', 'jenis', 'tempat', 'crew', 'crewWa',
                   'lokasi', 'maps', 'paket', 'attire', 'status', 'createdAt'],
    'deadlines':  ['project', 'customer', 'deadline', 'jam', 'status', 'progress', 'createdAt'],
    'prints':     ['tanggal', 'jamOrder', 'deadline', 'jamDeadline', 'customer', 'ukuran',
                   'jumlah', 'harga', 'totalHarga', 'dpDibayar', 'tglDp', 'jamDp',
                   'status', 'catatan', 'createdAt'],
    'targets':    ['bulan', 'tahun', 'target'],
}

# Koleksi Firestore untuk tiap tabel
TABLE_COLLECTION = {
    'users': 'ins_users',
    'customers': 'ins_customers',
    'income': 'ins_income',
    'expenses': 'ins_expenses',
    'schedules': 'ins_schedules',
    'deadlines': 'ins_deadlines',
    'prints': 'ins_prints',
    'targets': 'ins_targets',
}


class DB:
    def __init__(self, path):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys = ON')
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ---------- helper generik ----------
    def _row(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        r = cur.fetchone()
        return dict(r) if r else None

    def _all(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def _touch(self, table, rid):
        self.conn.execute(
            "UPDATE %s SET updated_at=?, sync_status='dirty' WHERE id=?" % table,
            (now_iso(), rid))
        self.conn.commit()

    # ---------- users ----------
    def user_by_username(self, username):
        return self._row("SELECT * FROM users WHERE username=? AND sync_status!='deleted'",
                         (username,))

    def user_list(self):
        return self._all("SELECT * FROM users WHERE sync_status!='deleted' ORDER BY username")

    def user_save(self, data, uid=None):
        fields = TABLE_FIELDS['users']
        if uid:
            sets = ", ".join(f + "=?" for f in fields)
            self.conn.execute("UPDATE users SET %s WHERE id=?" % sets,
                              [data.get(f, '') for f in fields] + [uid])
            self._touch('users', uid)
            return uid
        cur = self.conn.execute(
            "INSERT INTO users (%s, updated_at, sync_status) VALUES (%s, ?, 'dirty')" %
            (", ".join(fields), ", ".join(['?'] * len(fields))),
            [data.get(f, '') for f in fields] + [now_iso()])
        self.conn.commit()
        return cur.lastrowid

    def user_delete(self, uid):
        self.conn.execute("UPDATE users SET sync_status='deleted', updated_at=? WHERE id=?",
                          (now_iso(), uid))
        self.conn.commit()

    # ---------- customers ----------
    def customer_list(self, search=''):
        if search:
            q = "%" + search.lower() + "%"
            return self._all(
                "SELECT * FROM customers WHERE sync_status!='deleted' AND "
                "(LOWER(nama) LIKE ? OR LOWER(wa) LIKE ?) ORDER BY nama", (q, q))
        return self._all("SELECT * FROM customers WHERE sync_status!='deleted' ORDER BY nama")

    def customer_get(self, cid):
        return self._row("SELECT * FROM customers WHERE id=?", (cid,))

    def customer_save(self, data, cid=None):
        fields = TABLE_FIELDS['customers']
        vals = [data.get(f, '') for f in fields]
        if cid:
            sets = ", ".join(f + "=?" for f in fields)
            self.conn.execute("UPDATE customers SET %s WHERE id=?" % sets, vals + [cid])
            self._touch('customers', cid)
            return cid
        cur = self.conn.execute(
            "INSERT INTO customers (%s, updated_at, sync_status) VALUES (%s, ?, 'dirty')" %
            (", ".join(fields), ", ".join(['?'] * len(fields))), vals + [now_iso()])
        self.conn.commit()
        return cur.lastrowid

    def customer_delete(self, cid):
        self.conn.execute("UPDATE customers SET sync_status='deleted', updated_at=? WHERE id=?",
                          (now_iso(), cid))
        self.conn.commit()

    def customer_items(self, row):
        try:
            return json.loads(row.get('items') or '[]')
        except Exception:
            return []

    # ---------- income ----------
    def income_list(self, month=None):
        if month:
            return self._all(
                "SELECT * FROM income WHERE sync_status!='deleted' AND substr(tanggal,1,7)=? "
                "ORDER BY tanggal DESC, jam DESC", (month,))
        return self._all("SELECT * FROM income WHERE sync_status!='deleted' "
                         "ORDER BY tanggal DESC, jam DESC LIMIT 500")

    def income_get(self, iid):
        return self._row("SELECT * FROM income WHERE id=?", (iid,))

    def income_save(self, data, iid=None):
        fields = TABLE_FIELDS['income']
        vals = [data.get(f, '') for f in fields]
        if iid:
            sets = ", ".join(f + "=?" for f in fields)
            self.conn.execute("UPDATE income SET %s WHERE id=?" % sets, vals + [iid])
            self._touch('income', iid)
            return iid
        cur = self.conn.execute(
            "INSERT INTO income (%s, updated_at, sync_status) VALUES (%s, ?, 'dirty')" %
            (", ".join(fields), ", ".join(['?'] * len(fields))), vals + [now_iso()])
        self.conn.commit()
        return cur.lastrowid

    def income_delete(self, iid):
        self.conn.execute("UPDATE income SET sync_status='deleted', updated_at=? WHERE id=?",
                          (now_iso(), iid))
        self.conn.commit()

    def income_sum_month(self, month):
        r = self._row("SELECT COALESCE(SUM(jumlah),0) s FROM income "
                      "WHERE sync_status!='deleted' AND substr(tanggal,1,7)=?", (month,))
        return r['s'] if r else 0

    # ---------- expenses ----------
    def expense_list(self, month=None):
        if month:
            return self._all(
                "SELECT * FROM expenses WHERE sync_status!='deleted' AND substr(tanggal,1,7)=? "
                "ORDER BY tanggal DESC, jam DESC", (month,))
        return self._all("SELECT * FROM expenses WHERE sync_status!='deleted' "
                         "ORDER BY tanggal DESC, jam DESC LIMIT 500")

    def expense_get(self, eid):
        return self._row("SELECT * FROM expenses WHERE id=?", (eid,))

    def expense_save(self, data, eid=None):
        fields = TABLE_FIELDS['expenses']
        vals = [data.get(f, '') for f in fields]
        if eid:
            sets = ", ".join(f + "=?" for f in fields)
            self.conn.execute("UPDATE expenses SET %s WHERE id=?" % sets, vals + [eid])
            self._touch('expenses', eid)
            return eid
        cur = self.conn.execute(
            "INSERT INTO expenses (%s, updated_at, sync_status) VALUES (%s, ?, 'dirty')" %
            (", ".join(fields), ", ".join(['?'] * len(fields))), vals + [now_iso()])
        self.conn.commit()
        return cur.lastrowid

    def expense_delete(self, eid):
        self.conn.execute("UPDATE expenses SET sync_status='deleted', updated_at=? WHERE id=?",
                          (now_iso(), eid))
        self.conn.commit()

    def expense_sum_month(self, month):
        r = self._row("SELECT COALESCE(SUM(jumlah),0) s FROM expenses "
                      "WHERE sync_status!='deleted' AND substr(tanggal,1,7)=?", (month,))
        return r['s'] if r else 0

    # ---------- schedules ----------
    def schedule_list(self, upcoming_only=False):
        if upcoming_only:
            return self._all(
                "SELECT * FROM schedules WHERE sync_status!='deleted' AND tanggal>=? "
                "ORDER BY tanggal, jam LIMIT 100", (today_iso(),))
        return self._all("SELECT * FROM schedules WHERE sync_status!='deleted' "
                         "ORDER BY tanggal DESC, jam DESC LIMIT 300")

    def schedule_today(self):
        return self._all("SELECT * FROM schedules WHERE sync_status!='deleted' AND tanggal=? "
                         "ORDER BY jam", (today_iso(),))

    def schedule_get(self, sid):
        return self._row("SELECT * FROM schedules WHERE id=?", (sid,))

    def schedule_save(self, data, sid=None):
        fields = TABLE_FIELDS['schedules']
        vals = [data.get(f, '') for f in fields]
        if sid:
            sets = ", ".join(f + "=?" for f in fields)
            self.conn.execute("UPDATE schedules SET %s WHERE id=?" % sets, vals + [sid])
            self._touch('schedules', sid)
            return sid
        cur = self.conn.execute(
            "INSERT INTO schedules (%s, updated_at, sync_status) VALUES (%s, ?, 'dirty')" %
            (", ".join(fields), ", ".join(['?'] * len(fields))), vals + [now_iso()])
        self.conn.commit()
        return cur.lastrowid

    def schedule_delete(self, sid):
        self.conn.execute("UPDATE schedules SET sync_status='deleted', updated_at=? WHERE id=?",
                          (now_iso(), sid))
        self.conn.commit()

    # ---------- deadlines ----------
    def deadline_list(self, active_only=False):
        if active_only:
            return self._all(
                "SELECT * FROM deadlines WHERE sync_status!='deleted' AND status!='selesai' "
                "ORDER BY deadline, jam LIMIT 100")
        return self._all("SELECT * FROM deadlines WHERE sync_status!='deleted' "
                         "ORDER BY deadline, jam LIMIT 300")

    def deadline_get(self, did):
        return self._row("SELECT * FROM deadlines WHERE id=?", (did,))

    def deadline_save(self, data, did=None):
        fields = TABLE_FIELDS['deadlines']
        vals = [data.get(f, '') for f in fields]
        if did:
            sets = ", ".join(f + "=?" for f in fields)
            self.conn.execute("UPDATE deadlines SET %s WHERE id=?" % sets, vals + [did])
            self._touch('deadlines', did)
            return did
        cur = self.conn.execute(
            "INSERT INTO deadlines (%s, updated_at, sync_status) VALUES (%s, ?, 'dirty')" %
            (", ".join(fields), ", ".join(['?'] * len(fields))), vals + [now_iso()])
        self.conn.commit()
        return cur.lastrowid

    def deadline_delete(self, did):
        self.conn.execute("UPDATE deadlines SET sync_status='deleted', updated_at=? WHERE id=?",
                          (now_iso(), did))
        self.conn.commit()

    # ---------- prints ----------
    def print_list(self, search=''):
        if search:
            q = "%" + search.lower() + "%"
            return self._all(
                "SELECT * FROM prints WHERE sync_status!='deleted' AND "
                "(LOWER(customer) LIKE ? OR LOWER(ukuran) LIKE ?) ORDER BY tanggal DESC",
                (q, q))
        return self._all("SELECT * FROM prints WHERE sync_status!='deleted' "
                         "ORDER BY tanggal DESC LIMIT 300")

    def print_get(self, pid):
        return self._row("SELECT * FROM prints WHERE id=?", (pid,))

    def print_save(self, data, pid=None):
        fields = TABLE_FIELDS['prints']
        vals = [data.get(f, '') for f in fields]
        if pid:
            sets = ", ".join(f + "=?" for f in fields)
            self.conn.execute("UPDATE prints SET %s WHERE id=?" % sets, vals + [pid])
            self._touch('prints', pid)
            return pid
        cur = self.conn.execute(
            "INSERT INTO prints (%s, updated_at, sync_status) VALUES (%s, ?, 'dirty')" %
            (", ".join(fields), ", ".join(['?'] * len(fields))), vals + [now_iso()])
        self.conn.commit()
        return cur.lastrowid

    def print_delete(self, pid):
        self.conn.execute("UPDATE prints SET sync_status='deleted', updated_at=? WHERE id=?",
                          (now_iso(), pid))
        self.conn.commit()

    # ---------- targets ----------
    def target_month_get(self, month):
        return self._row("SELECT * FROM targets WHERE bulan=? AND sync_status!='deleted'",
                         (month,))

    def target_year_get(self, year):
        return self._row("SELECT * FROM targets WHERE tahun=? AND sync_status!='deleted'",
                         (year,))

    def target_save(self, data, tid=None):
        fields = TABLE_FIELDS['targets']
        vals = [data.get(f, '') for f in fields]
        if tid:
            sets = ", ".join(f + "=?" for f in fields)
            self.conn.execute("UPDATE targets SET %s WHERE id=?" % sets, vals + [tid])
            self._touch('targets', tid)
            return tid
        cur = self.conn.execute(
            "INSERT INTO targets (%s, updated_at, sync_status) VALUES (%s, ?, 'dirty')" %
            (", ".join(fields), ", ".join(['?'] * len(fields))), vals + [now_iso()])
        self.conn.commit()
        return cur.lastrowid

    # ---------- sync helpers ----------
    def row_by_fid(self, table, fid):
        return self._row("SELECT * FROM %s WHERE fid=?" % table, (fid,))

    def dirty_rows(self, table):
        return self._all("SELECT * FROM %s WHERE sync_status IN ('dirty','deleted')" % table)

    def mark_synced(self, table, rid, fid=None):
        if fid:
            self.conn.execute("UPDATE %s SET fid=?, sync_status='synced' WHERE id=?" % table,
                              (fid, rid))
        else:
            self.conn.execute("UPDATE %s SET sync_status='synced' WHERE id=?" % table, (rid,))
        self.conn.commit()

    def purge_deleted(self, table, rid):
        self.conn.execute("DELETE FROM %s WHERE id=?" % table, (rid,))
        self.conn.commit()

    def upsert_remote(self, table, fid, fields, remote_updated):
        """Tulis data remote ke lokal bila remote lebih baru (atau belum ada)."""
        local = self.row_by_fid(table, fid)
        cols = TABLE_FIELDS[table]
        if local:
            if (local.get('updated_at') or '') >= (remote_updated or ''):
                return 'skip'
            sets = ", ".join(c + "=?" for c in cols)
            self.conn.execute(
                "UPDATE %s SET %s, updated_at=?, sync_status='synced' WHERE id=?" % (table, sets),
                [fields.get(c, '') for c in cols] + [remote_updated or now_iso(), local['id']])
            self.conn.commit()
            return 'updated'
        self.conn.execute(
            "INSERT INTO %s (fid, %s, updated_at, sync_status) VALUES (?, %s, ?, 'synced')" %
            (table, ", ".join(cols), ", ".join(['?'] * len(cols))),
            [fid] + [fields.get(c, '') for c in cols] + [remote_updated or now_iso()])
        self.conn.commit()
        return 'inserted'

    def count_pending(self):
        total = 0
        for t in TABLE_FIELDS:
            r = self._row("SELECT COUNT(*) c FROM %s WHERE sync_status IN ('dirty','deleted')" % t)
            total += r['c'] if r else 0
        return total
