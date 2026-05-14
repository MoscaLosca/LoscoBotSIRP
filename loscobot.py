from imap_tools import MailBox, AND
import re
from playwright.sync_api import sync_playwright, expect
import time
from datetime import datetime

EMAIL = input("Inserisci la tua mail: ")
APP_PASSWORD = input("Inserisci la APP password: ")
IMAP_SERVER = "imap.gmail.com"
SUBJECT = "Conferma la tua presenza"

def url_and_pin_extraction_from_email():
    url = None
    student_pin = None
    regex_link = r'https://sirp\.regione\.puglia\.it/gradebook/confirm-entries/[^\s"<>]+'
    try:
        with MailBox(IMAP_SERVER).login(EMAIL, APP_PASSWORD) as mailbox:
            for mail in mailbox.fetch(AND(seen=False, subject=SUBJECT)):
                print("Email con oggetto '"+SUBJECT+"' trovata! Cerco il link...")
                text = mail.text
                link = re.search(regex_link, text)
                if link:
                    print("Link trovato! Estrazione url e pin...")
                    url = link.group(0)
                    print("Link estratto: "+url)
                    pin_match = re.search(r'\[(\d+)\]', text)
                    if pin_match:
                        student_pin = pin_match.group(1)
                        print("Pin studente estratto: "+student_pin)
                    else:
                        print("Errore nella estrazione del pin")
                        print("!! Conferma non effettuata!")
                else:
                    print("Link non trovato nel testo dell'email!")
                    print("!! Conferma non effettuata!")
    except Exception as e:
        print(f"!! Errore durante il controllo della mail: {e}")
        print("!! Conferma non effettuata!")
    return url, student_pin

def lesson_confirmation(url, student_pin):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url)
            page.wait_for_load_state("networkidle")

            lesson_code = page.locator("h5.mt-0.font-normal").inner_text()
            lesson_code = lesson_code.split("Codice Lezione: ")[1].strip()
            print(f"Codice lezione estratto: {lesson_code}\nProcedo con la conferma...")

            page.get_by_role("button", name="Conferma orari").click()
            page.wait_for_load_state("networkidle")

            page.locator("#pin-field-value").fill(student_pin)
            page.locator("#lesson-code-field-value").fill(lesson_code)

            button = page.locator("button[type='submit']")
            expect(button).to_be_enabled(timeout=10000)
            button.click()

            page.wait_for_load_state("networkidle")
            time.sleep(2)
            datetime_now = datetime.now().strftime('%dd%mm%Yy_%Hh%Mm%Ss')
            screenshot_path = f"Conferma_{datetime_now}.png"
            page.screenshot(path=screenshot_path)
            print("Screenshot salvato")
        except Exception as e:
            print(f"!! Errore durante la conferma della lezione: {e}")
            print("!! Conferma non effettuata!")
        finally:
            browser.close()

if __name__ == "__main__":
    print("Bot avviato, controllo mail in silenzio ogni 45 secondi...\n")
    while True:
        url, student_pin = url_and_pin_extraction_from_email()
        if (url != None and student_pin != None):
            lesson_confirmation(url, student_pin)
        time.sleep(45)