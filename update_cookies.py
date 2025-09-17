from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os

# Path to save cookies
COOKIES_FILE = os.path.join("cookies", "cookies.txt")

# Headless Chrome setup
options = Options()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

# Optional: Use a dedicated Chrome profile where you're logged into YouTube
# options.add_argument("--user-data-dir=/home/ubuntu/chrome-profile")

driver = webdriver.Chrome(options=options)

try:
    # Open YouTube in a fresh session
    driver.get("https://www.youtube.com/robots.txt")

    # Export cookies
    cookies = driver.get_cookies()

    with open(COOKIES_FILE, "w") as f:
        for c in cookies:
            f.write(
                f"{c['domain']}\t"
                f"{'TRUE' if c.get('secure', False) else 'FALSE'}\t"
                f"{c.get('path', '/')}\t"
                f"{'TRUE' if c.get('secure', False) else 'FALSE'}\t"
                f"{c.get('expiry', 0)}\t"
                f"{c['name']}\t{c['value']}\n"
            )
    print(f"[+] Cookies updated at {COOKIES_FILE}")

finally:
    driver.quit()
