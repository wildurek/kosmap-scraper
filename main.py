import time
import requests
from bs4 import BeautifulSoup
import os

LOGIN_URL = "https://adam-chromy.cz/kosmap/uzivatel/login.php"
AUTOMODUL_URL = "https://adam-chromy.cz/kosmap/automodul/index.php"

USERNAME = os.getenv("KOSMAP_USER")
PASSWORD = os.getenv("KOSMAP_PASS")
NTFY_TOPIC = os.getenv("NTFY_TOPIC")

CHECK_INTERVAL_MINUTES = 15

previous_state = {}


def send_notify(text):
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=text.encode("utf-8")
    )


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

    if not previous_state:
        previous_state = current
        return

    for event in current:
        if event not in previous_state:
            continue

        old = previous_state[event]
        new = current[event]

        if old != new:
            send_notify(f"V akci {event} je nové auto nebo volné místo.")

    previous_state = current


if __name__ == "__main__":
    while True:
        try:
            check_changes()
        except Exception as e:
            send_notify(f"KOSMAP CHYBA: {str(e)}")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)
