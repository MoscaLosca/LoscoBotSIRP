# LoscoBotSIRP

Bot Python che monitora automaticamente la tua casella email e conferma la presenza alle lezioni sulla piattaforma **SIRP Regione Puglia**, senza dover fare nulla manualmente.

---

## Cosa fa

- Controlla la casella email ogni 30 secondi
- Quando arriva l'email di conferma lezione, estrae automaticamente il link e il PIN studente
- Apre il link, legge il codice lezione dalla pagina
- Compila i campi richiesti e clicca il bottone di conferma
- Salva uno screenshot come prova della conferma effettuata

---

## Installazione

Assicurati di avere **Python 3.x** installato, poi esegui:

```bash
pip install imap-tools playwright
playwright install chromium
```

---

## Utilizzo

Avvia lo script:

```bash
python loscobot.py
```

Ti verranno chieste solo due cose:

```
Inserisci la tua mail: tuaemail@gmail.com
Inserisci la APP password: xxxx xxxx xxxx xxxx
```

Il bot si avvierà e inizierà a monitorare la casella email automaticamente.

---

## Come ottenere la App Password Gmail

Il bot richiede una **App Password** di Gmail, non la tua password normale. Per generarla:

1. Vai su [myaccount.google.com](https://myaccount.google.com)
2. Clicca su **Sicurezza**
3. Attiva la **Verifica in due passaggi** (se non è già attiva)
4. Cerca **Password per le app** e cliccaci
5. Dai un nome (es. `LoscoBotSIRP`) e clicca **Genera**
6. Copia la password di 16 caratteri e usala quando lo script la richiede

---

## Screenshot

Ogni conferma andata a buon fine genera un file immagine nella stessa cartella dello script, con nome:

```
Conferma_GG-MM-AAAA_HH:MM:SS.png
```

---

## Note

- Le email già elaborate vengono automaticamente marcate come lette, quindi non verranno mai processate due volte
- Il browser gira in modo invisibile in background
- Lo script è pensato per Gmail, ma funziona con qualsiasi provider IMAP