# pse-priv

Demo FastAPI + GitHub Actions: prywatne repo rozwojowe z auto-bumpem `.devN` i lustrem wydań do [pse-pub](https://github.com/pythonms/pse-pub) przy każdym squash-merge na `main` (konfiguracja **A**).

Szczegóły modelu: [docs/workflows/config-A-mirror-auto.md](docs/workflows/config-A-mirror-auto.md).  
Porównanie A vs B (Mermaid): [docs/plans/porownanie-1A2A-vs-1B2B.plan.md](docs/plans/porownanie-1A2A-vs-1B2B.plan.md).

## Community

- [Contributing](CONTRIBUTING.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)
- [License (MIT)](LICENSE)
- [Changelog](CHANGELOG.md)

## Remotes (stacja robocza)

Dwa remote’y, żeby tagi deweloperskie i wydaniowe nie kolidowały w jednym namespace:

```sh
git remote -v
# origin  → github.com/pythonms/pse-priv   (prywatne: gałęzie + tagi .dev*)
# public  → github.com/pythonms/pse-pub    (publiczne: tylko main + czyste vX.Y.Z)

# jeśli brakuje public:
git remote add public git@github.com:pythonms/pse-pub.git
```

| Remote | Repo | Gałęzie | Tagi |
|--------|------|---------|------|
| `origin` | pse-priv | `dev`, `main` | `vX.Y.Z.devN` (checkpointy) oraz `vX.Y.Z` (main) |
| `public` | pse-pub | `main` | tylko czyste `vX.Y.Z` — **nigdy** `.dev*` |

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
2. Każdy push na `dev` (oprócz `chore(bump):`) **podbija** `__version__.py` do PEP 440 `.devN` i stawia tag `vX.Y.Z.devN` **tylko na origin** (priv; nigdy na public).
3. Opcjonalnie ten sam checkpoint ręcznie: Actions → Dev Pipeline → Run workflow, albo
   `gh workflow run "Dev Pipeline" --ref dev -f create_dev_tag=true`.
4. Push na `dev` otwiera/aktualizuje automatyczny PR `dev` → `main`.
5. Przed merge **edytuj tytuł PR** — opis squasha do `CHANGELOG`.
6. **Squash merge** PR na `main`.
7. Workflow na `main`:
   - jeśli HEAD ma już czysty tag `vX.Y.Z` → używa go (bez ponownego tagowania)
   - w przeciwnym razie zdejmuje `.devN` → finalne `X.Y.Z`, CHANGELOG, tag na origin
   - buduje wheel + obraz, sync do `pse-pub` **tylko** z czystym tagiem (bez `.dev*`)

W ustawieniach repo:

- tylko **Allow squash merging** (+ kasowanie gałęzi po merge)
- Squash commit message = **Pull request title**

## Sekret

`PUBLISH_TOKEN` — PAT z `contents:write` do `pythonms/pse-pub`.

## Wersja

Jedyny plik wersji: `__version__.py` (PEP 440: `X.Y.Z` albo `X.Y.Z.devN`).
Tagi `.dev*` tylko na **origin** i tylko jako świadome checkpointy; na **public** wyłącznie `vX.Y.Z`.
