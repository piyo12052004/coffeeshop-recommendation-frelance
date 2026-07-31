from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import mysql.connector
import time

conn = mysql.connector.connect(
    # host='localhost',
    # user='root',
    # password='',
    # database='coffeeshop_project'
    # production
    host="mysql-aset",
    user="root",
    password="root123",
    database="coffeeshop_project"
)
cursor = conn.cursor()

cursor.execute("SELECT id, nama, instagram FROM coffeeshops WHERE image_url IS NULL AND instagram IS NOT NULL AND instagram != 'Tidak tersedia'")
shops = cursor.fetchall()
print(f"Total coffee shop dengan Instagram: {len(shops)}")

def buat_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_argument('--lang=en')
    options.add_argument('--no-sandbox')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

driver = buat_driver()

for shop in shops:
    shop_id, nama, ig_link = shop
    try:
        print(f"Scraping: {nama}...")

        ig_link = ig_link.strip().rstrip('/')
        if not ig_link.startswith('http'):
            ig_link = 'https://' + ig_link

        # Pastikan hanya 1 tab, tutup tab ekstra
        try:
            while len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
                driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass

        driver.get(ig_link)
        time.sleep(3)

        # Tutup popup login kalau muncul
        try:
            close_btn = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Close"]')
            close_btn.click()
            time.sleep(1)
        except:
            pass

        img_url = None
        all_imgs = driver.find_elements(By.TAG_NAME, 'img')
        for img in all_imgs:
            src = img.get_attribute('src') or ''
            alt = img.get_attribute('alt') or ''
            if ('cdninstagram' in src or 'fbcdn' in src):
                if "profile picture" in alt.lower() or "foto profil" in alt.lower():
                    img_url = src
                    break

        if not img_url:
            for img in all_imgs:
                src = img.get_attribute('src') or ''
                if ('cdninstagram' in src or 'fbcdn' in src) and len(src) > 50:
                    img_url = src
                    break

        if img_url:
            cursor.execute("UPDATE coffeeshops SET image_url = %s WHERE id = %s", (img_url, shop_id))
            conn.commit()
            print(f"  Berhasil: {img_url[:70]}...")
        else:
            print(f"  Tidak ditemukan: {nama}")

    except Exception as e:
        print(f"  Error: {nama}: {e}")
        # Restart browser kalau crash
        try:
            driver.quit()
        except:
            pass
        print("  Restart browser...")
        time.sleep(2)
        driver = buat_driver()

    time.sleep(2)

try:
    driver.quit()
except:
    pass
cursor.close()
conn.close()
print("Selesai!")