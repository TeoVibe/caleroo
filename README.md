# Caleroo

A simple AI-powered calorie counter. Photograph a plate, or upload one, and a vision model estimates the foods. Correct the numbers, then keep them in a daily log with calories, protein, carbs, and fat. You can also add a meal by hand, set a daily goal, and look back over the last seven days.

It is a small self-hosted web app. There is no account. Meals and photos stay in a `data/` directory on the machine running it.

The estimate request sends the image to the model provider, so that provider sees the photo.

## Run

```bash
cp .env.example .env
# put your key in OPENROUTER_API_KEY
docker compose up --build
```

Open [http://localhost:6969](http://localhost:6969).

## Estimates

`INFERENCE` chooses where photo estimates go.

- `openrouter` uses [OpenRouter](https://openrouter.ai). Set `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`. The default model is `google/gemini-2.5-flash`.
- `local` uses any OpenAI-compatible server. Set `LOCAL_BASE_URL` to its base, such as `http://192.168.1.20:8000/v1`, and `LOCAL_MODEL` to a vision model on that server. `LOCAL_API_KEY` is optional. From inside Docker, a server on this machine is `http://host.docker.internal:8000/v1`.

You can also change the model and the daily goal in the app. After editing `.env`, recreate the container with `docker compose up -d --force-recreate`. That reloads configuration. It does not delete the log.

## Data

Meals and photos persist in `data/` (`caleroo.sqlite` and `images/`). Docker bind-mounts that directory, and it is gitignored. Deleting those files clears the log.

## Notes

The camera needs a secure page (`localhost` or HTTPS). Uploading a photo works from any address you can reach, including another device on your network.

Do not publish port 6969 to the internet. Anyone who can open the app can use your OpenRouter key.

## Without Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENROUTER_API_KEY=sk-or-...
uvicorn app.main:app --host 0.0.0.0 --port 6969
```

Without `DATA_DIR`, the same files are written to `data/` in this directory.
