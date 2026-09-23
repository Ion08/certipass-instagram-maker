# certiPass Instagram Maker

Automatizare pentru trei postări statice Instagram certiPass.md în fiecare zi: un meme, o postare educativă și una informativă. Fiecare este o imagine PNG 4:5 cu artwork generat de GPT Image 2 și copy românesc redat exact peste artwork. Nu creează Reels, videoclipuri, pagini HTML sau capturi de ecran.

Textul, subiectul și prompturile vizuale sunt pregătite cu Codex CLI autentificat prin ChatGPT. Artwork-ul este generat separat prin OpenRouter, folosind modelul openai/gpt-image-2, iar imaginile rezultate sunt compuse în PNG-uri statice. OpenRouter se plătește separat; abonamentul ChatGPT Plus nu acoperă aceste cereri.

## Fluxul actual

- verifică surse pentru afirmații educaționale și reguli factuale;
- cere Codex să redacteze toate cele trei formate într-un singur apel: meme, educativ și informativ;
- compară subiectele, formulările, personajele și motivele vizuale cu ultimele 90 de postări salvate;
- păstrează aceeași familie vizuală pastel (ivory, lavandă, albastru pudrat, mentă, piersică și bleumarin), variind personajul, scena și compoziția fiecărei imagini;
- generează artwork PNG prin OpenRouter;
- așază textul românesc peste artwork și salvează trei imagini distincte, 1080×1350;
- ține evidența subiectelor și oferă artefactele pentru revizie;
- publicarea Meta rămâne dezactivată implicit și cere găzduire publică HTTPS pentru fiecare PNG.

## Costul imaginilor

Exemplul curent din documentația OpenRouter pentru o imagine 1536×864 la calitate high raportează $0.13; costul variază în funcție de rezoluție și de utilizarea efectivă. Trei imagini la acel tarif ar fi aproximativ $0.39 pe zi sau $11.70 pentru 30 de zile. Verifică activitatea și tariful efectiv în OpenRouter după primele rulări.

Setează o limită de cheltuieli în contul OpenRouter. Workflow-ul produce exact trei imagini într-o rulare și se oprește când OpenRouter raportează credite insuficiente ori o limită de utilizare.

## Rulare locală

Necesită Python 3.11+, Codex CLI autentificat cu ChatGPT, OPENROUTER_API_KEY și conexiune la internet. Nu trimite chei API în chat, capturi de ecran sau Git. Configurează cheia numai în variabile de mediu locale ori în secretele repository-ului.

Comenzile sunt: creează și activează un mediu virtual Python, instalează proiectul cu dependențele de test, setează OPENROUTER_API_KEY și rulează certipass-instagram draft. Draftul JSON și imaginile PNG apar în directorul artifacts. Comanda draft nu publică.

## GitHub Actions

Workflow-ul zilnic este oprit implicit. Pentru cele trei drafturi zilnice într-un repository privat:

1. Revocă imediat orice cheie OpenRouter pe care ai trimis-o într-o conversație și creează una nouă.
2. Adaugă cheia nouă ca repository Actions secret OPENROUTER_API_KEY.
3. Configurează autentificarea Codex/ChatGPT documentată pentru workflow folosind secretul CODEX_AUTH_JSON și mecanismul de rotație existent CODEX_SECRET_WRITE_TOKEN.
4. Setează repository variable ENABLE_DAILY_DRAFTS=true.
5. O rulare manuală sau programată va încărca cele trei PNG-uri și fișierele JSON ca artifact privat pentru revizie.

Nu scrie cheia API într-un fișier tracked și nu o pune în URL-uri ori loguri.

## Meta și publicare

Publicarea Instagram rămâne închisă până când app-ul Meta are permisiunile și aprobările necesare și PNG-urile sunt găzduite la URL-uri HTTPS publice pe care Meta le poate descărca. Repository-ul nu setează încă găzduirea publică a imaginilor. Pentru carusel, fiecare slide trebuie să aibă propriul URL HTTPS.

După configurarea găzduirii, folosește clientul oficial Meta cu INSTAGRAM_USER_ID, INSTAGRAM_ACCESS_TOKEN și META_GRAPH_API_VERSION. Publicarea cere suplimentar confirmarea explicită, draft marcat READY și variabilele INSTAGRAM_PUBLISH_ENABLED=true și INSTAGRAM_APP_LIVE_APPROVED=true. Nu pune tokenul Meta în Git sau în chat.

## Verificare

Rulează testele cu PYTHONPATH=src python -m pytest -q.

Testele folosesc răspunsuri sintetice/mock și nu cheamă OpenRouter ori Meta și nu creează postări publice. O rulare reală de generare consumă credite OpenRouter.
