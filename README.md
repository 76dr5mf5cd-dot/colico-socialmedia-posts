# Colico Social Agent

Een lokale agent die foto's uit een map ophaalt, er automatisch aangepaste
socialposts op basis van de Colico-huisstijl voor maakt, en ze ná goedkeuring
plaatst op Bluesky en Instagram.

## Hoe het werkt

1. `scan` — zoekt nieuwe foto's in je fotomap, stuurt ze naar een vision-model
   (Pixtral) en genereert een onderschrift, hashtags en alt-tekst.
2. `drafts` / `show` / `edit` — je bekijkt en bewerkt elk concept.
3. `approve` / `reject` — je keurt af of goed.
4. `publish` — de agent plaatst goedgekeurde posts op Bluesky en Instagram.

Alles wat gepost is (en afgekeurd) wordt bijgehouden in `state.json`,
dus elke foto wordt maar één keer gebruikt.

## Installatie

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # vul je keys in
cp settings.example.yaml settings.yaml
python -m colico_agent.cli --help
```

Put your photos in the folder shown in `settings.yaml` (default `./photos`).

## Instellingen

- **Bluesky**: maak in Bluesky een app-password aan (Account → App passwords)
  en zet je handle in `.env`.
- **Instagram**: je zakelijke/creator-account moet aan een Facebook-pagina
  hangen. Maak een Meta-app met de rechten `instagram_basic`,
  `pages_show_list`, `business_management` en `instagram_content_publish`,
  en genereer een lange-termijn-token. Zet `IG_USER_ID` (de
  instagram_business_account-id) en `IG_ACCESS_TOKEN`.
- **Instagram-publicatie** verplicht een publieke afbeelding-URL. Zet
  `photos.public_url_base` naar een bereikbare map op eigen hosting (bijv.
  colico.be), of gebruik `publish --platforms bluesky` als je geen URL hebt.
- **Onderschriften**: pas `captions` aan in `settings.yaml` (taal, toon,
  extra instructies, model, extra hashtags).

## Dagelijkse cyclus 

```bash
python -m colico_agent.cli scan                 # concepten maken
python -m colico_agent.cli drafts               # overzicht
python -m colico_agent.cli show <concept-id>    # details
python -m colico_agent.cli edit <concept-id>    # aanpassen in je editor
python -m colico_agent.cli approve <concept-id>
python -m colico_agent.cli publish <concept-id>
python -m colico_agent.cli publish --all --platforms bluesky,instagram
```

## Tests

```bash
pip install pytest
python -m pytest tests
```

De tests mocken alle netwerkaanroepen; er wordt niets gepost tijdens testen.
