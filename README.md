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

## Quickstart
1. **Clone and enter the repo.**
   ```bash
   git clone <repo-url>
   cd openpoke
   ```
2. **Create a shared env file.** Copy the template and open it in your editor:
   ```bash
   cp .env.example .env
   ```
3. **Fetch API keys and drop them into `.env`.**
   - **OpenRouter**: create an account at [openrouter.ai](https://openrouter.ai/), generate an API key, and paste it into `OPENROUTER_API_KEY`.
   - **Composio (optional Gmail tooling)**: sign in at [composio.com](https://www.composio.com/), create an API key, locate your Gmail auth config ID, and populate `COMPOSIO_API_KEY` / `COMPOSIO_GMAIL_AUTH_CONFIG_ID`.
4. **(Recommended) create and activate a Python virtualenv:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   On Windows (PowerShell):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
5. **Install backend dependencies:**
   ```bash
   pip install -r server/requirements.txt
   ```
6. **Install frontend dependencies:**
   ```bash
   npm install --prefix web
   ```
7. **Start the FastAPI server:**
   ```bash
   python -m server.server --reload
   ```
8. **Start the Next.js app (new terminal):**
   ```bash
   npm run dev --prefix web
   ```
9. **Connect Gmail for email workflows.** With both services running, open [http://localhost:3000](http://localhost:3000), head to *Settings → Gmail*, and complete the Composio OAuth flow. Email tools, triggers, and monitors rely on this step.

The web app proxies API calls to the Python server using the values in `.env`, so keeping both processes running is required for end-to-end flows.

## Project Layout
- `server/` – FastAPI application and agents
- `web/` – Next.js app
- `server/data/` – runtime data (ignored by git)

## License
MIT — see [LICENSE](LICENSE).
