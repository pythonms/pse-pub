from fastapi import FastAPI

from __version__ import __version__

app = FastAPI(
    title="Przykładowy Projekt FastAPI",
    description="Prosta testowa aplikacja z konfiguracją pyproject.toml",
    version=__version__,
)


@app.get("/")
def read_root():
  """Główny endpoint zwracający powitanie."""
  return {
      "message": "Witaj my friend w przykładowym projekcie FastAPI!",
      "status": "sukces",
      "code": 200,
  }