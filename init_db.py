import mysql.connector

# Koneksi ke MySQL XAMPP
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password=""
)
cursor = conn.cursor()

# Buat & Pilih Database
cursor.execute("CREATE DATABASE IF NOT EXISTS crawlingdata_db")
cursor.execute("USE crawlingdata_db")

# Buat Tabel kaunter
cursor.execute("""
    CREATE TABLE IF NOT EXISTS kaunter (
        kaunter INT PRIMARY KEY
    )
""")

# Isi nilai awal kaunter = 0 jika masih kosong
cursor.execute("""
    INSERT INTO kaunter (kaunter) 
    SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM kaunter)
""")

# Buat Tabel twitter
cursor.execute("""
    CREATE TABLE IF NOT EXISTS twitter (
        id INT AUTO_INCREMENT PRIMARY KEY,
        time_slot INT,
        keyword VARCHAR(255),
        username VARCHAR(255),
        waktu VARCHAR(255),
        isi_twit TEXT,
        processed_text TEXT
    )
""")

# Tambahkan kolom saat tabel twitter sudah dibuat sebelumnya.
for column, definition in (
    ('keyword', 'VARCHAR(255)'),
    ('username', 'VARCHAR(255)'),
):
    try:
        cursor.execute(f"ALTER TABLE twitter ADD COLUMN {column} {definition}")
    except mysql.connector.Error as err:
        if err.errno != 1060:
            raise

# Buat Tabel tweets untuk app.py
cursor.execute("""
    CREATE TABLE IF NOT EXISTS tweets (
        id INT AUTO_INCREMENT PRIMARY KEY,
        keyword VARCHAR(255),
        username VARCHAR(255),
        tweet_text TEXT,
        created_at VARCHAR(255),
        processed_text TEXT
    )
""")

conn.commit()
cursor.close()
conn.close()

print("Berhasil! Database & Tabel 'crawlingdata_db' sudah dibuat dan siap dipakai.")