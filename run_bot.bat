@echo off
echo ==========================================
echo Menyiapkan Lingkungan Virtual (venv) Bot...
echo ==========================================

:: Cek apakah venv sudah ada, jika belum buat baru
if not exist .venv (
    echo Membuat virtual environment .venv...
    python -m venv .venv
)

:: Aktifkan venv
echo Mengaktifkan virtual environment...
call .venv\Scripts\activate

:: Instal dependensi dari requirements.txt
echo Menginstal dependensi dari requirements.txt...
pip install -r requirements.txt

:: Instal Playwright browsers
echo.
echo Menginstal Playwright browsers...
playwright install chromium

echo.
echo ==========================================
echo Menjalankan Script Bot...
echo ==========================================
python -u register_canva_tempmail.py

echo.
echo Proses selesai.
pause