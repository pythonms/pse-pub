Przy **każdym pushu na `dev`** Actions sam stawia tag `vX.Y.Z.devN` na origin (priv).
Poniżej: jak odpalić to samo ręcznie / lokalnie.

**Przez Actions (zalecane)**

1. Repo **pse-priv** → **Actions** → workflow **Dev Build**
2. **Run workflow**
3. Branch: **`dev`**
4. **Create and push a private vX.Y.Z.devN…** → zostaw **true**
5. **Run workflow**

Workflow na tipie `dev` policzy następne `.devN` (z pliku + istniejących tagów), zrobi commit `chore(bump): …` jeśli trzeba, ustawi tag `v…` i wypchnie **tylko na origin** (priv).

To samo z CLI:

```bash
gh workflow run "Dev Build" --ref dev -f create_dev_tag=true
```

**Bez Actions (ręcznie lokalnie)** — tylko jeśli musisz:

```bash
git checkout as && git pull
# ustaw/sprawdź __version__.py → np. 0.4.0.dev6
git add __version__.py && git commit -m "chore(bump): 0.4.0.dev6"
git tag -a v0.4.0.dev6 -m "Dev checkpoint v0.4.0.dev6"
git push origin as v0.4.0.dev6   # NIE na remote public
```

Lepiej użyć dispatch — ta sama logika co w CI, bez kolizji numerów.
Nie wiem czy to będzie ok do weryfikacji.
CHANGELOG dev = main, nie dodajemy x.y.z.dev wersji