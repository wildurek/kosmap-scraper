import time
import requests
from bs4 import BeautifulSoup
import os

LOGIN_URL = "https://adam-chromy.cz/kosmap/uzivatel/login.php"
AUTOMODUL_URL = "https://adam-chromy.cz/kosmap/automodul/index.php"
MY_EVENTS_URL = "https://adam-chromy.cz/kosmap/uzivatel/index.php"

USERNAME = os.getenv("KOSMAP_USER")
PASSWORD = os.getenv("KOSMAP_PASS")
NTFY_TOPIC = os.getenv("NTFY_TOPIC")

MY_NAME = "Doušek Vilém"     # <<< tvoje jméno přesně jako v Kosmapu
CHECK_INTERVAL_MINUTES = 15

previous_state = {}
previous_my_events = set()


def send_notify(text):
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=text.encode("utf-8")
    )


def norm(s):
    return " ".join(s.split()).strip().lower()

def fetch_my_registered_events(session):
    r = session.get(MY_EVENTS_URL)
    soup = BeautifulSoup(r.text, "lxml")
    events = set()

    for link in soup.find_all("a"):
        href = link.get("href", "")
        if "treninky-detail" in href:
            event_name = link.get_text(strip=True)
            if event_name:
                events.add(norm(event_name))

    return events


def fetch_autodata(session):
    r = session.get(AUTOMODUL_URL)
    soup = BeautifulSoup(r.text, "lxml")
    tables = soup.find_all("table")

    results = {}

    for table in tables:
        rows = table.find_all("tr")
        if not rows:
            continue

        event_name = rows[0].get_text(strip=True)
        cars = []

        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            driver = cols[0].get_text(strip=True)
            passengers = [x.get_text(strip=True) for x in row.find_all("span")]
            seats = cols[2].get_text(strip=True)

            cars.append((driver, passengers, seats))

        results[norm(event_name)] = cars

    return results


def check_changes():
    global previous_state, previous_my_events

    session = requests.Session()
    session.post(LOGIN_URL, data={"uzivatel": USERNAME, "heslo": PASSWORD})

    my_events = fetch_my_registered_events(session)
    current = fetch_autodata(session)

    # první start → uložíme stav
    if not previous_state:
        previous_state = current
        previous_my_events = my_events
        send_notify("TEST: Kosmap hlídání běží správně.")
        return

    # detekce nového přihlášení na akci
    new_events = {e for e in my_events if e not in previous_my_events}
    for event in new_events:
        send_notify(f"Přihlásil ses na akci: {event}")

    previous_my_events = my_events

    # hlídání aut
    for event, cars in current.items():
        if event not in my_events:
            continue

        # jsi v autě?
        im_in_car = any(
            MY_NAME == driver or MY_NAME in passengers
            for driver, passengers, seats in cars
        )
        if im_in_car:
            continue

        # existuje volné místo?
        free_exists = any("volné" in seats.lower() for driver, passengers, seats in cars)
        if not free_exists:
            continue

        # změna oproti minule → notifikace
        if previous_state.get(event) != cars:
            send_notify(f"V akci {event} je volné místo nebo nové auto!")

    previous_state = current


if __name__ == "__main__":
    while True:
        try:
            check_changes()
        except Exception as e:
            send_notify(f"KOSMAP CHYBA: {str(e)}")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

