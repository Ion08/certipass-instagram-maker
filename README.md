# certiPass.md — 90 de postări Instagram

Acest repository publică **un carusel cu două imagini pe zi**, la **18:00, ora Chișinăului**. Butonul **Actions → Post today / Daily 18:00 → Run workflow** publică următoarea zi imediat. Dacă postarea zilei curente există deja, nu o dublează.

## Configurare

1. În **Settings → Secrets and variables → Actions → Secrets**, păstrează `META_ACCESS_TOKEN`: tokenul Instagram User obținut prin **Instagram API with Instagram Login**, cu `instagram_business_basic` și `instagram_business_content_publish`. Nu îl scrie în cod sau chat.
2. La **Variables**, păstrează `IG_USER_ID` și `MEDIA_BASE_URL`: `https://raw.githubusercontent.com/Ion08/certipass-instagram-maker/main/images`.
3. Caruselele folosesc imaginile `day-001-01.jpg` și `day-001-02.jpg`, până la ziua 90.
4. Pentru programarea zilnică, setează `PUBLISH_ENABLED` la `true`. Butonul manual este disponibil separat.

Tokenul long-lived se reînnoiește după 30 de zile și versiunea nouă se păstrează criptată în `data/token.enc`; cheia provine din secretul inițial din GitHub Secrets.

## Story

Automatizarea **nu publică fotografii în Story**. Cerința este să distribui postarea din feed în Story, cu postarea apăsabilă. Acțiunea **„Distribuie în poveste”** se face din aplicația Instagram; API-ul oficial folosit aici nu oferă această acțiune. Pentru fiecare postare: deschide caruselul pe Instagram → apasă pictograma de distribuire → **Adaugă în poveste** → **Distribuie**.

Fișierele verticale `*-story.jpg` create anterior nu sunt folosite de automatizare.

## Cum funcționează

- `data/posts.json` conține descrierile celor 90 de zile.
- `data/state.json` reține ziua următoare și istoricul publicării.
- Programarea rulează zilnic la 18:00 în `Europe/Chisinau`; GitHub Actions poate porni cu întârziere.
- Pentru a opri programarea, schimbă `PUBLISH_ENABLED` la `false`.

## Linkuri

- [Instagram API cu Instagram Login — Meta](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login)
- [Programarea workflow-urilor — GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule)
