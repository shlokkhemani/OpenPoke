# OpenPoke

Lightweight agent orchestration stack with a FastAPI backend and a Next.js web UI. The backend talks to OpenRouter for LLM calls and can optionally use Composio for Gmail automation.

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
