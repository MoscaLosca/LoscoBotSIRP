#!/usr/bin/env python3
"""
LoscoBot — conferma automatica della presenza a lezione.

Ciclo:
  1. cerca nella casella IMAP le email NON lette con l'oggetto atteso
  2. estrae link e PIN
  3. apre il link con Playwright e conferma
  4. SOLO se la conferma va a buon fine marca l'email come letta
     -> in caso di errore transitorio l'email resta "non letta" e viene
        ritentata al giro successivo (fino a MAX_ATTEMPTS)
  5. cancella gli screenshot più vecchi di SCREENSHOT_RETENTION_DAYS

Variabili .env obbligatorie: EMAIL, APP_PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Opzionali: IMAP_SERVER, SUBJECT, CHECK_INTERVAL, MAX_ATTEMPTS,
           SCREENSHOT_DIR, SCREENSHOT_RETENTION_DAYS
"""

import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from imap_tools import AND, MailBox, MailMessageFlags
from playwright.sync_api import expect, sync_playwright

# --- Configurazione ---------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

EMAIL = os.getenv("EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
SUBJECT = os.getenv("SUBJECT", "Conferma la tua presenza")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "100"))          # secondi
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "5"))                # tentativi per email
SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", SCRIPT_DIR / "screenshots"))
SCREENSHOT_RETENTION_DAYS = int(os.getenv("SCREENSHOT_RETENTION_DAYS", "15"))

REGEX_LINK = re.compile(r"https://sirp\.regione\.puglia\.it/gradebook/confirm-entries/[^\s\"<>]+")
REGEX_PIN = re.compile(r"\[(\d+)\]")
REGEX_LESSON_CODE = re.compile(r"codice\s+lezione\s*:\s*(\S+)", re.I)

# journald aggiunge già il timestamp: qui basta il livello
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)
log = logging.getLogger("loscobot")

# Tentativi per email, in memoria: chiave = UID IMAP
attempts: dict[str, int] = {}


class PermanentError(Exception):
    """Errore che non ha senso ritentare (email malformata, link scaduto...)."""


# --- Utility ----------------------------------------------------------------

def check_env_variables() -> bool:
    required = {
        "EMAIL": EMAIL,
        "APP_PASSWORD": APP_PASSWORD,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        log.error("variabili mancanti nel file .env: %s", ", ".join(missing))
        log.error("Il file .env deve stare in %s e contenere: %s",
                  SCRIPT_DIR, ", ".join(f"{k}=..." for k in required))
        return False
    return True


def send_telegram_message(text: str, photo_path: Path | None = None) -> None:
    """Invia un messaggio testuale e, se disponibile, uno screenshot."""
    base = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    try:
        if photo_path and Path(photo_path).is_file():
            with open(photo_path, "rb") as photo:
                r = requests.post(f"{base}/sendPhoto",
                                  files={"photo": photo},
                                  data={"chat_id": TELEGRAM_CHAT_ID, "caption": text[:1024]},
                                  timeout=30)
        else:
            r = requests.post(f"{base}/sendMessage",
                              data={"chat_id": TELEGRAM_CHAT_ID, "text": text[:4096]},
                              timeout=30)
        r.raise_for_status()
        log.info("[Telegram] messaggio inviato")
    except Exception as e:  # Telegram non deve mai far cadere il bot
        log.warning("[Telegram] invio fallito: %s", e)


def take_screenshot(page, prefix: str) -> Path | None:
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SCREENSHOT_DIR / f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}.png"
        page.screenshot(path=str(path))
        log.info("screenshot salvato: %s", path.name)
        return path
    except Exception as e:
        log.warning("screenshot non salvato: %s", e)
        return None


def cleanup_screenshots() -> None:
    """Elimina gli screenshot più vecchi di SCREENSHOT_RETENTION_DAYS."""
    if not SCREENSHOT_DIR.is_dir():
        return
    cutoff = datetime.now() - timedelta(days=SCREENSHOT_RETENTION_DAYS)
    removed = 0
    for f in SCREENSHOT_DIR.glob("*.png"):
        try:
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
                removed += 1
        except OSError as e:
            log.warning("impossibile cancellare %s: %s", f.name, e)
    if removed:
        log.info("pulizia screenshot: rimossi %d file più vecchi di %d giorni",
                 removed, SCREENSHOT_RETENTION_DAYS)


# --- IMAP -------------------------------------------------------------------

def fetch_pending_emails() -> list[dict]:
    """
    Ritorna le email non lette con l'oggetto atteso, SENZA marcarle come lette.
    Ogni elemento: {"uid", "url", "pin"}; url/pin sono None se non estraibili.
    """
    pending = []
    with MailBox(IMAP_SERVER).login(EMAIL, APP_PASSWORD) as mailbox:
        for mail in mailbox.fetch(AND(seen=False, subject=SUBJECT), mark_seen=False):
            text = mail.text or mail.html or ""
            link = REGEX_LINK.search(text)
            pin = REGEX_PIN.search(text)
            pending.append({
                "uid": mail.uid,
                "url": link.group(0) if link else None,
                "pin": pin.group(1) if pin else None,
            })
    return pending


def mark_as_seen(uid: str) -> None:
    with MailBox(IMAP_SERVER).login(EMAIL, APP_PASSWORD) as mailbox:
        mailbox.flag(uid, MailMessageFlags.SEEN, True)
    log.info("email uid=%s marcata come letta", uid)


# --- Playwright -------------------------------------------------------------

def check_confirmation_status(page) -> tuple[bool, str]:
    try:
        notification = page.wait_for_selector(".alert, .toast, [role='alert']", timeout=5000)
    except Exception:
        return False, "Nessuna notifica rilevata, esito sconosciuto"

    raw = notification.inner_text().strip()
    text = raw.lower()
    cls = (notification.get_attribute("class") or "").lower()

    # Prima gli errori, poi il successo
    if any(k in cls for k in ("danger", "error")) or any(k in text for k in ("errore", "400", "non è stata")):
        return False, raw
    if "success" in cls or any(w in text for w in ("successo", "ok")):
        return True, raw
    return False, raw


def lesson_confirmation(url: str, student_pin: str) -> None:
    """
    Esegue la conferma. Solleva un'eccezione se fallisce:
      - PermanentError  -> non ritentare
      - qualunque altra -> errore transitorio, ritentare al giro dopo
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle")

            # FIX: l'h5 esiste nel DOM prima che il JS lo riempia -> aspettare
            # che contenga davvero il testo invece di leggerlo subito
            header = page.locator("h5.mt-0.font-normal")
            expect(header).to_contain_text(re.compile(r"codice\s+lezione", re.I), timeout=15000)
            header_text = header.inner_text()
            m = REGEX_LESSON_CODE.search(header_text)
            if not m:
                raise PermanentError(f"codice lezione non trovato nell'intestazione: '{header_text}'")
            lesson_code = m.group(1)
            log.info("codice lezione: %s — procedo con la conferma", lesson_code)

            page.get_by_role("button", name="Conferma orari").click()
            page.wait_for_load_state("networkidle")

            page.locator("#pin-field-value").fill(student_pin)
            page.locator("#lesson-code-field-value").fill(lesson_code)

            submit = page.locator("button[type='submit']")
            expect(submit).to_be_enabled(timeout=10000)
            submit.click()
            page.wait_for_load_state("networkidle")
            time.sleep(2)

            success, notification = check_confirmation_status(page)
            shot = take_screenshot(page, "Conferma" if success else "Errore")

            if not success:
                send_telegram_message(f"❌ Conferma rifiutata dal sito\nNotifica: {notification}", shot)
                # Il sito ha risposto ma ha rifiutato: ritentare non cambia nulla
                raise PermanentError(f"conferma rifiutata: {notification}")

            send_telegram_message(f"✅ Conferma effettuata con successo\nNotifica: {notification}", shot)

        except PermanentError:
            raise
        except Exception as e:
            shot = take_screenshot(page, "Errore")
            send_telegram_message(f"⚠️ Errore durante la conferma (riproverò): {e}", shot)
            raise
        finally:
            browser.close()


# --- Ciclo principale -------------------------------------------------------

def process_email(item: dict) -> None:
    uid, url, pin = item["uid"], item["url"], item["pin"]

    if not url or not pin:
        # Email malformata: non migliora ritentando -> marca letta e avvisa
        missing = "link" if not url else "PIN"
        log.error("email uid=%s: %s non trovato nel testo", uid, missing)
        send_telegram_message(f"❌ Email uid={uid}: {missing} non trovato, conferma NON effettuata")
        mark_as_seen(uid)
        return

    n = attempts.get(uid, 0) + 1
    attempts[uid] = n
    log.info("email uid=%s: tentativo %d/%d", uid, n, MAX_ATTEMPTS)

    try:
        lesson_confirmation(url, pin)
    except PermanentError as e:
        log.error("email uid=%s: errore permanente: %s", uid, e)
        mark_as_seen(uid)
        attempts.pop(uid, None)
        return
    except Exception as e:
        log.error("email uid=%s: errore transitorio: %s", uid, e)
        if n >= MAX_ATTEMPTS:
            log.error("email uid=%s: raggiunti %d tentativi, rinuncio", uid, MAX_ATTEMPTS)
            send_telegram_message(
                f"❌ Rinuncio dopo {MAX_ATTEMPTS} tentativi (uid={uid}). Conferma da fare a mano:\n{url}")
            mark_as_seen(uid)
            attempts.pop(uid, None)
        return  # altrimenti l'email resta non letta e viene ritentata

    # Successo: solo ora l'email viene marcata come letta
    mark_as_seen(uid)
    attempts.pop(uid, None)


def main() -> int:
    if not check_env_variables():
        return 1

    log.info("bot avviato: controllo ogni %ds, max %d tentativi, screenshot in %s (retention %d giorni)",
             CHECK_INTERVAL, MAX_ATTEMPTS, SCREENSHOT_DIR, SCREENSHOT_RETENTION_DAYS)
    send_telegram_message("🤖 Bot avviato - inizio monitoraggio email")

    while True:
        try:
            for item in fetch_pending_emails():
                process_email(item)
        except Exception as e:
            # Errori IMAP/rete: non fermano il bot, si riprova al giro dopo
            log.error("errore nel controllo della casella: %s", e)

        try:
            cleanup_screenshots()
        except Exception as e:
            log.warning("pulizia screenshot fallita: %s", e)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.info("interrotto dall'utente")
        sys.exit(0)
