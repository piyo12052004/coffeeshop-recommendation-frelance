import requests
import mysql.connector
import os
import time
from urllib.parse import urlparse

# Koneksi database
conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='',
    database='coffeeshop_project'
)
cursor = conn.cursor()

# Buat folder kalau belum ada
os.makedirs('static/images/coffeeshops', exist_ok=True)

# Ambil semua yang image_url-nya ada (dari Instagram CDN)
cursor.execute("SELECT id, nama, image_url FROM coffeeshops WHERE image_url IS NOT NULL AND image_url NOT LIKE '/static/%'")
shops = cursor.fetchall()
print(f"Total foto yang akan didownload: {len(shops)}")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

for shop in shops:
    shop_id, nama, img_url = shop
    try:
        print(f"Downloading: {nama}...")
        
        res = requests.get(img_url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            # Simpan dengan nama file berdasarkan ID
            ext = '.jpg'
            filename = f"static/images/coffeeshops/{shop_id}{ext}"
            
            with open(filename, 'wb') as f:
                f.write(res.content)
            
            # Update database dengan path lokal
            local_path = f"/static/images/coffeeshops/{shop_id}{ext}"
            cursor.execute("UPDATE coffeeshops SET image_url = %s WHERE id = %s", (local_path, shop_id))
            conn.commit()
            print(f"  Berhasil disimpan: {local_path}")
        else:
            print(f"  Gagal download {nama}: HTTP {res.status_code}")
    
    except Exception as e:
        print(f"  Error {nama}: {e}")
    
    time.sleep(0.5)

cursor.close()
conn.close()
print("\nSelesai! Semua foto sudah disimpan lokal.")