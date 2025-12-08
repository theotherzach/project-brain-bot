# Project Brain Bot

A Slack bot that helps teams query project context using Claude AI and RAG (Retrieval-Augmented Generation). Ask questions in natural language and get answers backed by your project's actual data from Linear, Notion, GitHub, Mixpanel, and Datadog.

## Usage Examples

### How to Talk to Brain

**Mention in a channel:**
```
@brain what's the status of the auth refactor?
```

**Send a direct message:**
```
Who's working on the payment integration?
```

**Use the slash command:**
```
/brain Are there any active alerts right now?
```

---

### Basic Queries

**Project status:**

> @brain what's the status of the checkout redesign?

**Meeting context:**

> @brain what did we decide about the auth refactor last week?

**Ticket lookup:**

> @brain who's working on the Stripe integration?

---

### Multi-Source Queries (The Good Stuff)

**Connecting metrics to engineering work:**

> @brain checkout conversion dropped 15% yesterday—are there any related bugs or deploys?

*Pulls from: Mixpanel (conversion data) + Datadog (recent deploys, errors) + Linear (related tickets) + GitHub (recent merges to checkout flow)*

---

**Sprint health check:**

> @brain are we on track for the Q1 launch? Any blockers I should know about?

*Pulls from: Linear (epic progress, blocked tickets) + Notion (sprint planning notes, risk flags) + Datadog (any active alerts on launch-critical services)*

---

**Incident investigation:**

> @brain the API is slow—what changed recently and who should I ping?

*Pulls from: Datadog (latency metrics, alerts) + GitHub (recent PRs merged) + Linear (who owns what) + Notion (on-call schedule if you track it there)*

---

**Customer issue triage:**

> @brain a customer reported checkout failures around 2pm yesterday—what do we know?

*Pulls from: Datadog (error rates at that time) + Linear (any related bug reports) + GitHub (deploys around that window) + Mixpanel (checkout funnel drop)*

---

**Onboarding a new team member:**

> @brain give me the TLDR on the payments service—architecture decisions, current status, and who knows it best

*Pulls from: Notion (architecture docs, meeting notes) + Linear (recent tickets, ownership) + GitHub (top contributors to that repo)*

---

**Exec prep:**

> @brain summarize engineering progress this week—what shipped, what's blocked, and any metrics changes I should mention in the all-hands

*Pulls from: Linear (completed tickets, blockers) + GitHub (merged PRs) + Notion (meeting notes) + Mixpanel (weekly metrics trends) + Datadog (uptime/reliability)*

---

**Root cause analysis:**

> @brain signups dropped 30% last Tuesday—walk me through what might have caused it

*Pulls from: Mixpanel (signup funnel breakdown) + Datadog (any outages or latency spikes) + GitHub (what shipped that day) + Linear (any related bugs filed) + Notion (was there a meeting about this?)*

---

**Dependency tracking:**

> @brain what's blocking the mobile app release and who do I need to follow up with?

*Pulls from: Linear (blocked tickets, dependencies, assignees) + Notion (release planning notes) + GitHub (open PRs that need review)*

---

**Historical context:**

> @brain why did we choose Redis over Postgres for session storage?

*Pulls from: Notion (meeting notes, architecture decision records) + GitHub (PR discussions, ADRs in repo) + Linear (original tickets/spikes)*

---

### Quick Ops Checks

**Morning standup prep:**

> @brain anything on fire?

*Pulls from: Datadog (active alerts) + Linear (P0/P1 bugs) + GitHub (failed CI on main)*

---

**Pre-deploy sanity:**

> @brain how's the system looking right now—safe to deploy?

*Pulls from: Datadog (error rates, latency, active alerts) + Linear (any deploy blockers flagged)*

---

**End of week wrap:**

> @brain what did the team ship this week?

*Pulls from: Linear (completed tickets) + GitHub (merged PRs) + Notion (demo notes if you track them)*

---

### Power User Moves

**Comparative analysis:**

> @brain compare this week's error rate to last week—are we getting better or worse?

---

**Trend spotting:**

> @brain any patterns in the bugs filed this month?

---

**Knowledge discovery:**

> @brain who on the team knows the most about our GraphQL layer?

*Pulls from: GitHub (commit history) + Linear (ticket assignments) + Notion (meeting attendance on related topics)*

---

## Features

- **Natural Language Queries**: Ask questions about your project in plain English
- **Multi-Source Context**: Aggregates information from:
  - **Linear**: Tasks, issues, sprints, and project status
  - **Notion**: Documentation, meeting notes, and specs
  - **GitHub**: PRs, issues, and code
  - **Mixpanel**: Analytics and user behavior metrics
  - **Datadog**: Monitoring alerts and incidents
- **RAG-Powered Answers**: Uses embeddings and vector search for accurate, context-aware responses
- **Automatic Sync**: Background job keeps the vector store updated with fresh data
- **Smart Caching**: Redis-based caching to minimize API calls

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Slack    │────▶│  Bot App    │────▶│   Claude    │
└─────────────┘     └──────┬──────┘     └─────────────┘
                          │
                    ┌─────▼─────┐
                    │    RAG    │
                    │  Engine   │
                    └─────┬─────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   ┌────▼────┐      ┌─────▼─────┐     ┌─────▼─────┐
   │ Vector  │      │  Context  │     │   Cache   │
   │  Store  │      │ Providers │     │  (Redis)  │
   │(Pinecone)│     └─────┬─────┘     └───────────┘
   └─────────┘            │
                    ┌─────┴─────┐
              ┌─────┴─────┬─────┴─────┬─────┴─────┐
              │           │           │           │
           Linear     Notion     GitHub    Mixpanel/DD
```

## Quick Start

### Prerequisites

- Python 3.11+
- Redis
- Slack App with Bot Token and App Token
- API keys for: Anthropic, OpenAI, Pinecone
- (Optional) API keys for: Linear, Notion, GitHub, Mixpanel, Datadog

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/theotherzach/project-brain-bot.git
   cd project-brain-bot
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. **Start Redis** (if not using Docker)
   ```bash
   redis-server
   ```

6. **Seed the vector store** (initial data sync)
   ```bash
   python scripts/seed_vectorstore.py
   ```

7. **Run the bot**
   ```bash
   python -m src.main
   ```

### Using Docker

```bash
# Build and run with Docker Compose
docker-compose up -d

# Run initial seed (optional)
docker-compose --profile seed up seed
```

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `SLACK_BOT_TOKEN` | Slack Bot OAuth Token (xoxb-...) |
| `SLACK_APP_TOKEN` | Slack App-Level Token for Socket Mode (xapp-...) |
| `SLACK_SIGNING_SECRET` | Slack Signing Secret |
| `ANTHROPIC_API_KEY` | Anthropic API Key |
| `OPENAI_API_KEY` | OpenAI API Key (for embeddings) |
| `PINECONE_API_KEY` | Pinecone API Key |

### Optional Environment Variables

See [.env.example](.env.example) for all available configuration options.

## Slack App Setup

1. Create a new Slack App at [api.slack.com/apps](https://api.slack.com/apps)

2. **Enable Socket Mode**
   - Settings → Socket Mode → Enable
   - Generate an App-Level Token with `connections:write` scope

3. **Configure Bot Token Scopes** (OAuth & Permissions):
   - `app_mentions:read`
   - `chat:write`
   - `im:history`
   - `im:read`
   - `im:write`

4. **Enable Events** (Event Subscriptions):
   - `app_mention`
   - `message.im`

5. **Add Slash Command** (optional):
   - Command: `/brain`
   - Description: "Ask Project Brain a question"

6. Install the app to your workspace

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_handlers.py -v
```

### Code Quality

```bash
# Lint with ruff
ruff check src/ tests/

# Format with ruff
ruff format src/ tests/

# Type check with mypy
mypy src/
```

### Project Structure

```
src/
├── main.py                 # Entry point
├── config.py               # Pydantic settings
├── bot/
│   ├── handlers.py         # Slack event handlers
│   └── formatting.py       # Message formatting
├── llm/
│   ├── client.py           # Claude query logic
│   ├── prompts.py          # System prompts
│   └── classifier.py       # Question classification
├── context/
│   ├── linear.py           # Linear API
│   ├── notion.py           # Notion API
│   ├── github.py           # GitHub API
│   ├── mixpanel.py         # Mixpanel API
│   └── datadog.py          # Datadog API
├── retrieval/
│   ├── embeddings.py       # OpenAI embeddings
│   ├── vectorstore.py      # Pinecone client
│   └── query.py            # RAG query logic
├── sync/
│   ├── scheduler.py        # Background sync
│   ├── chunking.py         # Document chunking
│   └── sources/            # Source-specific sync
└── utils/
    ├── cache.py            # Caching decorator
    └── logging.py          # Structured logging
```

## Deployment

### Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Create app
fly apps create project-brain-bot

# Create Redis (or use Upstash)
fly redis create

# Set secrets
fly secrets set SLACK_BOT_TOKEN=xoxb-...
fly secrets set ANTHROPIC_API_KEY=...
# ... set all required secrets

# Deploy
fly deploy
```

### Docker

```bash
# Build image
docker build -t project-brain-bot .

# Run with environment file
docker run --env-file .env project-brain-bot
```

## How It Works

1. **Question Classification**: When a question is received, Claude classifies it to determine which data sources are most relevant.

2. **RAG Retrieval**: The question is converted to an embedding and used to search the Pinecone vector store for relevant documents.

3. **Live Context**: For some queries, the bot also fetches live data from APIs (cached to reduce load).

4. **Response Generation**: Claude generates a response using the retrieved context, citing sources where available.

5. **Background Sync**: APScheduler runs periodic jobs to sync data from all sources to the vector store.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.
