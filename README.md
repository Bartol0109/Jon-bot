# 💼 Job bot – dnevni programerski oglasi za studente (WhatsApp / Telegram)

Mala Python aplikacija koja **svaki dan u 12:00 (Europe/Zagreb)**:

1. skupi svježe oglase (zadnjih ~24–48 h) za programerske poslove pogodne za studente / osobe bez iskustva
   (junior, praksa, internship, trainee, studentski posao…) – **remote bilo gdje** + **Hrvatska (svi gradovi)**,
2. makne duplikate i oglase koji su već poslani,
3. (opcionalno) AI-jem (xAI Grok ili OpenAI) ocijeni oglase prema tvojim kriterijima i odabere 5–10 najboljih,
   s kratkim obrazloženjem na hrvatskom – bez API ključa koristi filter po ključnim riječima,
4. pošalje ti poruku na **WhatsApp (CallMeBot ili Twilio)** ili **Telegram**.

Radi potpuno samostalno na [Railwayu](https://railway.com) – ne treba nikakav asistent.

---

## Izvori oglasa (testirano 31.10.2026.)

| Izvor | Tip | Opseg | Napomena |
|---|---|---|---|
| Remotive | službeni JSON API | remote | kategorija software-dev; besplatni API kasni ~24 h |
| RemoteOK | službeni JSON API | remote | |
| Arbeitnow | službeni JSON API | remote (+ HR ako ima) | uzimaju se samo remote oglasi (većina je Njemačka) |
| Jobicy | službeni JSON API | remote | tagovi developer/junior/intern |
| Himalayas | službeni JSON API | remote | filter „Entry-level“; mnogi su ograničeni na SAD → automatski se izbace |
| We Work Remotely | RSS | remote | kategorija programming |
| Posao.hr | službeni RSS | Hrvatska | djelatnost „Informatika i telekomunikacije“ |
| MojPosao.hr | JSON koji koristi njihova web stranica | Hrvatska | nije službeni API – može se promijeniti bez najave |

Svaki izvor je izoliran: ako jedan padne, ostali normalno rade (u logu piše koji je pao).
Izvor isključiš s `DISABLED_SOURCES=himalayas,arbeitnow`.
**HZZ burza rada** nije uključena (ASP.NET stranica s cookie provjerama, bez RSS-a/API-ja).

---

## 1. Lokalno testiranje

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # pa ispuni što trebaš
python main.py --dry-run                                 # samo ispiše poruku, ništa ne šalje
python main.py --test-whatsapp                           # pošalje testnu poruku preko SENDER-a
python main.py --test-whatsapp --sender telegram         # test baš za Telegram
```

`--dry-run` ne šalje ništa i ne zapisuje oglase kao „poslane“.

---

## 2. Odaberi kanal za poruke (`SENDER`)

### A) CallMeBot – WhatsApp, besplatno (zadano, `SENDER=callmebot`)

> ⚠️ **Na dan pisanja (31.10.2026.) CallMeBot je pun** – na njihovoj stranici piše:
> *„The bot is currently full. Please check back in a few days; once slots are available, the phone number will be visible.“*
> Broj bota je trenutno skriven. Ako je tako i kod tebe, koristi **Telegram** (B) dok se mjesta ne oslobode.

Koraci (prema https://www.callmebot.com/blog/free-api-whatsapp-messages/):

1. Otvori gornji link i **prepiši trenutni broj bota** (počinje s `+34…`) – dodaj ga u kontakte na mobitelu.
   Broj se mijenja/skriva pa ga ne pišemo ovdje.
2. Na WhatsAppu tom kontaktu pošalji točno: `I allow callmebot to send me messages`
3. Pričekaj odgovor *„API Activated for your phone number. Your APIKEY is 123123“*.
   Ako ne stigne u 2 minute, pokušaj ponovno nakon 24 h.
4. Na Railwayu postavi:
   - `CALLMEBOT_PHONE` = tvoj broj s pozivnim, npr. `+385911234567`
   - `CALLMEBOT_APIKEY` = broj iz poruke
5. Testiraj: `python main.py --test-whatsapp`

Napomena: besplatni CallMeBot je samo za osobnu upotrebu (poruke samo tebi). Duge poruke bot dijeli na
više dijelova (~900 znakova) s pauzom od 6 s između njih.

### B) Telegram – najpouzdanije, besplatno (`SENDER=telegram`) ✅ preporučena rezerva

1. U Telegramu otvori **@BotFather** → `/newbot` → upiši ime i korisničko ime (mora završavati na `bot`).
2. BotFather ti da **token** (npr. `123456:ABC-...`) → to je `TELEGRAM_BOT_TOKEN`.
3. Otvori svog novog bota (link od BotFathera) i pošalji mu bilo što, npr. `bok` (bez toga bot ti ne smije pisati).
4. Saznaj **chat ID**:
   - lokalno: `TELEGRAM_BOT_TOKEN=... python main.py --telegram-chat-id`, ili
   - u pregledniku otvori `https://api.telegram.org/bot<TOKEN>/getUpdates` i nađi `"chat":{"id":123456789,...}`.
5. Postavi `SENDER=telegram`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` i testiraj `python main.py --test-whatsapp`.

### C) Twilio – WhatsApp (`SENDER=twilio`)

1. Registriraj se na https://www.twilio.com (trial je besplatan).
2. Console → *Messaging → Try it out → Send a WhatsApp message* (WhatsApp Sandbox).
3. Sa svog WhatsAppa pošalji poruku `join <tvoja-dva-riječi>` na sandbox broj **+1 415 523 8886**
   (točan kod piše u konzoli).
4. Postavi `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` (Console → Account Info),
   `TWILIO_WHATSAPP_FROM=whatsapp:+14155238886`, `TWILIO_WHATSAPP_TO=whatsapp:+385...`.

> ⚠️ **Ograničenja sandboxa** (zato Twilio nije idealan za dnevnog bota):
> - **sandbox članstvo istječe nakon 3 dana** – moraš ponovno poslati `join ...`;
> - **24-satni prozor**: slobodan tekst se smije slati samo unutar 24 h od tvoje zadnje poruke tom broju.
>   Izvan toga WhatsApp dopušta samo odobrene predloške (templates) pa poruke neće stići.
>   Praktično: svaki dan prije 12 h pošalji sandbox broju bilo kakvu poruku, ili registriraj vlastiti
>   WhatsApp Business sender i odobreni predložak (plaća se).
> - sandbox šalje najviše 1 poruku / 3 s (bot čeka 4 s između dijelova).

---

## 3. AI rangiranje (opcionalno)

Bez `LLM_API_KEY` bot koristi filter po ključnim riječima (junior/intern/praksa/student…, izbacuje senior/lead/
„5+ years“). S ključem AI ocijeni do 80 kandidata prema `JOB_CRITERIA` i napiše razlog za svaki.

**xAI (Grok)** – zadano:
1. https://console.x.ai → prijava → *API Keys* → *Create API key*. (Treba dodati malo kredita; jedan dnevni run je
   reda veličine jednog centa.)
2. `LLM_API_KEY=xai-...`, `LLM_BASE_URL=https://api.x.ai/v1`, `LLM_MODEL=grok-4.20-non-reasoning`
   (popis modela: https://docs.x.ai/developers/models).

**OpenAI**:
1. https://platform.openai.com/api-keys → *Create new secret key*.
2. `LLM_API_KEY=sk-...`, `LLM_BASE_URL=https://api.openai.com/v1`, `LLM_MODEL=gpt-4o-mini` (ili noviji jeftini model).

Kriterije mijenjaš u `JOB_CRITERIA`, npr.
`Student 2. godine FER-a, Python/JavaScript, praksa ili studentski posao, remote ili Zagreb, bez iskustva`.

---

## 4. Deploy na Railway (korak po korak)

### 4.1 GitHub
```bash
cd job-bot
git init && git add . && git commit -m "Job bot"
# na github.com napravi novi (privatni) repozitorij, npr. job-bot, pa:
git remote add origin https://github.com/<tvoj-user>/job-bot.git
git branch -M main && git push -u origin main
```
`.env` je u `.gitignore` – **ključeve nikad ne stavljaj u git**.

### 4.2 Railway servis
1. https://railway.com → *New Project* → *Deploy from GitHub repo* → odaberi `job-bot`.
2. Railway (Railpack) sam prepozna Python (`requirements.txt`, `main.py`) i pokreće `python main.py`
   (isto piše u `Procfile`). Ako treba, u *Settings → Deploy → Custom Start Command* upiši `python main.py`.
3. *Variables* → dodaj varijable iz `.env.example` (najmanje `SENDER` + podaci za odabrani kanal).
   Može i *Raw Editor* → zalijepi sadržaj svoje `.env` datoteke.

### 4.3 Cron raspored (preporučeno) ⏰
*Settings → Cron Schedule*. Railway cron radi u **UTC**-u, a Hrvatska ima ljetno/zimsko vrijeme:

| Razdoblje | 12:00 u Zagrebu = | cron |
|---|---|---|
| zimsko vrijeme (CET, UTC+1), kraj listopada – kraj ožujka | 11:00 UTC | `0 11 * * *` |
| ljetno vrijeme (CEST, UTC+2), kraj ožujka – kraj listopada | 10:00 UTC | `0 10 * * *` |

**Najbolje (bez ručnog mijenjanja):** cron `0 10,11 * * *` + varijabla `ONLY_AT_LOCAL_HOUR=12`.
Railway pokrene skriptu u 10 i 11 UTC, a skripta stvarno radi samo kad je u Zagrebu 12 h – drugi put odmah izađe.
(Ako ne postaviš `ONLY_AT_LOCAL_HOUR`, koristi jedan od cronova iz tablice i mijenjaj ga pri promjeni vremena.)

U cron načinu skripta odradi posao i **izađe** (Railway preskače sljedeći run ako prethodni još radi).
U *Settings → Deploy → Restart Policy* stavi **Never** (ili On Failure) da se ne vrti u krug.

> Napomena: datoteka `railway.json` (config-as-code) je kod Railwaya označena kao zastarjela,
> zato se raspored postavlja u dashboardu.

### 4.4 Volume (preporučeno – pamćenje poslanih oglasa)
Railway disk je **privremen** – nakon svakog runa/deploya `data/` nestaje. Bez volumena bot ne pamti što je poslao,
pa se oslanja na datum: uzima samo oglase iz zadnjih **26 h** (malo duplikata, ali može propustiti oglas koji je izvor
objavio s kašnjenjem).

S volumenom:
1. U projektu desni klik na servis (ili ⌘K) → *Attach Volume* / *New Volume* → mount path npr. `/data`.
2. Railway sam postavi `RAILWAY_VOLUME_MOUNT_PATH=/data` – bot ga automatski koristi (`/data/seen_jobs.sqlite3`)
   i tada gleda oglase iz zadnjih **48 h** te preskače već poslane.
3. (Opcionalno) `DATA_DIR=/data` ako želiš eksplicitno.

### 4.5 Test na Railwayu
- Ručni run: `railway cron run` iz Railway CLI-ja (ili redeploy servisa) – pogledaj *Logs*.
- Za testnu poruku privremeno promijeni start command u `python main.py --test-whatsapp`, deployaj, pa vrati na `python main.py`.
- Za probu bez slanja: start command `python main.py --dry-run` (poruka se ispiše u logove).

### Alternativa: stalno upaljen servis (`RUN_MODE=scheduler`)
Postavi `RUN_MODE=scheduler` (i `RUN_AT=12:00`), **ne** postavljaj Cron Schedule, restart policy *Always*.
Proces stalno radi i sam čeka 12:00 po `Europe/Zagreb` (zoneinfo, DST riješen automatski).
Troši više resursa od crona, pa je cron preporučen.

---

## Sve varijable

| Varijabla | Zadano | Opis |
|---|---|---|
| `SENDER` | `callmebot` | `callmebot` / `telegram` / `twilio` |
| `CALLMEBOT_PHONE`, `CALLMEBOT_APIKEY` | – | CallMeBot |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | – | Telegram |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `TWILIO_WHATSAPP_TO` | from: `whatsapp:+14155238886` | Twilio |
| `LLM_API_KEY` | – | bez njega: keyword filter |
| `LLM_BASE_URL` | `https://api.x.ai/v1` | bilo koji OpenAI-kompatibilni API |
| `LLM_MODEL` | `grok-4.20-non-reasoning` | |
| `JOB_CRITERIA` | Student bez iskustva, … | tekst kriterija za AI |
| `MAX_RESULTS` | `8` | max oglasa po danu |
| `RUN_MODE` | `cron` | `cron` / `scheduler` |
| `RUN_AT` | `12:00` | vrijeme za scheduler mod |
| `ONLY_AT_LOCAL_HOUR` | – | npr. `12` za DST-safe cron `0 10,11 * * *` |
| `TZ_NAME` | `Europe/Zagreb` | |
| `DATA_DIR` | `RAILWAY_VOLUME_MOUNT_PATH` ili `./data` | gdje je SQLite baza |
| `MAX_AGE_HOURS` | 48 (s volumenom) / 26 (bez) | koliko stari oglasi |
| `DISABLED_SOURCES` | – | npr. `himalayas,mojposao_hr` |

## Struktura
```
main.py              CLI: --dry-run, --test-whatsapp, --sender, --mode, --telegram-chat-id
jobbot/sources.py    izvori oglasa (svaki izoliran)
jobbot/ranking.py    keyword filter + LLM rangiranje
jobbot/formatter.py  poruka na hrvatskom + dijeljenje na dijelove
jobbot/senders.py    CallMeBot / Twilio / Telegram
jobbot/store.py      SQLite pamćenje poslanih oglasa
```

## Poznata ograničenja
- Svježih oglasa „za početnike“ zna biti malo (posebno vikendom) – tada stigne poruka *„Danas nema novih oglasa…“*.
- Keyword filter je grub: ako nema dovoljno jasnih junior oglasa, dopuni ih ne-senior oglasima bez traženih godina
  iskustva (označeno s „provjeri uvjete“). AI način je puno precizniji.
- MojPosao.hr koristi nedokumentirani endpoint; ako se promijeni, izvor se samo preskoči (vidi log).
- Remote oglasi ograničeni na druge države (npr. „United States“) se izbacuju; „Remote“ oglasi s Arbeitnowa
  često traže njemački ili boravak u DE/CH – AI ih ocjenjuje niže.
- Molimo poštuj uvjete izvora (RemoteOK/Jobicy traže navođenje izvora – linkovi vode na njihove stranice).
