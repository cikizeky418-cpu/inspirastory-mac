# -*- coding: utf-8 -*-
"""Sinkronisasi dua arah antara SQLite lokal dan Firestore via REST API.

Strategi "data terbaru menang":
  1. PULL: unduh semua dokumen remote per koleksi. Bila dokumen belum ada di
     lokal -> sisipkan. Bila ada dan remote.updated_at > lokal.updated_at ->
     timpa lokal.
  2. PUSH: baris lokal berstatus 'dirty' -> PATCH ke remote (atau POST bila
     belum punya fid). Baris 'deleted' -> DELETE remote lalu hapus permanen.

Hanya memakai stdlib (urllib, json).
"""

import json
import socket
import urllib.request
import urllib.parse
import urllib.error

from db import TABLE_FIELDS, TABLE_COLLECTION, now_iso

FIRESTORE_BASE = 'https://firestore.googleapis.com/v1'


def load_config(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _base_url(cfg):
    pid = cfg['projectId']
    return '%s/projects/%s/databases/(default)/documents' % (FIRESTORE_BASE, pid)


def _req(url, method='GET', body=None, timeout=20):
    data = None
    headers = {'Content-Type': 'application/json'}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode('utf-8')
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode('utf-8')[:300]
        except Exception:
            detail = ''
        raise RuntimeError('HTTP %s: %s' % (e.code, detail))


def is_online(timeout=8):
    """Cek koneksi internet + keterjangkauan Firestore."""
    try:
        url = 'https://firestore.googleapis.com/v1?key=x'
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        # fallback: cek DNS/connectivity umum
        try:
            socket.create_connection(('8.8.8.8', 53), timeout=timeout)
            return True
        except Exception:
            return False


# ---------- Firestore value encoding ----------
def _enc_value(v):
    if v is None:
        return {'nullValue': None}
    if isinstance(v, bool):
        return {'booleanValue': v}
    if isinstance(v, int):
        return {'integerValue': str(v)}
    if isinstance(v, float):
        return {'doubleValue': v}
    if isinstance(v, str):
        # coba kenali angka yang tersimpan sebagai string? Tidak: biarkan string.
        return {'stringValue': v}
    if isinstance(v, list):
        return {'arrayValue': {'values': [_enc_value(x) for x in v]}}
    if isinstance(v, dict):
        return {'mapValue': {'fields': {k: _enc_value(x) for k, x in v.items()}}}
    return {'stringValue': str(v)}


def _dec_value(fv):
    if not isinstance(fv, dict) or len(fv) != 1:
        return ''
    (t, v), = fv.items()
    if t == 'stringValue':
        return v
    if t == 'integerValue':
        try:
            return int(v)
        except Exception:
            return 0
    if t == 'doubleValue':
        try:
            return float(v)
        except Exception:
            return 0.0
    if t == 'booleanValue':
        return bool(v)
    if t == 'nullValue':
        return ''
    if t == 'arrayValue':
        return [_dec_value(x) for x in (v.get('values') or [])]
    if t == 'mapValue':
        return {k: _dec_value(x) for k, x in (v.get('fields') or {}).items()}
    if t == 'timestampValue':
        return v
    return v


def doc_to_fields(doc):
    """Ubah dokumen Firestore REST -> dict field datar."""
    fields = {}
    for k, fv in (doc.get('fields') or {}).items():
        fields[k] = _dec_value(fv)
    return fields


def doc_id_from_name(name):
    # name: projects/.../documents/<collection>/<docId>
    return name.rsplit('/', 1)[-1]


def _coerce_for_table(table, fields):
    """Samakan tipe dengan skema lokal (items -> JSON string)."""
    out = dict(fields)
    if table == 'customers' and isinstance(out.get('items'), list):
        out['items'] = json.dumps(out['items'], ensure_ascii=False)
    return out


# ---------- operasi remote ----------
def list_remote(collection, cfg, page_size=300):
    url = '%s/%s?pageSize=%d&key=%s' % (
        _base_url(cfg), collection, page_size, urllib.parse.quote(cfg['apiKey']))
    docs = []
    while True:
        res = _req(url)
        docs.extend(res.get('documents', []))
        token = res.get('nextPageToken')
        if not token:
            break
        url = '%s/%s?pageSize=%d&pageToken=%s&key=%s' % (
            _base_url(cfg), collection, page_size,
            urllib.parse.quote(token), urllib.parse.quote(cfg['apiKey']))
    return docs


def create_remote(collection, cfg, fields):
    url = '%s/%s?key=%s' % (_base_url(cfg), collection, urllib.parse.quote(cfg['apiKey']))
    body = {'fields': {k: _enc_value(v) for k, v in fields.items()}}
    res = _req(url, method='POST', body=body)
    return doc_id_from_name(res.get('name', ''))


def update_remote(collection, cfg, doc_id, fields):
    url = '%s/%s/%s?key=%s&%s' % (
        _base_url(cfg), collection, urllib.parse.quote(doc_id, safe=''),
        urllib.parse.quote(cfg['apiKey']),
        '&'.join('updateMask.fieldPaths=%s' % urllib.parse.quote(k, safe='') for k in fields))
    body = {'fields': {k: _enc_value(v) for k, v in fields.items()}}
    _req(url, method='PATCH', body=body)


def delete_remote(collection, cfg, doc_id):
    url = '%s/%s/%s?key=%s' % (
        _base_url(cfg), collection, urllib.parse.quote(doc_id, safe=''),
        urllib.parse.quote(cfg['apiKey']))
    try:
        _req(url, method='DELETE')
    except RuntimeError as e:
        if 'HTTP 404' not in str(e):
            raise


# ---------- sinkronisasi ----------
def sync_table(dbs, cfg, table, log=None):
    """Sinkron satu tabel. Kembalikan dict statistik."""
    collection = TABLE_COLLECTION[table]
    cols = TABLE_FIELDS[table]
    stat = {'pulled': 0, 'pushed': 0, 'deleted': 0, 'skipped': 0}

    def _log(msg):
        if log:
            log(msg)

    # 1) PULL
    try:
        docs = list_remote(collection, cfg)
    except Exception as e:
        _log('[%s] pull gagal: %s' % (collection, e))
        return stat
    for doc in docs:
        fid = doc_id_from_name(doc.get('name', ''))
        fields = _coerce_for_table(table, doc_to_fields(doc))
        remote_updated = str(fields.get('updated_at') or '')
        # hanya ambil kolom yang dikenal skema
        clean = {c: fields.get(c, '') for c in cols}
        # normalisasi angka
        for c in cols:
            if c in ('totalHarga', 'dpDibayar', 'jumlah', 'harga', 'target', 'progress'):
                try:
                    clean[c] = float(clean[c] or 0)
                except Exception:
                    clean[c] = 0
        res = dbs.upsert_remote(table, fid, clean, remote_updated)
        if res == 'skip':
            stat['skipped'] += 1
        else:
            stat['pulled'] += 1

    # 2) PUSH
    for row in dbs.dirty_rows(table):
        try:
            if row['sync_status'] == 'deleted':
                if row['fid']:
                    delete_remote(collection, cfg, row['fid'])
                dbs.purge_deleted(table, row['id'])
                stat['deleted'] += 1
                continue
            payload = {c: row.get(c, '') for c in cols}
            payload['updated_at'] = row.get('updated_at') or now_iso()
            if row['fid']:
                update_remote(collection, cfg, row['fid'], payload)
                dbs.mark_synced(table, row['id'])
            else:
                new_fid = create_remote(collection, cfg, payload)
                dbs.mark_synced(table, row['id'], new_fid)
            stat['pushed'] += 1
        except Exception as e:
            _log('[%s] push id=%s gagal: %s' % (collection, row['id'], e))
    return stat


def sync_all(dbs, cfg, log=None):
    """Sinkron semua tabel. Kembalikan (ok, ringkasan)."""
    total = {'pulled': 0, 'pushed': 0, 'deleted': 0, 'skipped': 0}
    for table in TABLE_FIELDS:
        if log:
            log('Sinkron %s ...' % TABLE_COLLECTION[table])
        s = sync_table(dbs, cfg, table, log=log)
        for k in total:
            total[k] += s[k]
    return True, total
