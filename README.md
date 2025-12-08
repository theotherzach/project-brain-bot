# Project Brain Bot

A Slack bot that helps teams query project context using Claude AI and RAG (Retrieval-Augmented Generation). Ask questions in natural language and get answers backed by your project's actual data from Linear, Notion, GitHub, Mixpanel, and Datadog.

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

## Usage

### In Slack

**Mention the bot in a channel:**
```
@Project Brain What's the status of the auth refactor?
```

**Send a direct message:**
```
Who's working on the payment integration?
```

**Use the slash command:**
```
/brain Are there any active alerts right now?
```

### Example Questions

- "What did we decide in the last sprint planning?"
- "What's the status of ticket ENG-123?"
- "Who reviewed the last PR for the API service?"
- "What's our current user retention rate?"
- "Are there any critical alerts in production?"

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
