# pse-priv

Prywatne repozytorium rozwojowe. Publiczne lustro ląduje w [pse-pub](https://github.com/pythonms/pse-pub) przy każdym squash-merge na `main` (konfiguracja **A**: auto-bump + sync).

Szczegóły modelu: [docs/workflows/config-A-mirror-auto.md](docs/workflows/config-A-mirror-auto.md) · diagramy: [docs/plans/diagrams/](docs/plans/diagrams/).

## Uruchomienie przez Docker Compose

```sh
docker compose up --build
```

API: http://localhost:8000 · Swagger: http://localhost:8000/docs


## Smoke endpoints

- `GET /` — powitanie
- `GET /health` — liveness
- `GET /version` — wersja pakietu

## Codzienny rytm

1. Feature branch → PR → `dev` (CI + obraz GHCR `:dev`).
2. Gdy gotowe: PR `dev` → `main`, **squash merge**.
3. Tytuł / wiadomość squash (conventional commits):
   - `fix:` / inne → **patch**
   - `feat:` → **minor**
   - `feat!:` albo `BREAKING CHANGE:` → **major**
4. Workflow na `main`:
   - podbija `__version__.py` do `X.Y.Z`
   - dopisuje wpis do `CHANGELOG.md` (Features / Bug Fixes / Breaking…)
   - taguje `vX.Y.Z`
   - buduje wheel + obraz (`latest`, `vX.Y.Z`)
   - synchronizuje drzewo do `pse-pub` (kod + changelog + `wheels/*.whl`)
   - dokłada ten sam `.whl` do GitHub Release na `pse-pub`

Na `dev` workflow buduje wheel i wrzuca go jako artifact Actions (`package-wheel-dev`); na pub wheel trafia dopiero po wejściu na `main`.

W ustawieniach repo zostaw tylko **squash merge** i kasowanie gałęzi po merge.

## Publikacja do `pse-pub`

W environment Actions **`public-publish`**:

- preferowane: `PUBLISH_APP_ID` + `PUBLISH_APP_PRIVATE_KEY` (GitHub App na `pythonms/pse-pub`)
- fallback: `PUBLISH_TOKEN` (PAT z `contents:write`). Bez credentials job sync kończy się błędem.

## Wersja

Jedyny plik wersji: `__version__.py` (format `X.Y.Z`). Na `dev` nie tworzymy tagów `v*`.
