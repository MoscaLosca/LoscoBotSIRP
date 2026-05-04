from imap_tools import MailBox, AND
import re
from playwright.sync_api import sync_playwright, expect
import time
from datetime import datetime

EMAIL = input("Inserisci la tua mail: ")
APP_PASSWORD = input("Inserisci la APP password: ")
IMAP_SERVER = "imap.gmail.com"
SUBJECT = "Conferma la tua presenza"

def UrlAndPinExtractionFromEmail():
    url = None
    student_pin = None
    link_filter = "https://sirp.regione.puglia.it/gradebook/confirm-entries/"
    regex_link = r'https://sirp\.regione\.puglia\.it/gradebook/confirm-entries/[^\s"<>]+'
    with MailBox(IMAP_SERVER).login(EMAIL, APP_PASSWORD) as mailbox:
        i = 0
        for mail in mailbox.fetch(AND(seen=False, subject=SUBJECT)):
            i = i+1
            text = mail.text
            if link_filter in text:
                print("Link trovato nell'email, estrazione...")
                link = re.search(regex_link, text)
                if link:
                    url = link.group(0)
                    print("Link estratto: "+url)
                else:
                    print("Errore nella estrazione del link!")
                
                index1 = text.find("[")
                index2 = text.find("]")
                student_pin = text[index1+1:index2]
                print("pin studente estratto: "+student_pin)
            else:
                print("Link non presente nell'email!")
    if i == 0: print("Nessuna mail corrispondente trovata!")
    return url, student_pin

def LessonConfirmation(url, student_pin):
    if url != None and student_pin != None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
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
            datetime_now = datetime.now().strftime('%d-%m-%Y_%H:%M:%S')
            page.screenshot(path=f"Conferma_{datetime_now}.png")
            print("Screenshot salvato")
            browser.close()
    else:
        print("Conferma della presenza non effettuata!")

if __name__ == "__main__":
    print("Bot avviato, controllo ogni 30 secondi...")
    while True:
        print("\n--- Controllo email ---")
        url, student_pin = UrlAndPinExtractionFromEmail()
        LessonConfirmation(url, student_pin)
        print("Prossimo controllo tra 30 secondi...")
        time.sleep(30)
