# certiPass Instagram Maker

Automatizare pentru postări statice Instagram certiPass.md: postări cu o imagine sau carusele de 4–6 imagini. Fiecare slide final este un fișier PNG 4:5 cu artwork generat de GPT Image 2 și copy românesc redat exact peste artwork. Nu creează Reels, videoclipuri, pagini HTML sau capturi de ecran.

Textul, subiectul și prompturile vizuale sunt pregătite cu Codex CLI autentificat prin ChatGPT. Artwork-ul este generat separat prin OpenRouter, folosind modelul openai/gpt-image-2, iar imaginile rezultate sunt compuse în PNG-uri statice. OpenRouter se plătește separat; abonamentul ChatGPT Plus nu acoperă aceste cereri.

## Fluxul actual

- verifică surse pentru afirmații educaționale și reguli factuale;
- cere Codex să redacteze o postare românească și prompturile pentru fiecare slide;
- generează artwork PNG prin OpenRouter;
- așază textul românesc peste artwork și salvează imaginile 1080×1350;
- ține evidența subiectelor și oferă artefactele pentru revizie;
- publicarea Meta rămâne dezactivată implicit și cere găzduire publică HTTPS pentru fiecare PNG.

## Costul imaginilor

Exemplul curent din documentația OpenRouter pentru o imagine 1536×864 la calitate high raportează $0.13; costul variază în funcție de rezoluție și de utilizarea efectivă. Ca ordin de mărime, cinci imagini la acel tarif ar costa aproximativ $0.65 per carusel, sau $19.50 pentru 30 de carusele cu câte cinci slide-uri. Verifică întotdeauna costul afișat în activitatea OpenRouter după o rulare reală.

Setează o limită de cheltuieli în contul OpenRouter. Workflow-ul produce cel mult șase slide-uri într-o rulare și se oprește când OpenRouter raportează credite insuficiente ori o limită de utilizare.

## Rulare locală

Necesită Python 3.11+, Codex CLI autentificat cu ChatGPT, OPENROUTER_API_KEY și conexiune la internet. Nu trimite chei API în chat, capturi de ecran sau Git. Configurează cheia numai în variabile de mediu locale ori în secretele repository-ului.

Comenzile sunt: creează și activează un mediu virtual Python, instalează proiectul cu dependențele de test, setează OPENROUTER_API_KEY și rulează certipass-instagram draft. Draftul JSON și imaginile PNG apar în directorul artifacts. Comanda draft nu publică.

## GitHub Actions

Workflow-ul zilnic este oprit implicit. Pentru drafturi programate într-un repository privat:

1. Revocă imediat orice cheie OpenRouter pe care ai trimis-o într-o conversație și creează una nouă.
2. Adaugă cheia nouă ca repository Actions secret OPENROUTER_API_KEY.
3. Configurează autentificarea Codex/ChatGPT documentată pentru workflow folosind secretul CODEX_AUTH_JSON și mecanismul de rotație existent CODEX_SECRET_WRITE_TOKEN.
4. Setează repository variable ENABLE_DAILY_DRAFTS=true.
5. O rulare manuală sau programată va încărca PNG-urile ca artifact privat pentru revizie.

Nu scrie cheia API într-un fișier tracked și nu o pune în URL-uri ori loguri.

## Meta și publicare

Publicarea Instagram rămâne închisă până când app-ul Meta are permisiunile și aprobările necesare și PNG-urile sunt găzduite la URL-uri HTTPS publice pe care Meta le poate descărca. Repository-ul nu setează încă găzduirea publică a imaginilor. Pentru carusel, fiecare slide trebuie să aibă propriul URL HTTPS.

După configurarea găzduirii, folosește clientul oficial Meta cu INSTAGRAM_USER_ID, INSTAGRAM_ACCESS_TOKEN și META_GRAPH_API_VERSION. Publicarea cere suplimentar confirmarea explicită, draft marcat READY și variabilele INSTAGRAM_PUBLISH_ENABLED=true și INSTAGRAM_APP_LIVE_APPROVED=true. Nu pune tokenul Meta în Git sau în chat.

## Verificare

Rulează testele cu PYTHONPATH=src python -m pytest -q.

Testele folosesc răspunsuri sintetice/mock și nu cheamă OpenRouter ori Meta și nu creează postări publice. O rulare reală de generare consumă credite OpenRouter.
