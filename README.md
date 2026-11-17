# LoscoBotSIRP

Bot Python che monitora automaticamente la tua casella email e conferma la presenza alle lezioni sulla piattaforma **SIRP Regione Puglia**, senza dover fare nulla manualmente.

---

## Cosa fa

- Controlla la casella email a intervalli regolari (default: 100 secondi)
- Quando arriva l'email di conferma lezione, estrae automaticamente il link e il PIN studente
- Apre il link, legge il codice lezione dalla pagina
- Compila i campi richiesti e clicca il bottone di conferma
- Controlla l'esito della conferma rilevando la notifica a schermo
- Salva uno screenshot come prova della conferma effettuata
- Invia una notifica Telegram con l'esito e lo screenshot
- **Ritenta da solo** se la conferma fallisce per un errore transitorio
- **Cancella gli screenshot vecchi** (default: dopo 15 giorni)

---

## Installazione

Assicurati di avere **Python 3.10+** installato, poi esegui:

```bash
pip install imap-tools playwright python-dotenv requests
playwright install chromium
```

---

## Configurazione

Il bot non chiede credenziali a runtime. Copia `.env.example` in `.env` nella stessa cartella dello script e compilalo:

```env
EMAIL=tuaemail@gmail.com
APP_PASSWORD=xxxx xxxx xxxx xxxx
TELEGRAM_BOT_TOKEN=il_tuo_bot_token
TELEGRAM_CHAT_ID=il_tuo_chat_id
```

Variabili **opzionali** (con i rispettivi default):

| Variabile | Default | Significato |
|---|---|---|
| `IMAP_SERVER` | `imap.gmail.com` | Server IMAP della casella |
| `SUBJECT` | `Conferma la tua presenza` | Oggetto dell'email da cercare |
| `CHECK_INTERVAL` | `100` | Secondi tra un controllo e il successivo |
| `MAX_ATTEMPTS` | `5` | Tentativi massimi per la stessa email prima di rinunciare |
| `SCREENSHOT_DIR` | `./screenshots` | Cartella in cui salvare gli screenshot |
| `SCREENSHOT_RETENTION_DAYS` | `15` | Dopo quanti giorni cancellare gli screenshot |

Se una delle variabili obbligatorie manca, il bot si blocca all'avvio e indica quali variabili sono assenti.

---

## Utilizzo

```bash
python loscobot.py
```

Il bot si avvierà, invierà un messaggio Telegram di conferma e inizierà a monitorare la casella email automaticamente. I log vanno su stdout (comodo con `systemd`/`journalctl`).

---

## Come gestisce gli errori

L'email viene marcata come **letta solo dopo una conferma riuscita**. Questo significa:

- **Errore transitorio** (timeout, pagina non ancora caricata, rete assente): l'email resta non letta e viene ritentata al controllo successivo, fino a `MAX_ATTEMPTS` volte. Su Telegram arriva un avviso ⚠️ per ogni tentativo fallito.
- **Tentativi esauriti**: il bot rinuncia, marca l'email come letta e invia su Telegram ❌ il link per fare la conferma a mano.
- **Errore permanente** (email senza link o PIN, conferma rifiutata dal sito): non ha senso ritentare, l'email viene marcata subito come letta e arriva un avviso ❌.
- **Problemi IMAP o Telegram** non fermano il bot: si riprova al giro successivo.

---

## Notifiche Telegram

- 🤖 Avvio del bot
- ✅ Conferma riuscita + screenshot
- ⚠️ Errore transitorio + screenshot (il bot riproverà)
- ❌ Errore definitivo (+ screenshot se disponibile)

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

Gli screenshot vengono salvati in `SCREENSHOT_DIR` (default: cartella `screenshots/` accanto allo script, creata automaticamente):

- `Conferma_YYYYMMDD_HHMMSS.png` — conferma riuscita
- `Errore_YYYYMMDD_HHMMSS.png` — errore durante la conferma

A ogni ciclo i file più vecchi di `SCREENSHOT_RETENTION_DAYS` giorni vengono eliminati.

---

## Note

- Il browser gira in modo invisibile in background
- Lo script è pensato per Gmail, ma funziona con qualsiasi provider IMAP configurando `IMAP_SERVER` nel file `.env`
