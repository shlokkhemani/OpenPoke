# OpenPoke

OpenPoke is a simplified, open-source take on [Interaction Company’s](https://interaction.co/about) [Poke](https://poke.com/) assistant—built to show how a multi-agent orchestration stack can feel genuinely useful. It keeps the handful of things Poke is great at (email triage, reminders, and persistent agents) while staying easy to spin up locally.

- Multi-agent FastAPI backend that mirrors Poke’s interaction/execution split, powered by OpenRouter LLMs.
- Gmail tooling, optional via Composio, for drafting/replying/forwarding without leaving chat.
- Trigger scheduler and background watchers for reminders and “important email” alerts.
- Next.js web UI that proxies everything through the shared `.env`, so plugging in API keys is the only setup.

## Requirements
- Python 3.10+
- Node.js 18+
- npm 9+

## Setup
1. Copy the shared environment file: `cp .env.example .env` and fill in OpenRouter and Composio keys.
2. (Recommended) create and activate a virtual environment in the repo root:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   On Windows (PowerShell):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install backend deps: `pip install -r server/requirements.txt`.
4. Install frontend deps: `npm install --prefix web`.

## API Keys
- **OpenRouter**: create an account at [openrouter.ai](https://openrouter.ai/), generate an API key from the dashboard, and place it in `OPENROUTER_API_KEY` inside `.env`. The backend reads this value for all LLM calls.
- **Composio (Gmail tooling)**: log into the [Composio Console](https://www.composio.com/), create an API key, and note the Gmail auth config ID from the Gmail integration setup. Set `COMPOSIO_API_KEY` to the API token and `COMPOSIO_GMAIL_AUTH_CONFIG_ID` to the config identifier when you want Gmail actions enabled. 

## Development
Open two terminals after installing dependencies:

- Backend: `python -m server.server --reload`
- Frontend: `npm run dev --prefix web`

The web app proxies API calls to the Python server using the values in `.env`.

## Project Layout
- `server/` – FastAPI application and agents
- `web/` – Next.js app
- `server/data/` – runtime data (ignored by git)

## License
MIT — see [LICENSE](LICENSE).
