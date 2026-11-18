# pse-priv

Prywatne repozytorium rozwojowe. Publiczne lustro ląduje w [pse-pub](https://github.com/pythonms/pse-pub) przy każdym squash-merge na `main` (konfiguracja **A**: auto-bump + sync).

Szczegóły modelu: [docs/workflows/config-A-mirror-auto.md](docs/workflows/config-A-mirror-auto.md).  
Porównanie A vs B (Mermaid): [docs/plans/porownanie-1A2A-vs-1B2B.plan.md](docs/plans/porownanie-1A2A-vs-1B2B.plan.md).

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
2. Każdy push na `dev` (oprócz `chore(bump):`) **podbija** `__version__.py` z conventional commits:
   - `fix:` / inne → **patch**
   - `feat:` → **minor**
   - `feat!:` albo `BREAKING CHANGE:` → **major**
3. Push na `dev` otwiera/aktualizuje automatyczny PR `dev` → `main` (lista commitów w body).
4. Przed merge **edytuj tytuł PR** — opis squasha do `CHANGELOG` (nie zmienia numeru wersji).
5. **Squash merge** PR na `main`.
6. Workflow na `main`:
   - bierze wersję już z `__version__.py` (najwyższa z `dev`)
   - dopisuje wpis do `CHANGELOG.md` z tytułu PR
   - taguje `vX.Y.Z`
   - buduje wheel + obraz (`latest`, `vX.Y.Z`)
   - synchronizuje drzewo do `pse-pub` (kod + changelog + `wheels/*.whl`)
   - dokłada ten sam `.whl` do GitHub Release na `pse-pub`

Na `dev` workflow buduje wheel i wrzuca go jako artifact Actions (`package-wheel-dev`); na pub wheel trafia dopiero po wejściu na `main`.

W ustawieniach repo:

- tylko **Allow squash merging** (+ kasowanie gałęzi po merge)
- Squash commit message = **Pull request title** (tytuł PR → changelog / opis release)

## Sekret

`PUBLISH_TOKEN` — PAT z `contents:write` do `pythonms/pse-pub`. Bez niego job release/sync kończy się błędem.

## Wersja

Jedyny plik wersji: `__version__.py` (format `X.Y.Z`). Numer rośnie na **`dev`** przy każdym pushu; na **`main`** release = ta sama (najwyższa) wersja z merga. Tagi `v*` tylko na `main`.
