# InspiraStory — Aplikasi Manajemen Studio (macOS)

Aplikasi desktop manajemen studio wedding & foto untuk brand **InspiraStory**,
port macOS dari aplikasi BR Studio PC. Berjalan online & offline.

## Cara menjalankan (2 langkah)

1. Install Python 3 dari https://www.python.org/downloads/ (macOS)
2. Buka Terminal di folder ini, jalankan:
   ```
   python3 app.py
   ```
   Tidak perlu install tambahan apa pun (hanya Python standar).

**Atau pakai versi jadi:** download `InspiraStory.dmg` dari halaman
[Releases](../../releases) → buka → seret ke Applications → klik kanan
**Open** saat pertama kali dibuka (aplikasi belum ditandatangani Apple —
ini normal untuk aplikasi indie).

Login pertama: username `admin` + password awal (diberikan terpisah).
**Segera ganti password di menu Pengaturan.**

## Cara kerja online / offline

- Data tersimpan lokal di `~/Library/Application Support/InspiraStory/inspirastory.db`
  (dibuat otomatis).
- Tanpa internet: semua fitur jalan normal dari data lokal.
- Ada internet: tekan tombol **Sinkronisasi** (pojok kanan atas) untuk
  menyamakan data dengan database cloud (koleksi Firestore `ins_*`).
- Indikator ONLINE (hijau) / OFFLINE (merah) tampil di atas.

## Fitur

- **Dashboard**: omzet bulan ini, pengeluaran, laba, jumlah customer,
  jadwal hari ini, deadline aktif, progress target.
- **Customer**: tambah customer, pilih banyak layanan, total otomatis,
  DP, sisa otomatis (LUNAS/belum). DP otomatis masuk Pemasukan.
- **Pemasukan & Pengeluaran**: catat manual + otomatis dari DP.
- **Jadwal Foto**: tanggal, jam, customer, jenis, lokasi, crew.
- **Deadline Edit**: daftar project + tandai selesai.
- **Cetak Foto**: ukuran 8R–24RP (harga otomatis), jumlah, DP.
- **Laporan**: rekap bulanan + simpan sebagai file .txt.
- **Target**: target omzet bulanan & tahunan + progress bar.
- **Pengaturan**: ganti password, kelola akun, backup database.

## Backup

Menu Pengaturan → Backup Database. File `.db` juga bisa dicopy manual
sebagai cadangan.

## Build .dmg (otomatis via GitHub Actions)

Setiap push ke branch `main` (atau via tombol Run workflow) memicu build
di runner macOS (ARM64): PyInstaller → `.app` → `.dmg` → GitHub Release.
Lihat `.github/workflows/build-macos.yml`.

## Keamanan

- Password tersimpan sebagai hash SHA-256 (salt `ins_*`).
- `firebase_config.json` berisi API key publik Firebase (bukan rahasia);
  keamanan data dijaga oleh Firestore Rules di koleksi `ins_*`.
