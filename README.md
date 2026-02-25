# AI-Powered Deal Desk

> **Auto-Generate Sales Proposals in 60 Seconds**

[![CI](https://github.com/Garrettc123/ai-powered-deal-desk/actions/workflows/ci.yml/badge.svg)](https://github.com/Garrettc123/ai-powered-deal-desk/actions/workflows/ci.yml)
[![Deploy](https://img.shields.io/badge/Deploy-Railway-blueviolet)](https://railway.app)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![Win Rate](https://img.shields.io/badge/Win_Rate-42%25+-success.svg)]()

---

## Revenue Model

| Plan | Price | Users |
|------|-------|-------|
| Per-seat | $149/month | 1 |
| Team | $499/month | up to 10 |
| Enterprise | $1,499/month | Unlimited |

**Target: $18K MRR**

---

## What It Does

Turns "needs call notes" into a signed proposal in 60 seconds:

- Auto-generates custom proposals via GPT-4
- Dynamic pricing optimization (3 tiers, urgency-aware)
- ROI calculators built-in
- Competitive positioning
- Win/loss tracking

**42% average win rate** (vs 25% industry average)

---

## Project Structure

```
ai-powered-deal-desk/
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions: lint, test, Docker build
├── src/
│   └── server.py           # FastAPI application
├── tests/
│   └── test_server.py      # Pytest test suite (20+ tests)
├── .env.example            # All configurable env vars documented
├── Dockerfile              # Multi-stage build, non-root user, health check
├── pytest.ini              # Test configuration
├── requirements.txt        # Pinned production + test dependencies
└── README.md
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info & pricing |
| GET | `/health` | Health check |
| POST | `/api/v1/proposals` | Generate a sales proposal |
| GET | `/api/v1/stats` | Platform statistics |
| GET | `/docs` | Interactive Swagger UI |

### Example Request

```json
POST /api/v1/proposals
{
  "company_name": "Acme Corp",
  "industry": "Manufacturing",
  "pain_points": ["manual invoicing", "high churn"],
  "budget_range": "$50K",
  "decision_makers": ["CTO", "CFO"],
  "competitors": ["SAP", "Oracle"],
  "urgency": "high"
}
```

---

## Quick Start

### Local Development

```bash
# 1. Clone & install dependencies
git clone https://github.com/Garrettc123/ai-powered-deal-desk.git
cd ai-powered-deal-desk
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 3. Run the server
cd src && python server.py
# or: uvicorn src.server:app --reload
```

Open http://localhost:8000/docs

### Docker

```bash
docker build -t ai-deal-desk .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... ai-deal-desk
```

---

## Testing

```bash
pip install pytest pytest-asyncio httpx
pytest
```

Tests cover:
- All endpoints (root, health, stats, proposals)
- Input validation (422 on invalid urgency, short names, oversized lists)
- Pricing tier logic (urgency multipliers, recommended tier)
- Fallback behavior when OpenAI key is absent

---

## Configuration

See `.env.example` for all configurable variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4-turbo-preview` | Model for generation |
| `PORT` | `8000` | Server port |
| `HOST` | `0.0.0.0` | Server host |
| `ALLOWED_ORIGINS` | `localhost:3000,8080` | CORS allowed origins |
| `BASE_PRICE` | `10000` | Professional tier base price |
| `RELOAD` | `false` | Hot-reload in dev |

---

## Deploy to Railway

1. Fork this repo
2. Connect to [Railway](https://railway.app)
3. Set `OPENAI_API_KEY` in Railway environment variables
4. Deploy

---

## Security Notes

- CORS is restricted to explicit origins (no wildcard `*`)
- Docker container runs as non-root user
- OpenAI key is read from environment, never hardcoded
- All list inputs are capped at 20 items to prevent abuse
- `urgency` field accepts only `low | medium | high` (validated by Pydantic Literal)
