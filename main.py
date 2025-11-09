import time
import requests
from bs4 import BeautifulSoup
import os
import re

LOGIN_URL = "https://adam-chromy.cz/kosmap/uzivatel/login.php"
AUTOMODUL_URL = "https://adam-chromy.cz/kosmap/automodul/index.php"
MY_EVENTS_URL = "https://adam-chromy.cz/kosmap/uzivatel/index.php"

USERNAME = os.getenv("KOSMAP_USER")
PASSWORD = os.getenv("KOSMAP_PASS")
NTFY_TOPIC = os.getenv("NTFY_TOPIC")

MY_NAME = "Doušek Vilém"
CHECK_INTERVAL_SECONDS = 15   # TEST INTERVAL — later change to 300–900

previous_state = {}
previous_my_events = set()


def send_notify(text):
    requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=text.encode("utf-8"))


def extract_event_id(url):
    m = re.search(r"ID=(\d+)", url)
    return m.group(1) if m else None


def login_session():
    session = requests.Session()

    # STEP 1 → establish cookie
    session.get(LOGIN_URL)

    # STEP 2 → correct form fields + user-agent
    headers = {"User-Agent": "Mozilla/5.0"}
    session.post(
        LOGIN_URL,
        data={
            "action": "login",
            "user_login": USERNAME,       # << correct
            "user_password": PASSWORD     # << correct
        },
        headers=headers
    )

    # STEP 3 → verify login success
    check = session.get(MY_EVENTS_URL)
    if MY_NAME not in check.text:
        send_notify("CHYBA: Nepovedlo se přihlásit na KosMap (špatný login nebo session).")
        print("LOGIN FAILED")
    else:
        print("LOGIN OK")

    return session


def fetch_my_registered_events(session):
    r = session.get(MY_EVENTS_URL)
    soup = BeautifulSoup(r.text, "lxml")
    events = set()

    for link in soup.find_all("a"):
        href = link.get("href", "")
        if "treninky-detail" in href:
            event_id = extract_event_id(href)
            if event_id:
                events.add(event_id)
    return events


def fetch_autodata(session):
    r = session.get(AUTOMODUL_URL)
    soup = BeautifulSoup(r.text, "lxml")
    tables = soup.find_all("table")

    results = {}
    for table in tables:
        header = table.find("a")
        if not header:
            continue

        event_id = extract_event_id(header.get("href", ""))
        if not event_id:
            continue

        rows = table.find_all("tr")[1:]
        cars = []

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            driver = cols[0].get_text(strip=True)
            passengers = [x.get_text(strip=True) for x in row.find_all("span")]
            seats = cols[2].get_text(strip=True)

            cars.append((driver, passengers, seats))

        results[event_id] = cars

    return results


def check_changes():
    global previous_state, previous_my_events

    session = login_session()
    my_events = fetch_my_registered_events(session)
    current = fetch_autodata(session)

    print("MY_EVENTS:", my_events)
    print("CURRENT_AUTOMODUL:", list(current.keys()))

    if not previous_state:
        previous_state = current
        previous_my_events = my_events
        send_notify("TEST: Kosmap hlídání běží správně.")
        return

    new = my_events - previous_my_events
    for event_id in new:
        send_notify(f"Přihlásil ses na akci (ID={event_id}).")

    previous_my_events = my_events

    for event_id, cars in current.items():
        if event_id not in my_events:
            continue

        im_in_car = any(
            MY_NAME == d or MY_NAME in p
            for d, p, s in cars
        )
        if im_in_car:
            continue

        free_exists = any("volné" in s.lower() for d, p, s in cars)
        if not free_exists:
            continue

        if previous_state.get(event_id) != cars:
            send_notify(f"V akci (ID={event_id}) je volné místo nebo nové auto!")

    previous_state = current


if __name__ == "__main__":
    while True:
        try:
            check_changes()
        except Exception as e:
            send_notify(f"KOSMAP CHYBA: {str(e)}")
        time.sleep(CHECK_INTERVAL_SECONDS)
