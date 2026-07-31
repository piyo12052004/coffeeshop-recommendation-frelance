from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

options = webdriver.ChromeOptions()
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option('excludeSwitches', ['enable-automation'])
options.add_argument('--lang=en')
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

driver.get("https://www.bing.com/images/search?q=cafe+kissimmee+bekasi")
time.sleep(4)

all_imgs = driver.find_elements(By.TAG_NAME, 'img')
print(f"Total img ditemukan: {len(all_imgs)}")
for i, img in enumerate(all_imgs[:15]):
    src = img.get_attribute('src') or ''
    cls = img.get_attribute('class') or ''
    if src:
        print(f"  [{i}] class='{cls[:50]}' src='{src[:80]}'")

driver.quit()