from fastapi import FastAPI

from __version__ import __version__

app = FastAPI(
    title="Przykładowy Projekt FastAPI, do testów workflow na GitHub.",
    description="Prosta testowa aplikacja z konfiguracją pyproject.toml",
    version=__version__,
)


@app.get("/")
def read_root():
    """Główny endpoint zwracający powitanie podstawowe."""
    return {
        "message": "Witaj w przykładowym projekcie FastAPI!",
        "status": "sukces",
        "code": 200,
        "service": "pse",
    }


@app.get("/health")
def health():
    """Liveness probe for Compose, CI, and local smoke checks."""
    return {"status": "ok", "version": __version__, "service": "pse"}


@app.get("/version")
def version():
    """Return package version for smoke tests."""
    return {"version": __version__, "service": "pse"}
