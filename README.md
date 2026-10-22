# Caleroo

A simple AI-powered calorie counter. Photograph a plate, or upload one, and a vision model estimates the foods. Correct the numbers, then keep them in a daily log with calories, protein, carbs, and fat. You can also add a meal by hand, set daily goals for calories, protein, carbs, and fat, and look back over the last seven days. On today, **What to eat** asks the same model what still fits the calories and macros you have left.

It is a small self-hosted web app. By default there is no account: one shared log, and nobody logs in. Set `AUTHENTICATION=true` when more than one person should keep a separate log. Meals and photos stay in a `data/` directory on the machine running it.

A photo estimate is sent to whichever model server you configure. That server sees the image. Meal advice sends that day’s log: titles, calories, macros, and the time of day. It does not send photos. Logging a meal by hand does not send anything.

## Run

```bash
cp .env.example .env
# put your key in API_KEY
docker compose up --build
```

Open [http://localhost:6969](http://localhost:6969).

After editing `.env`, recreate the container so it picks up the new values:

```bash
docker compose up -d --force-recreate
```

That reloads configuration. It does not delete the log.

You can also change the model and the daily goals in the app. A model typed there overrides `MODEL`. Leave that field blank to use the value from `.env` again.

## Estimates

Photo estimates and meal advice call an OpenAI-style `POST /v1/chat/completions` endpoint. The model has to accept images for photo estimates. Meal advice is text only.

Leave `BASE_URL` empty to use [OpenRouter](https://openrouter.ai). Set `API_KEY`. If `MODEL` is empty, Caleroo sends `google/gemini-2.5-flash`.

To use a server you run yourself (Ollama, llama.cpp, vLLM, LM Studio, or anything else with an OpenAI-compatible `/v1` API), set `BASE_URL` to that API base:

```bash
BASE_URL=http://host.docker.internal:8000/v1
MODEL=your-vision-model
API_KEY=
```

`BASE_URL` is the part that ends in `/v1`. Caleroo appends `/chat/completions`. `MODEL` is the name that server uses for a vision model. `API_KEY` is only needed when that server requires a bearer token. Leave it empty otherwise. OpenRouter always requires `API_KEY`.

From inside Docker, `localhost` is the container, so a server on the host machine is `http://host.docker.internal:8000/v1`. Compose adds that hostname. Use the machine's LAN address, such as `http://192.168.1.20:8000/v1`, when the server is on another computer. Without Docker, `http://127.0.0.1:8000/v1` is the server on this machine.

Photo estimates stay off until OpenRouter has an API key, or your own server has a base URL and a model name. You can still log meals by hand.

## Environment

Docker Compose reads `.env` and passes these into the container.

| Variable | What it does |
| --- | --- |
| `BASE_URL` | OpenAI-compatible API base, such as `http://host.docker.internal:8000/v1`. Empty uses `https://openrouter.ai/api/v1`. |
| `API_KEY` | Bearer token. Required for OpenRouter. Optional for a server that does not check one. |
| `MODEL` | Model name. Empty on OpenRouter uses `google/gemini-2.5-flash`. Your own server needs a vision model here, or one set in the app. |
| `APP_URL` | Sent to OpenRouter as the `HTTP-Referer` header so the request is attributed to this app. Defaults to `http://localhost:6969`. |
| `AUTHENTICATION` | `false` (the default) is one shared log with no login. `true` asks each person to register. They choose a password, starting calorie and macro goals, and an avatar. Each account then has its own meals and goals. |

Two more are set by Compose itself, in `docker-compose.yml`:

| Variable | What it does |
| --- | --- |
| `PORT` | Port the app listens on inside the container. Defaults to `6969`. The published port is the left side of `6969:6969` in Compose. |
| `DATA_DIR` | Directory for `caleroo.sqlite` and `images/`. Compose sets `/data`, which is bind-mounted to `./data`. |

## Data

Meals and photos persist in `data/` (`caleroo.sqlite` and `images/`). Docker bind-mounts that directory, and it is gitignored. Deleting those files clears the log. With accounts on, each person has their own meals, photos, and goals in that same database. The container runs as user id 1000, so that directory stays owned by the usual login on this machine.

## Notes

The camera needs a secure page (`localhost` or HTTPS). Uploading a photo works from any address you can reach, including another device on your network.

Do not publish port 6969 to the internet. Anyone who can open the app can use your API key, or your model server. With `AUTHENTICATION=true`, anyone who can open the page can also create an account.

## Without Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export API_KEY=sk-or-...
uvicorn app.main:app --host 0.0.0.0 --port 6969
```

For a model server on this machine:

```bash
export BASE_URL=http://127.0.0.1:8000/v1
export MODEL=your-vision-model
export API_KEY=
uvicorn app.main:app --host 0.0.0.0 --port 6969
```

Without `DATA_DIR`, the same files are written to `data/` in this directory.
