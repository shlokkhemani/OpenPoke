# OpenPoke 🌴

OpenPoke is a simplified, open-source take on [Interaction Company’s](https://interaction.co/about) [Poke](https://poke.com/) assistant—built to show how a multi-agent orchestration stack can feel genuinely useful. It keeps the handful of things Poke is great at (email triage, reminders, and persistent agents) while staying easy to spin up locally.

- Multi-agent FastAPI backend that mirrors Poke's interaction/execution split, powered by [OpenRouter](https://openrouter.ai/).
- Gmail tooling via [Composio](https://composio.dev/) for drafting/replying/forwarding without leaving chat.
- Trigger scheduler and background watchers for reminders and "important email" alerts.
- Next.js web UI that proxies everything through the shared `.env`, so plugging in API keys is the only setup.

### 🐳 Docker Support (`feat/docker`)
- **One-Command Deployment**: Start the entire stack with `docker-compose up`
- **Multi-Container Architecture**: Separate backend and frontend containers for better scaling
- **Data Persistence**: Automatic volume management for SQLite database and logs
- **Development Mode**: Hot-reload support for rapid development
- **Production Ready**: Optimized images with security best practices and health checks
- **Comprehensive Testing**: Full test suite for Docker setup validation

## Requirements

### Option 1: Docker (Recommended)
- Docker 20.10+
- Docker Compose 2.0+

### Option 2: Local Development
- Python 3.10+
- Node.js 18+
- npm 9+

## Quickstart

**Base setup to get Open Router API key and Composio key**
1. **Clone and enter the repo.**
   ```bash
   git clone https://github.com/shlokkhemani/OpenPoke
   cd OpenPoke
   ```
2. **Create a shared env file.** Copy the template and open it in your editor:
   ```bash
   cp .env.example .env
   ```
3. **Get your API keys and add them to `.env`:**
   
   **OpenRouter (Required)**
   - Create an account at [openrouter.ai](https://openrouter.ai/)
   - Generate an API key
   - Replace `your_openrouter_api_key_here` with your actual key in `.env`
   
   **Composio (Required for Gmail)**
   - Sign in at [composio.dev](https://composio.dev/)
   - Create an API key
   - Set up Gmail integration and get your auth config ID
   - Replace `your_composio_api_key_here` and `your_gmail_auth_config_id_here` in `.env`

### 🐳 Docker Deployment (Easiest)

**Perfect for: Self-hosters, quick testing, and production deployments**

1. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Start with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

3. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8001
   - API Docs: http://localhost:8001/docs

4. **View logs:**
   ```bash
   docker-compose logs -f
   ```

**That's it!** Your OpenPoke instance is running. See [DEPLOYMENT.md](DEPLOYMENT.md) for advanced configuration, backup, and production setup.

---

### 💻 Local Development Setup

1. **(Required) Create and activate a Python 3.10+ virtualenv:**
   ```bash
   # Ensure you're using Python 3.10+
   python3.10 -m venv .venv
   source .venv/bin/activate
   
   # Verify Python version (should show 3.10+)
   python --version
   ```
   On Windows (PowerShell):
   ```powershell
   # Use Python 3.10+ (adjust path as needed)
   python3.10 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   
   # Verify Python version
   python --version
   ```

2. **Install backend dependencies:**
   ```bash
   pip install -r server/requirements.txt
   ```
3. **Install frontend dependencies:**
   ```bash
   npm install --prefix web
   ```
4. **Start the FastAPI server:**
   ```bash
   python -m server.server --reload
   ```
5. **Start the Next.js app (new terminal):**
   ```bash
   npm run dev --prefix web
   ```

---

### **Connect Gmail for email workflows.**

 With both services running, open [http://localhost:3000](http://localhost:3000), head to *Settings → Gmail*, and complete the Composio OAuth flow. This step is required for email drafting, replies, and the important-email monitor.

The web app proxies API calls to the Python server using the values in `.env`, so keeping both processes running is required for end-to-end flows.

## Project Layout
- `server/` – FastAPI application and agents
- `web/` – Next.js app
- `server/data/` – runtime data (ignored by git)

## License
MIT — see [LICENSE](LICENSE).
