# certiPass.md — 90 de postări Instagram

Acest repository publică **un carusel cu două imagini și două cadre Story pe zi**, la **18:00, ora Chișinăului**. Butonul **Actions → Post today / Daily 18:00 → Run workflow** publică următoarea zi imediat. Dacă ai publicat deja caruselul în ziua curentă, butonul publică doar cadrele Story lipsă. Dacă toate sunt publicate, nu le dublează.

## Configurare înainte de prima postare

1. În **Settings → Secrets and variables → Actions → Secrets**, adaugă `META_ACCESS_TOKEN`: tokenul Instagram User obținut prin **Instagram API with Instagram Login**, cu `instagram_business_basic` și `instagram_business_content_publish`. Nu îl scrie în README, cod sau chat.
2. În aceeași pagină, la **Variables**, adaugă `IG_USER_ID` (ID-ul numeric al contului Instagram) și `MEDIA_BASE_URL` (adresa publică a folderului cu imaginile JPEG, fără `/` final): `https://raw.githubusercontent.com/Ion08/certipass-instagram-maker/main/images`.
3. Imaginile caruselului trebuie să existe public la `MEDIA_BASE_URL/day-001-01.jpg`, `...-02.jpg` până la `day-090-02.jpg`. Cele două cadre Story folosesc fișierele `day-XXX-01-story.jpg` și `day-XXX-02-story.jpg`, în format vertical 1080×1920, fără decuparea slide-urilor. Meta descarcă imaginile de la aceste adrese când creează postarea.
4. Deschide **Actions → Post today / Daily 18:00 → Run workflow** pentru prima postare. Verifică rezultatul în Instagram și în sumarul workflow-ului.
5. Când vrei să înceapă publicarea zilnică, setează variabila `PUBLISH_ENABLED` la `true`. Până atunci, programarea zilnică nu publică nimic.

Tokenul trebuie să fie **long-lived** și neexpirat când îl instalezi. Workflow-ul îl reînnoiește după 30 de zile și păstrează versiunea nouă criptată în `data/token.enc`; cheia este derivată din secretul inițial, care rămâne în GitHub Secrets. Nu modifica secretul inițial fără să refaci și tokenul criptat.

## Cum funcționează

- `data/posts.json` conține descrierile celor 90 de zile, în ordinea din documentul campaniei.
- `data/state.json` reține ziua următoare, caruselul și Story-ul fiecărei zile. Story-ul folosește ambele variante verticale ale caruselului (`day-XXX-01-story.jpg` și `day-XXX-02-story.jpg`). Workflow-ul actualizează istoricul după fiecare publicare.
- Dacă un job se reia după ce Instagram a publicat deja, programul verifică descrierile recente și evită dublarea caruselului. Fiecare cadru Story are propriul ID și nu se republică atunci când există deja. Dacă răspunsul Meta pentru un cadru este incert, programul oprește relansarea acelui cadru până la verificare manuală.
- `make_story_assets.py` generează variantele verticale din slide-urile originale fără a le decupa. Pentru prima zi, butonul manual oferă opțiunea `correct_day_1_story`, care publică doar cele două cadre corectate, fără un nou carusel.
- Programarea este zilnică la 18:00 în `Europe/Chisinau`; GitHub Actions poate porni uneori cu întârziere.
- Pentru a opri automatizarea, schimbă `PUBLISH_ENABLED` la `false`. Butonul manual rămâne disponibil.

## Linkuri utile

- [Instagram API cu Instagram Login — Meta](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login)
- [Programarea workflow-urilor — GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule)
- [Secrets în GitHub Actions](https://docs.github.com/en/actions/reference/security/secrets)
