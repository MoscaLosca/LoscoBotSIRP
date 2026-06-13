from imap_tools import MailBox, AND
import re
from playwright.sync_api import sync_playwright, expect
import time
from datetime import datetime
import requests
import os
from dotenv import load_dotenv

# Carica le variabili dal file .env
load_dotenv()

# Funzione per controllare le variabili obbligatorie
def check_env_variables():
    required_vars = {
        "EMAIL": os.getenv("EMAIL"),
        "APP_PASSWORD": os.getenv("APP_PASSWORD"),
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID")
    }
    missing = [var for var, value in required_vars.items() if not value]
    if missing:
        print(f"[!] Errore: variabili mancanti nel file .env: {', '.join(missing)}")
        print("Assicurati che il file .env esista nella stessa cartella dello script e contenga:")
        print("EMAIL=...")
        print("APP_PASSWORD=...")
        print("TELEGRAM_BOT_TOKEN=...")
        print("TELEGRAM_CHAT_ID=...")
        return False
    return True

# Variabili di configurazione (con valori di default per quelle opzionali)
EMAIL = os.getenv("EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
SUBJECT = os.getenv("SUBJECT", "Conferma la tua presenza")

def send_telegram_message(text, photo_path=None):
    """Invia un messaggio testuale e opzionalmente una foto su Telegram."""
    try:
        if photo_path:
            with open(photo_path, 'rb') as photo:
                files = {'photo': photo}
                data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': text}
                r = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                    files=files, data=data
                )
        else:
            data = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data=data
            )
        r.raise_for_status()
        print("[Telegram] Messaggio inviato.")
    except Exception as e:
        print(f"[!] Errore nell'invio del messaggio Telegram: {e}")

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
                        print("[!] Conferma non effettuata!")
                else:
                    print("Link non trovato nel testo dell'email!")
                    print("[!] Conferma non effettuata!")
    except Exception as e:
        print(f"[!] Errore durante il controllo della mail: {e}")
        print("[!] Conferma non effettuata!")
    return url, student_pin

def check_confirmation_status(page):
    try:
        notification = page.wait_for_selector(".alert, .toast, [role='alert']", timeout=5000)
        if notification:
            text = notification.inner_text().lower()
            class_attr = notification.get_attribute("class") or ""

            # Controlla prima gli errori
            if "danger" in class_attr or "error" in class_attr or "errore" in text or "400" in text or "non è stata" in text:
                return False, notification.inner_text()

            # Solo dopo controlla il successo
            if "success" in class_attr or any(word in text for word in ["successo", "ok"]):
                return True, notification.inner_text()

            return False, notification.inner_text()
        else:
            return False, "Nessuna notifica rilevata, esito sconosciuto"
    except Exception as e:
        return False, f"Errore nel controllo della notifica: {e}"

def lesson_confirmation(url, student_pin):
    screenshot_path = None
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

            success, notification_msg = check_confirmation_status(page)

            datetime_now = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_path = f"Conferma_{datetime_now}.png"
            page.screenshot(path=screenshot_path)
            print("[V] Screenshot salvato")

            if success:
                msg = f"Conferma effettuata con successo\nNotifica: {notification_msg}"
                print("[V] "+msg)
                send_telegram_message("✅ "+msg, screenshot_path)
            else:
                msg = f"Errore nella conferma\nMotivo: {notification_msg}"
                print("[!] "+msg)
                send_telegram_message("❌ "+msg, screenshot_path)

            return success, screenshot_path

        except Exception as e:
            error_msg = f"Errore durante la conferma della lezione: {e}"
            print("[!] "+error_msg)
            try:
                screenshot_path = f"Errore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=screenshot_path)
                send_telegram_message("❌ "+error_msg, screenshot_path)
            except:
                send_telegram_message("❌ "+error_msg)
            return False, screenshot_path

        finally:
            browser.close()

if __name__ == "__main__":
    # Controllo variabili d'ambiente prima di partire
    if not check_env_variables():
        exit(1)

    print("Script avviato, controllo mail ogni 100 secondi...\n")
    send_telegram_message("Bot avviato - Inizio monitoraggio email")

    while True:
        url, student_pin = url_and_pin_extraction_from_email()
        if url and student_pin:
            lesson_confirmation(url, student_pin)
        time.sleep(100)