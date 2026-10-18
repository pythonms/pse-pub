# pse-priv

Prywatne repozytorium rozwojowe. Publiczne lustro ląduje w [pse-pub](https://github.com/pythonms/pse-pub) przy każdym squash-merge na `main` (konfiguracja **A**: auto-bump + sync).

Szczegóły modelu: [docs/workflows/config-A-mirror-auto.md](docs/workflows/config-A-mirror-auto.md).  
Porównanie A vs B (plan Cursor + Mermaid): [docs/plans/porownanie-1A2A-vs-1B2B.plan.md](docs/plans/porownanie-1A2A-vs-1B2B.plan.md).

## Uruchomienie przez Docker Compose

```sh
docker compose up --build
```

API: http://localhost:8000 · Swagger: http://localhost:8000/docs

## Codzienny rytm

1. Feature branch → PR → `dev` (CI + obraz GHCR `:dev`).
2. Gdy gotowe: PR `dev` → `main`, **squash merge**.
3. Tytuł / wiadomość squash (conventional commits):
   - `fix:` / inne → **patch**
   - `feat:` → **minor**
   - `feat!:` albo `BREAKING CHANGE:` → **major**
4. Workflow na `main`:
   - podbija `__version__.py` do `X.Y.Z`
   - taguje `vX.Y.Z`
   - buduje wheel + obraz (`latest`, `vX.Y.Z`)
   - synchronizuje drzewo plików do `pse-pub` (bez `.github/` i docs workflow)

W ustawieniach repo zostaw tylko **squash merge** i kasowanie gałęzi po merge.

## Sekret

`PUBLISH_TOKEN` — PAT z `contents:write` do `pythonms/pse-pub`. Bez niego job release/sync kończy się błędem.

## Wersja

Jedyny plik wersji: `__version__.py` (format `X.Y.Z`). Na `dev` nie tworzymy tagów `v*`.
