# Bot Ruch Wolnych Polaków – posiedzenia

Jedna komenda: **`/posiedzenie data godzina temat wydarzenie [opis]`**

- ogłoszenie z pingiem rangi trafia na kanał ogłoszeń (embed + przyciski Będę / Nie wiem / Spóźnię się / Nie będę),
- w tej samej chwili każdy z rangi dostaje PV z linkami (wydarzenie, podium, Roblox) i przyciskami,
- odpowiedź można wybrać **tylko raz** (na kanale albo w PV, decyzji nie da się zmienić),
- godzinę i 15 minut przed startem bot wysyła przypomnienie na PV: osobom, które wybrały Będę / Nie wiem / Spóźnię się (bez przycisków) oraz tym, które jeszcze nie odpowiedziały (z przyciskami). „Nie będę" nie dostają nic,
- wszystko (utworzenie, odpowiedzi, wyniki wysyłki PV, przypomnienia) idzie na kanał logów.

## Domyślne ID (config.py, można nadpisać zmiennymi)
| Zmienna | Domyślnie | Do czego |
|---|---|---|
| `PING_ROLE_ID` | 1523301940853870653 | ranga pingowana w ogłoszeniu i odbiorcy PV |
| `COMMAND_ROLE_ID` | 1523301940853870653 | kto może użyć komendy (ranga albo użytkownik o tym ID) |
| `ANNOUNCE_CHANNEL_ID` | 1523311020117065888 | kanał ogłoszeń |
| `LOG_CHANNEL_ID` | 1523326084106682369 | kanał logów |

Stałe linki: `PODIUM_URL`, `ROBLOX_URL`, nazwa partii: `PARTY_NAME`.

## Discord Developer Portal
1. New Application → Bot → **Reset Token** (token do `DISCORD_TOKEN`).
2. W zakładce Bot włącz **Server Members Intent**.
3. OAuth2 → URL Generator: scopes `bot` + `applications.commands`; uprawnienia: View Channels, Send Messages, Embed Links, Read Message History, **Mention @everyone, @here and All Roles** (potrzebne do pingu rangi).
4. Bot musi widzieć kanał ogłoszeń i kanał logów.

## GitHub
```bash
git init
git add .
git commit -m "Bot posiedzen"
git branch -M main
git remote add origin https://github.com/TWOJ_LOGIN/rwp-bot.git
git push -u origin main
```
Repo najlepiej **Private**. Pliku `.env` nie ma w repo (jest w `.gitignore`).

## Railway
1. New Project → Deploy from GitHub repo → wybierz repo.
2. Variables: `DISCORD_TOKEN`, `GUILD_ID` (ID serwera partii), `DATA_DIR=/data`.
3. **Volume** z Mount path `/data` (bez tego po każdym deployu znikną posiedzenia i odpowiedzi).
4. Start z `Procfile` (`python main.py`). W logach ma być `Zalogowano jako ...` i `Zsynchronizowano 1 komend`.
5. Aktualizacje: `git push`, Railway sam wdroży.

## Uwagi
- Czas to zawsze Europe/Warsaw.
- PV nie dojdzie osobom z zablokowanymi wiadomościami od członków serwera, bot wypisze je na kanale logów.
- Dane posiedzeń są usuwane 7 dni po terminie.
