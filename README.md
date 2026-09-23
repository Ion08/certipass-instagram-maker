# certiPass Instagram Maker

Instrument local-first pentru documentare, redactare și randarea unui Reel vertical pentru contul certiPass.md. Textul este generat de Codex CLI autentificat cu ChatGPT; nu citește `OPENAI_API_KEY` și nu cheamă OpenAI Platform API. Grafica este construită local din tipografie și forme, iar videoclipul este H.264, 9:16. Publicarea Meta este o comandă separată, oprită implicit.

## Ce poate face acum

- citește paginile curente certiPass.md și câteva documentații tehnice primare;
- cere Codex CLI să creeze scenariul în română, cu surse limitate la paginile citite;
- verifică formatul de bază și blochează sursele neincluse în cercetare;
- ține o evidență atomică a zilelor și respinge duplicatele apropiate;
- redă un MP4 1080×1920 local, fără API-uri de imagini/video;
- trimite conținutul către Instagram doar prin fluxul oficial Meta, cu mai multe verificări explicite.

Randarea actuală este un Reel animat, numai cu text și grafică simplă, fără voce sau muzică. Verificarea automată nu înlocuiește revizia vizuală și factuală de către o persoană.

## Rulare locală

Necesită Python 3.11+, ffmpeg/ffprobe și Codex CLI autentificat prin „Sign in with ChatGPT”. Instalarea Codex CLI și autentificarea se fac separat, prin instrucțiunile oficiale OpenAI.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
certipass-instagram draft
```

Fișierele apar în `artifacts/`; evidența locală este `data/ledger.json`. `draft` nu publică nimic și nu trimite secrete către Codex. Deschide MP4-ul și JSON-ul înainte de a marca o postare ca pregătită:

```sh
certipass-instagram approve reel-YYYY-MM-DD
```

## Meta și publicarea

Pentru Instagram Login, configurarea citește `INSTAGRAM_USER_ID`, `INSTAGRAM_ACCESS_TOKEN` și `META_GRAPH_API_VERSION` din variabile de mediu. Folosește numai permisiunile de care are nevoie aplicația ta, inclusiv `instagram_business_basic` și `instagram_business_content_publish`. Nu trimite tokenul în chat, nu-l pune în Git și nu-l include în capturi de ecran. Păstrează-l într-un manager de secrete.

Pentru ca Meta să proceseze Reel-ul, MP4-ul trebuie să fie disponibil prin HTTPS public în momentul cererii. Acest proiect nu configurează încă un serviciu de găzduire media. Nu folosi URL-uri locale, linkuri Drive private sau URL-uri temporare expirate.

Publicarea rămâne oprită până când sunt setate ambele variabile `INSTAGRAM_PUBLISH_ENABLED=true` și `INSTAGRAM_APP_LIVE_APPROVED=true`, utilizatorul transmite `--confirm-publish`, postarea este marcată `READY`, iar un MP4 găzduit public este furnizat prin `--media-url`. Dacă Meta răspunde ambiguu, ledger-ul blochează repetarea automată până la verificarea manuală a contului.

Aplicația Meta văzută în configurarea certiPass este încă în modul de testare, iar permisiunile erau „Ready for testing”. Asta nu demonstrează accesul de producție ori aprobarea App Review. Nu activa publicarea regulată înainte de a confirma cerințele Meta și de a trece app review-ul cerut.

## ChatGPT Plus și GitHub Actions

Fluxul programat folosește `codex exec` autentificat prin contul ChatGPT. Acesta folosește limita de utilizare a planului ChatGPT; nu cere `OPENAI_API_KEY` și nu folosește facturarea OpenAI Platform. OpenAI documentează un flux avansat pentru autentificare personală în CI: runner-ul citește `auth.json`, Codex reîmprospătează sesiunea în timpul unei rulări, iar fișierul actualizat este păstrat înapoi în secret manager. Documentația recomandă autentificarea API pentru automatizări în general; fluxul de abonament este descris pentru infrastructură privată și de încredere. Acest repository este privat.

Workflow-ul `daily-draft.yml` este oprit implicit. Pentru activarea generării zilnice:

1. Pe computerul tău de încredere, configurează Codex CLI să folosească stocare în fișier și autentifică-te cu ChatGPT. `auth.json` trebuie tratat ca o parolă; nu îl trimite în conversație.
2. În setările repository-ului privat, adaugă `CODEX_AUTH_JSON` cu conținutul fișierului `~/.codex/auth.json`.
3. Creează un token fine-grained limitat doar la acest repository, cu dreptul de actualizare a Actions secrets; salvează-l ca `CODEX_SECRET_WRITE_TOKEN`. Workflow-ul îl folosește numai pentru a înlocui `CODEX_AUTH_JSON` cu tokenurile Codex actualizate.
4. Creează repository variable `ENABLE_DAILY_DRAFTS=true`. Cron-ul rulează zilnic la 07:23, ora Chișinăului, și pune JSON-ul și MP4-ul într-un artifact privat pentru revizie.

`auth.json` nu este pus în cache, loguri, artifacts sau în Git. Pentru a respecta limita sesiunii rotate, rulările sunt serializate și actualizează secretul; dacă sesiunea e revocată, va trebui să o autentifici din nou și să înlocuiești secretul. Workflow-ul nu publică nimic pe Instagram.

## Verificare

```sh
PYTHONPATH=src python -m pytest -q
```

Testele folosesc sesiuni și răspunsuri Meta false; nu creează postări publice. Renderer-ul necesită `ffmpeg` și `ffprobe` instalate. Generarea locală prin ChatGPT Plus a fost verificată o dată; fluxul GitHub trebuie activat numai după ce cele două secrete și variabila de mai sus sunt configurate.
