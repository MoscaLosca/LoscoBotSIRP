# LoscoBotSIRP

Bot Python che monitora automaticamente la tua casella email e conferma la presenza alle lezioni sulla piattaforma **SIRP Regione Puglia**, senza dover fare nulla manualmente.

---

## Cosa fa

- Controlla la casella email ogni 100 secondi
- Quando arriva l'email di conferma lezione, estrae automaticamente il link e il PIN studente
- Apre il link, legge il codice lezione dalla pagina
- Compila i campi richiesti e clicca il bottone di conferma
- Controlla l'esito della conferma rilevando la notifica a schermo
- Salva uno screenshot come prova della conferma effettuata
- Invia una notifica Telegram con l'esito e lo screenshot

---

## Installazione

Assicurati di avere **Python 3.x** installato, poi esegui:

```bash
pip install imap-tools playwright python-dotenv requests
playwright install chromium
```

---

## Configurazione

Il bot non chiede più credenziali a runtime. Modifica il file `.env` nella stessa cartella dello script:

```env
EMAIL=tuaemail@gmail.com
APP_PASSWORD=xxxx xxxx xxxx xxxx
TELEGRAM_BOT_TOKEN=il_tuo_bot_token
TELEGRAM_CHAT_ID=il_tuo_chat_id

# Opzionali (hanno già valori di default)
IMAP_SERVER=imap.gmail.com
SUBJECT=Conferma la tua presenza
```

Se una delle variabili obbligatorie manca, il bot si blocca all'avvio e indica quali variabili sono assenti.

---

## Utilizzo

```bash
python loscobot.py
```

Il bot si avvierà, invierà un messaggio Telegram di conferma e inizierà a monitorare la casella email automaticamente.

---

## Notifiche Telegram

Ad ogni conferma il bot invia su Telegram:

- ✅ Messaggio di successo + screenshot, se la conferma è andata a buon fine
- ❌ Messaggio di errore + screenshot (se disponibile), in caso di problemi

### Come creare un bot Telegram

1. Apri Telegram e cerca **@BotFather**
2. Invia `/newbot` e segui le istruzioni
3. Copia il **token** ricevuto → `TELEGRAM_BOT_TOKEN`
4. Avvia una conversazione con il tuo bot, poi vai su `https://api.telegram.org/bot<TOKEN>/getUpdates`
5. Copia il valore `id` dentro `"chat"` → `TELEGRAM_CHAT_ID`

---

## Come ottenere la App Password Gmail

Il bot richiede una **App Password** di Gmail, non la tua password normale. Per generarla:

1. Vai su [myaccount.google.com](https://myaccount.google.com)
2. Clicca su **Sicurezza**
3. Attiva la **Verifica in due passaggi** (se non è già attiva)
4. Cerca **Password per le app** e cliccaci
5. Dai un nome (es. `LoscoBotSIRP`) e clicca **Genera**
6. Copia la password di 16 caratteri e usala nel file `.env`

---

## Screenshot

Ogni esecuzione genera un file immagine nella stessa cartella dello script:

- `Conferma_YYYYMMDD_HHMMSS.png` — conferma riuscita
- `Errore_YYYYMMDD_HHMMSS.png` — errore durante la conferma

---

## Note

- Le email già elaborate vengono automaticamente marcate come lette, quindi non verranno mai processate due volte
- Il browser gira in modo invisibile in background
- Lo script è pensato per Gmail, ma funziona con qualsiasi provider IMAP configurando `IMAP_SERVER` nel file `.env`