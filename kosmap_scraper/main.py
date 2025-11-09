import time
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

LOGIN_URL = "https://adam-chromy.cz/kosmap/uzivatel/login.php"
AUTOMODUL_URL = "https://adam-chromy.cz/kosmap/automodul/index.php"

USERNAME = os.getenv("KOSMAP_USER")
PASSWORD = os.getenv("KOSMAP_PASS")

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

CHECK_INTERVAL_MINUTES = 15

previous_state = {}

def send_email(subject, text):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_APP_PASSWORD)
        server.send_message(msg)

def fetch_autodata():
    session = requests.Session()
    login_data = {"uzivatel": USERNAME, "heslo": PASSWORD}
    session.post(LOGIN_URL, data=login_data)

    r = session.get(AUTOMODUL_URL)
    soup = BeautifulSoup(r.text, "lxml")
    tables = soup.find_all("table")

    results = {}

    for table in tables:
        rows = table.find_all("tr")
        if not rows:
            continue

        event_name = rows[0].get_text(strip=True)
        if not event_name: 
            continue

        cars = []
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            driver = cols[0].get_text(strip=True)
            seats = cols[2].get_text(strip=True)
            cars.append((driver, seats))

        results[event_name] = cars

    return results

def check_changes():
    global previous_state

    current = fetch_autodata()

    # First run: just record state
    if not previous_state:
        previous_state = current
        return

    for event in current:
        if event not in previous_state:
            continue

        old = previous_state[event]
        new = current[event]

        if old != new:
            send_email(
                f"[KOSMAP] Nové auto nebo místo v akci: {event}",
                f"V akci {event} se změnil stav aut nebo míst.\nZkontroluj automodul."
            )

    previous_state = current

if __name__ == "__main__":
    while True:
        try:
            check_changes()
        except Exception as e:
            send_email("[KOSMAP] ERROR", str(e))
        time.sleep(CHECK_INTERVAL_MINUTES * 60)
