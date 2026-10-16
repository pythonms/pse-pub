# pse-priv

Prywatne repozytorium rozwojowe. Publiczne wydanie ląduje w [pse-pub](https://github.com/pythonms/pse-pub) jako snapshot plików, bez historii z tego repozytorium.

## Uruchomienie przez Docker Compose

Uruchom aplikację poleceniem:

```sh
docker compose up --build
```

API będzie dostępne pod adresem http://localhost:8000, a dokumentacja Swagger UI pod http://localhost:8000/docs.

## Wersja na `dev`

Workflow publikuje obraz Dockera i artefakt wheel przy zmianach na gałęziach `main` i `dev`. Na `main` uruchamia również Release Please oraz synchronizację do publicznego repozytorium.

Każdy push na `dev` dostaje nową wersję i otwiera albo aktualizuje pull request z `dev` do `main`. Tytuł to `dev: X.Y.Z.devN`. Domyślnie podbijany jest patch, `feat:` podbija minor, a `!` lub `BREAKING CHANGE:` podbija major. Workflow zapisuje wersję wheel jako `X.Y.Z.devN` w `__version__.py`, aktualizuje manifest Release Please, publikuje wheel jako artefakt workflow (z 14-dniową retencją) i tworzy tag Git `vX.Y.Z`. Nie publikuje wheel’a do PyPI. Numer użyty na `dev` jest zarezerwowany, więc stabilne wydanie powinno użyć następnego numeru. Tagowane jest automatyczne zatwierdzenie zmiany wersji.

Aby włączyć synchronizację publiczną, ustaw zmienną repozytorium `PUBLIC_REPOSITORY` w formacie `właściciel/repozytorium` oraz sekret `PUBLIC_REPO_TOKEN` (https://github.com/settings/personal-access-tokens) Jeszcze dodajemy R/W dla PR do tokena, z uprawnieniami `contents: write` i `pull requests: write` w repozytorium docelowym. Jeśli zmienna nie jest ustawiona, krok synchronizacji jest pomijany.

## Wydanie na `main`

`VERSION` na `main` ma postać `X.Y.Z-dev`. Zwykły PR zostawia ten numer bez zmian.

Tytuł PR opisuje zmianę. Squash-merge do `main`. Tytuł nie może być samym numerem wersji.

W ustawieniach repozytorium zostaw tylko squash merge i kasowanie gałęzi po merge.

PR wydania spełnia cztery warunki:

- tytuł `release: 1.5.0`
- `VERSION` równy `1.5.0`
- w `CHANGELOG.md` nagłówek `## [1.5.0]`
- w opisie linia `Next-dev: 1.5.1-dev` z wyższym numerem

Po squash-merge workflow taguje `v1.5.0` tutaj, commituje drzewo plików na `main` w `pse-pub` (rodzicem jest poprzednie wydanie publiczne, nie commit z tego repo) i ustawia `VERSION` na `main` na wartość z `Next-dev`.

Sekret `PUBLISH_TOKEN` to PAT z uprawnieniem contents:write do `pythonms/pse-pub`. GitHub Actions musi móc wypchnąć commit z podbiciem wersji na `main`.
==
Pewne zmiany 3.0

