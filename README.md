# certiPass.md — 90 de postări Instagram

Acest repository publică **un carusel cu două imagini pe zi**, la **18:00, ora Chișinăului**. Butonul **Actions → Post today / Daily 18:00 → Run workflow** publică următoarea zi imediat. Dacă ai publicat deja în ziua curentă, butonul nu dublează postarea.

## Configurare înainte de prima postare

1. În **Settings → Secrets and variables → Actions → Secrets**, adaugă `META_ACCESS_TOKEN`: tokenul Instagram User obținut prin **Instagram API with Instagram Login**, cu `instagram_business_basic` și `instagram_business_content_publish`. Nu îl scrie în README, cod sau chat.
2. În aceeași pagină, la **Variables**, adaugă `IG_USER_ID` (ID-ul numeric al contului Instagram) și `MEDIA_BASE_URL` (adresa publică a folderului cu imaginile JPEG, fără `/` final). Exemplu: `https://raw.githubusercontent.com/OWNER/PUBLIC-ASSET-REPO/main/images`.
3. Imaginile trebuie să existe public la `MEDIA_BASE_URL/day-001/01.jpg`, `.../02.jpg` până la `day-090/02.jpg`. Meta descarcă imaginile de la aceste adrese când creează postarea. Repository-ul acesta poate rămâne privat.
4. Deschide **Actions → Post today / Daily 18:00 → Run workflow** pentru prima postare. Verifică rezultatul în Instagram și în sumarul workflow-ului.
5. Când vrei să înceapă publicarea zilnică, setează variabila `PUBLISH_ENABLED` la `true`. Până atunci, programarea zilnică nu publică nimic.

## Cum funcționează

- `data/posts.json` conține descrierile celor 90 de zile, în ordinea din documentul campaniei.
- `data/state.json` reține ziua următoare și istoricul. Workflow-ul îl actualizează după publicare.
- Dacă un job se reia după ce Instagram a publicat deja, programul verifică descrierile recente și evită dublarea.
- Programarea este zilnică la 18:00 în `Europe/Chisinau`; GitHub Actions poate porni uneori cu întârziere.
- Pentru a opri automatizarea, schimbă `PUBLISH_ENABLED` la `false`. Butonul manual rămâne disponibil.

## Linkuri utile

- [Instagram API cu Instagram Login — Meta](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login)
- [Programarea workflow-urilor — GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule)
- [Secrets în GitHub Actions](https://docs.github.com/en/actions/reference/security/secrets)
