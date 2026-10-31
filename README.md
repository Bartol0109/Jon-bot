# 💼 Job bot – dnevni tehnološki oglasi za studente (WhatsApp / Telegram)

Mala Python aplikacija koja **svaki dan u 12:00 (Europe/Zagreb)**:

1. skupi svježe oglase (zadnjih ~24–48 h) za početne tehnološke uloge pogodne za studente / osobe bez iskustva
   (programiranje, data/business/BI analitičar, QA i testiranje, IT i tehnička podrška, helpdesk,
   application support, technical/customer success engineer, junior DevOps ili sysadmin;
   i hrvatski termini: analitičar, podrška, tehnička podrška…) – **on-site/hybrid samo Zagreb i Zadar**,
   **remote** ako je otvoren bilo gdje u EU (ili Europe/worldwide) i ako je dovoljan engleski,
2. makne duplikate i oglase koji su već poslani,
3. (opcionalno) AI-jem (xAI Grok ili OpenAI) ocijeni oglase prema tvojim kriterijima i odabere 5–10 najboljih,
   s kratkim obrazloženjem na hrvatskom – bez API ključa koristi filter po ključnim riječima,
4. pošalje ti poruku na **WhatsApp (CallMeBot ili Twilio)** ili **Telegram**.

Radi samostalno kao besplatni zakazani workflow na GitHub Actionsu (svaki dan u 12:00 po Zagrebu). Railway ostaje kao alternativa ako ga već imaš.

---

## Izvori oglasa (testirano 31.10.2026.)

| Izvor | Tip | Opseg | Napomena |
|---|---|---|---|
| Remotive | službeni JSON API | remote | kategorije software-dev, customer-support, devops, qa; besplatni feed je mali i zna ignorirati kategoriju |
| RemoteOK | službeni JSON API | remote | cijeli feed, pa ga suzi filter uloga |
| Arbeitnow | službeni JSON API | remote (+ HR ako ima) | uzimaju se samo remote oglasi (većina je Njemačka) |
| Jobicy | službeni JSON API | remote | tagovi developer, junior, intern, data, analyst, devops, support |
| Himalayas | službeni JSON API | remote | „Entry-level“ + upiti developer, data/business analyst, QA, IT support, helpdesk, devops; SAD-only se izbace |
| We Work Remotely | RSS | remote | programming, devops/sysadmin i customer support |
| Posao.hr | službeni RSS | Hrvatska | djelatnost „Informatika i telekomunikacije“ (pokriva i podršku i analitiku) |
| MojPosao.hr | JSON koji koristi njihova web stranica | Hrvatska | upiti za uloge + dodatni upit po `ONSITE_CITIES` (Zagreb, Zadar); nije službeni API |

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

Bez `LLM_API_KEY` bot koristi filter po ključnim riječima. Uloge su u `ROLE_KEYWORDS`
(programiranje, analitičar, QA, IT/tehnička podrška, helpdesk, DevOps/sysadmin…; prazno = ugrađeni popis).
Junior/intern/praksa i dalje idu naprijed, a senior/lead/manager i „5+ years“ ispadaju.
S ključem AI ocijeni do 80 kandidata prema `JOB_CRITERIA` i napiše razlog za svaki.

**xAI (Grok)** – zadano:
1. https://console.x.ai → prijava → *API Keys* → *Create API key*. (Treba dodati malo kredita; jedan dnevni run je
   reda veličine jednog centa.)
2. `LLM_API_KEY=xai-...`, `LLM_BASE_URL=https://api.x.ai/v1`, `LLM_MODEL=grok-4.20-non-reasoning`
   (popis modela: https://docs.x.ai/developers/models).

**OpenAI**:
1. https://platform.openai.com/api-keys → *Create new secret key*.
2. `LLM_API_KEY=sk-...`, `LLM_BASE_URL=https://api.openai.com/v1`, `LLM_MODEL=gpt-4o-mini` (ili noviji jeftini model).

Kriterije mijenjaš u `JOB_CRITERIA`, npr.
`Student 2. godine FER-a, Python ili data analyst, praksa ili studentski posao, remote ili Zagreb, bez iskustva`.
Uloge za filter (ne AI tekst) mijenjaš s `ROLE_KEYWORDS=data analyst, qa, helpdesk, devops` – to **zamjenjuje** ugrađeni popis.

**Lokacija.** On-site i hybrid samo u `ONSITE_CITIES` (zadano **Zagreb** i **Zadar**). Remote samo ako je otvoren kandidatima **bilo gdje u EU**, ili je Europe/worldwide/EMEA/CET koje EU uključuje (`REMOTE_REGIONS`). Oglas samo za Njemačku, Austriju ili SAD otpada. Oglas (naslov i opis) mora biti **na engleskom ili hrvatskom**. Ako je pretežno njemački, nizozemski, francuski ili drugi jezik, ili naslov ima tipične riječi (`Kundenservice`, `Mitarbeiter`, `(m/w/d)`, `Werkstudent`, `Kundenbetreuer`), otpada. Isto vrijedi ako oglas *traži* drugi jezik (`fluent German`, `Deutschkenntnisse`, `German speaker`, `native Dutch` — popis je `EXCLUDED_LANGUAGES`). Hrvatski je u redu. Naslov s riječima iz `EXCLUDE_KEYWORDS` (zadano hardware, electronics, embedded, firmware, PCB, FPGA, elektro, mehatronika, field technician, …) također otpada — to nije softver, analitika ni podrška. `/iskljuci` i `/ukljuci` mijenjaju taj popis. `/remote off` (ili `/bezremote`) isključi sve remote oglase; ostaju samo on-site i hybrid u gradovima. `/remote on` ih vraća. Zadano je uključeno. Vrijedi za dnevni pregled, `/poslovi` i `/mjesec`. U poruci stoji `⭐ Zagreb`, `⭐ Zadar` (ili `· hibrid`) odnosno `🌍 Remote`.

---

## 4. Deploy na GitHub Actions (preporučeno)

Workflow `.github/workflows/daily-job-bot.yml` pokreće bota **jednom dnevno** u podne po `Europe/Zagreb`, ljeti i zimi. Zakazani runovi rade **samo na grani `main`**, nakon mergea. Pull request samo provjeri logiku rasporeda i ništa ne šalje.

GitHubov cron je u **UTC-u** i run se zna odgoditi (često oko pune ure). 12:00 u Zagrebu je **10:00 UTC ljeti** (CEST) ili **11:00 UTC zimi** (CET). Zato raspored nije jedna UTC ura, nego:

```cron
5 9-16 * * *
```

svaki sat od 9 do 16 UTC, u minuti :05 (manje gužve nego u :00). Skripta `.github/scripts/should_send.py` odlučuje:

- ako je lokalno **12:00 ili kasnije** i za **današnji zagrebački datum** još nije poslano → pošalji (odgoda do popodneva i dalje prođe; drugi run isti dan odmah izađe);
- ako je **prije 12:00**, a cijeli prethodni dan je propušten → jedna nadoknada, zabilježena kao jučer, da današnje podne ipak ode;
- inače prije podneva → preskoči.

Ako slanje padne, datum se ne zabilježi pa sljedeći sat u tom prozoru pokuša opet. `ONLY_AT_LOCAL_HOUR` **nemoj** postavljati za Actions: ta provjera traži točno 12 h i odgođeni run bi preskočio cijeli dan. Workflow sam forsira `RUN_MODE=cron` i `TZ_NAME=Europe/Zagreb`.

Već poslani oglasi (SQLite, isto što lokalno stoji u `data/seen_jobs.sqlite3`) i datum zadnjeg slanja drže se u **Actions cacheu** između runova. To nije commit i nema tajni. Na runneru su izvan git checkouta, jer je `data/` u `.gitignore`. GitHub cache obriše ako se ne dirne 7 dana ili ako se napuni kvota; svakodnevni run ga obnavlja. Ako cache nestane, bot može jednom ponoviti oglase iz zadnjih 48 h.

### 4.1 Secrets (tajne)

Repo → **Settings** → **Secrets and variables** → **Actions** → kartica **Secrets** → **New repository secret**.

Imena moraju biti točno ovakva. Vrijednosti prazne u gitu; ovdje ide prava vrijednost. Prazan secret koji ne koristiš možeš preskočiti.

| Secret | Kad treba |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `SENDER=telegram` |
| `TELEGRAM_CHAT_ID` | `SENDER=telegram` |
| `LLM_API_KEY` | opcionalno (bez njega: filter po ključnim riječima) |
| `CALLMEBOT_PHONE` | `SENDER=callmebot` |
| `CALLMEBOT_APIKEY` | `SENDER=callmebot` |
| `TWILIO_ACCOUNT_SID` | `SENDER=twilio` |
| `TWILIO_AUTH_TOKEN` | `SENDER=twilio` |
| `TWILIO_WHATSAPP_FROM` | `SENDER=twilio` (prazno = sandbox `whatsapp:+14155238886`) |
| `TWILIO_WHATSAPP_TO` | `SENDER=twilio` |

### 4.2 Variables (nisu tajne)

Isti ekran → kartica **Variables** → **New repository variable**. Ako varijablu ne dodaš, vrijedi zadano.

| Variable | Zadano ako je nema |
|---|---|
| `SENDER` | `telegram` |
| `LLM_BASE_URL` | `https://api.x.ai/v1` |
| `LLM_MODEL` | `grok-4.20-non-reasoning` |
| `JOB_CRITERIA` | ugrađeni tekst (početne tech uloge, remote ili Hrvatska, bez seniora) |
| `ROLE_KEYWORDS` | ugrađeni popis uloga (vidi odjeljak 3) |
| `ONSITE_CITIES` | `Zagreb, Zadar` (on-site/hybrid; u poruci ⭐) |
| `REMOTE_REGIONS` | EU / Europe / worldwide (ne pojedina susjedna država) |
| `EXCLUDED_LANGUAGES` | fraze poput `fluent German`, `Kundenservice` (prazno = ugrađeni popis) |
| `EXCLUDE_KEYWORDS` | hardware, firmware, elektro, … u naslovu (prazno = ugrađeni popis) |
| `MAX_RESULTS` | `8` |
| `MAX_AGE_HOURS` | `48` (cache se računa kao trajna pohrana) |
| `DISABLED_SOURCES` | ništa (npr. `himalayas,arbeitnow`) |

`SENDER=callmebot` ili `SENDER=twilio` postaviš ovdje; tokeni i brojevi idu u Secrets, ne u Variables.

### 4.3 Ručni test

1. Otvori **Actions**.
2. Lijevo odaberi **Dnevni job bot**.
3. **Run workflow**.
4. Branch: **`main`** (nakon mergea). Run s druge grane ne dijeli cache s dnevnim rasporedom na `main`.
5. **mode**:
   - `dry-run` — skupi oglase i ispiše poruku u log; ne šalje i ne računa se kao današnje slanje;
   - `test-message` — pošalje kratku testnu poruku preko `SENDER`-a (`python main.py --test-whatsapp`);
   - `send` — pravi dnevni run. Ako uspije, taj se dan više ne šalje automatski.
6. **Run workflow**.

Prije prvog `send` / rasporeda najprije `test-message`, pa po želji `dry-run`.

### 4.4 Logovi

**Actions** → **Dnevni job bot** → klik na run (zeleno / crveno) → job **run** → koraci.

- **Odluči treba li slati** — za zakazani run piše je li poslao, preskočio (već poslano ili još nije podne) ili radi nadoknadu.
- **Dry-run** / **Testna poruka** / **Pošalji dnevne oglase** — ispis bota.
- Crveni korak: otvori ga i pročitaj zadnje linije (najčešće nedostaje secret za odabrani `SENDER`).

Zakazani run koji namjerno ništa ne pošalje ostaje zelen.

### 4.5 60 dana bez aktivnosti

U **javnom** repozitoriju GitHub **automatski ugasi zakazane workflowe** ako 60 dana nema aktivnosti na repou. Samo pokretanje Actions to ne produžuje. Ništa se ne briše; stanje workflowa postane `disabled_inactivity` i ne ide ni cron ni ručni run dok ga netko opet ne uključi.

`.github/workflows/keepalive.yml` (**Održavanje rasporeda**) svaki ponedjeljak u 08:20 UTC napravi mali commit na `main` (`.github/keepalive-last.txt`, samo UTC vrijeme). To drži rok živim. Treba dozvola `contents: write` (već je u workflowu, preko `GITHUB_TOKEN`) i da zaštita grane ne blokira `github-actions[bot]`. Ručno: **Actions** → **Održavanje rasporeda** → **Run workflow** na `main`.

Ako je GitHub već ugasio workflow, keepalive se sam ne može upaliti. Uključi oba:

1. **Actions** → **Dnevni job bot** → **Enable workflow**.
2. **Actions** → **Održavanje rasporeda** → **Enable workflow**.

Isto radi `gh workflow enable "Dnevni job bot"` i `gh workflow enable "Održavanje rasporeda"`. Propušteni dani se ne nadoknađuju unazad osim kroz jutarnju nadoknadu iz odjeljka 4, i to samo ako je workflow uopće upaljen.

Dnevni pregled prije slanja pročita **prikvačenu Telegram poruku** s postavkama (ako postoji). Zato `/dodaj` i `/grad` u chatu vrijede i za poruku u 12:00. Vidi odjeljak 5.

---

## 5. Telegram naredbe na Renderu (besplatno)

Osim dnevnog pregleda na GitHub Actions, možeš pisati botu. To je mali web servis (`webapp.py`) na [Render](https://render.com) **free** planu. Besplatni web servis zaspi nakon otprilike 15 minuta tišine i nema stalni disk ni background worker. Zato:

- Telegram šalje poruku na **webhook** (ulazni HTTPS zahtjev budi servis),
- servis odmah vrati 200, a `/poslovi` traži oglase u pozadini,
- postavke nisu na disku: bot ih drži u **prikvačenoj poruci** u tvom chatu (JSON red `JOBBOT_SETTINGS=…`). To ne košta i preživi restart. Dnevni GitHub Actions čita istu poruku. Poruku nemoj brisati ni otkvačivati. Ako je nema, vrijede ugrađeni filtri i Variables.

Ručni `/poslovi` ne dijeli bazu već poslanih oglasa s Actions cacheom, pa se isti oglas može pojaviti i u jutarnjoj poruci.

### 5.1 Naredbe

| Naredba | Što radi |
|---|---|
| `/start`, `/pomoc` | pomoć |
| `/poslovi` | odmah potraži svježe oglase i pošalji |
| `/mjesec` | zadnjih 30 dana, bez preskakanja već poslanih; neki izvori daju samo novije oglase |
| `/postavke` | pokaži uloge i gradove |
| `/dodaj data analyst` | dodaj ulogu |
| `/makni data analyst` | makni ulogu |
| `/grad Zagreb` | dodaj grad za on-site/hybrid |
| `/maknigrad Zagreb` | makni grad (zadnji ne može) |
| `/iskljuci hardware` | izbaci naslove koji sadrže tu riječ |
| `/ukljuci hardware` | vrati tu riječ (naslov opet može proći) |
| `/remote` | jesu li remote oglasi uključeni |
| `/remote off`, `/bezremote` | samo on-site/hybrid u gradovima |
| `/remote on` | opet šalji i remote |
| `/reset` | vrati ugrađene filtre |

Bot odgovara samo chatu iz `TELEGRAM_CHAT_ID`. Zahtjev mora imati zaglavlje `X-Telegram-Bot-Api-Secret-Token` jednak `WEBHOOK_SECRET`.

### 5.2 Deploy

1. Na https://render.com napravi račun i **New → Blueprint**. Spoji GitHub repozitorij `Jon-bot` i granu `main` (nakon mergea). Render čita `render.yaml` (plan: free, health check `/health`).
2. U servisu **Environment** upiši:
   - `TELEGRAM_BOT_TOKEN` — token od BotFathera
   - `TELEGRAM_CHAT_ID` — tvoj chat (vidi odjeljak 2.B)
   - `WEBHOOK_SECRET` — Blueprint ga sam generira; možeš ga ostaviti ili upisati svoj dugačak nasumičan niz
   Ostalo (`SENDER=telegram`) već stoji u `render.yaml`. `LLM_API_KEY` je opcionalan ako želiš AI rangiranje i na ručnoj pretrazi.
3. Pričekaj da deploy prođe. Prvi `GET /health` smije trajati dok se servis budi. URL je oblika `https://job-bot-xxxx.onrender.com`.
4. Uključi webhook. U Renderu otvori **Shell** pokrenutog servisa i pokreni:

```bash
python -m jobbot.set_webhook
```

Mora ispisati `Webhook postavljen: https://…/telegram/webhook`. Isto radi, s bilo kojeg računala:

```bash
curl -X POST "$RENDER_URL/telegram/setup" -H "X-Setup-Token: $WEBHOOK_SECRET"
```

(`RENDER_URL` je adresa servisa. `WEBHOOK_SECRET` je vrijednost iz Environment.)
5. U Telegramu otvori bota i pošalji `/start`. Trebao bi prikvačiti poruku s postavkama. Zatim `/postavke`, `/dodaj data analyst`, `/poslovi`.
6. Ako je servis spavao, prva poruka može kasniti pola minute dok se Render budi. Sljedeće su brže. `/poslovi` nakon toga još traži oglase (desetak sekundi i više).

Dnevni pregled i dalje ide s GitHub Actions u 12:00. Na Actions trebaju isti `TELEGRAM_BOT_TOKEN` i `TELEGRAM_CHAT_ID` (Secrets), inače se pin ne može pročitati i ostaju zadani filtri.

---

## Alternativa: deploy na Railway

Railway više nije potreban. Upute ostaju ako servis već imaš ili ga kasnije otvoriš. Na Actionsima nemoj postavljati `ONLY_AT_LOCAL_HOUR`; na Railwayu ta varijabla i dalje vrijedi kao dolje.

### A.1 GitHub
Datoteke su u **korijenu** repozitorija (nema podmape `job-bot/`). `.env` je u `.gitignore` – **ključeve nikad ne stavljaj u git**. Ako repozitorij već postoji, preskoči `git init`. Novi izgleda ovako:

```bash
git init && git add . && git commit -m "Job bot"
git remote add origin https://github.com/<tvoj-user>/<repo>.git
git branch -M main && git push -u origin main
```

### A.2 Railway servis
1. https://railway.com → *New Project* → *Deploy from GitHub repo* → odaberi ovaj repozitorij.
2. Railway (Railpack) sam prepozna Python (`requirements.txt`, `main.py`) i pokreće `python main.py`
   (isto piše u `Procfile`). Ako treba, u *Settings → Deploy → Custom Start Command* upiši `python main.py`.
3. *Variables* → dodaj varijable iz `.env.example` (najmanje `SENDER` + podaci za odabrani kanal).
   Može i *Raw Editor* → zalijepi sadržaj svoje `.env` datoteke.

### A.3 Cron raspored ⏰
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

### A.4 Volume (pamćenje poslanih oglasa)
Railway disk je **privremen** – nakon svakog runa/deploya `data/` nestaje. Bez volumena bot ne pamti što je poslao,
pa se oslanja na datum: uzima samo oglase iz zadnjih **26 h** (malo duplikata, ali može propustiti oglas koji je izvor
objavio s kašnjenjem).

S volumenom:
1. U projektu desni klik na servis (ili ⌘K) → *Attach Volume* / *New Volume* → mount path npr. `/data`.
2. Railway sam postavi `RAILWAY_VOLUME_MOUNT_PATH=/data` – bot ga automatski koristi (`/data/seen_jobs.sqlite3`)
   i tada gleda oglase iz zadnjih **48 h** te preskače već poslane.
3. (Opcionalno) `DATA_DIR=/data` ako želiš eksplicitno.

### A.5 Test na Railwayu
- Ručni run: `railway cron run` iz Railway CLI-ja (ili redeploy servisa) – pogledaj *Logs*.
- Za testnu poruku privremeno promijeni start command u `python main.py --test-whatsapp`, deployaj, pa vrati na `python main.py`.
- Za probu bez slanja: start command `python main.py --dry-run` (poruka se ispiše u logove).

### A.6 Stalno upaljen servis (`RUN_MODE=scheduler`)
Postavi `RUN_MODE=scheduler` (i `RUN_AT=12:00`), **ne** postavljaj Cron Schedule, restart policy *Always*.
Proces stalno radi i sam čeka 12:00 po `Europe/Zagreb` (zoneinfo, DST riješen automatski).
Troši više resursa od crona, pa je cron preporučen.

---

## Sve varijable

| Varijabla | Zadano | Opis |
|---|---|---|
| `SENDER` | `callmebot` (GitHub Actions: `telegram` ako nema variable) | `callmebot` / `telegram` / `twilio` |
| `CALLMEBOT_PHONE`, `CALLMEBOT_APIKEY` | – | CallMeBot |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | – | Telegram |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `TWILIO_WHATSAPP_TO` | from: `whatsapp:+14155238886` | Twilio |
| `LLM_API_KEY` | – | bez njega: keyword filter |
| `LLM_BASE_URL` | `https://api.x.ai/v1` | bilo koji OpenAI-kompatibilni API |
| `LLM_MODEL` | `grok-4.20-non-reasoning` | |
| `JOB_CRITERIA` | Student bez iskustva, početne tech uloge, … | tekst kriterija za AI |
| `ROLE_KEYWORDS` | ugrađeni popis | zarezom odvojene uloge; prazno = zadano. Senior i dalje ispada |
| `ONSITE_CITIES` | `Zagreb, Zadar` | on-site i hybrid samo tu; prazno = zadano |
| `REMOTE_REGIONS` | EU, Europe, worldwide, Hrvatska | remote otvoren bilo gdje u EU; prazno = zadano |
| `EXCLUDED_LANGUAGES` | ugrađene fraze | zabranjeni jezik; prazno = zadano |
| `EXCLUDE_KEYWORDS` | hardware, firmware, elektro, … | riječ u naslovu izbacuje oglas; prazno = zadano |
| `MAX_RESULTS` | `8` | max oglasa po danu |
| `RUN_MODE` | `cron` | `cron` / `scheduler` |
| `RUN_AT` | `12:00` | vrijeme za scheduler mod |
| `ONLY_AT_LOCAL_HOUR` | – | samo Railway: npr. `12` uz cron `0 10,11 * * *`. Na Actionsima nemoj (odgođeni run bi preskočio dan) |
| `TZ_NAME` | `Europe/Zagreb` | |
| `DATA_DIR` | `RAILWAY_VOLUME_MOUNT_PATH` ili `./data` | gdje je SQLite baza |
| `MAX_AGE_HOURS` | 48 (s volumenom) / 26 (bez) | koliko stari oglasi |
| `DISABLED_SOURCES` | – | npr. `himalayas,mojposao_hr` |

## Struktura
```
main.py                          CLI: --dry-run, --test-whatsapp, --sender, --mode, --telegram-chat-id
webapp.py                        Telegram webhook (FastAPI) za Render
render.yaml                      Render Blueprint, free plan
jobbot/sources.py                izvori oglasa (svaki izoliran)
jobbot/ranking.py                keyword filter + LLM rangiranje
jobbot/formatter.py              poruka na hrvatskom + dijeljenje na dijelove
jobbot/senders.py                CallMeBot / Twilio / Telegram
jobbot/store.py                  SQLite pamćenje poslanih oglasa
.github/workflows/daily-job-bot.yml   dnevni GitHub Actions raspored + ručni test
.github/workflows/keepalive.yml       tjedni commit da GitHub ne ugasi schedule (60 dana)
.github/scripts/should_send.py        točno jedno slanje po zagrebačkom danu
```

## Poznata ograničenja
- Svježih oglasa „za početnike“ zna biti malo (posebno vikendom) – tada stigne poruka *„Danas nema novih oglasa…“*.
- GitHub Actions cache nije pravi disk: ako ga GitHub obriše, sljedeći run može ponoviti oglase iz zadnjih 48 h. Zakazani workflow radi samo na `main`. U javnom repou GitHub ugasi schedule nakon 60 dana bez aktivnosti (vidi odjeljak 4.5).
- Keyword filter je grub: pokriva i analitiku, QA, podršku i DevOps, pa ponekad propusti srodan oglas
  (npr. općenita „podrška“). Ako nema dovoljno jasnih junior oglasa, dopuni ih ne-senior oglasima bez traženih
  godina iskustva (označeno s „provjeri uvjete“). Senior/lead/manager i dalje ispadaju. AI način je precizniji.
- MojPosao.hr koristi nedokumentirani endpoint; ako se promijeni, izvor se samo preskoči (vidi log).
- Remote oglasi ograničeni na druge države (npr. „United States“) se izbacuju; „Remote“ oglasi s Arbeitnowa
  često traže njemački ili boravak u DE/CH – AI ih ocjenjuje niže.
- Molimo poštuj uvjete izvora (RemoteOK/Jobicy traže navođenje izvora – linkovi vode na njihove stranice).
