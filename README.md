# AI-Powered Deal Desk

> **Auto-Generate Sales Proposals in 60 Seconds**

[![CI](https://github.com/Garrettc123/ai-powered-deal-desk/actions/workflows/ci.yml/badge.svg)](https://github.com/Garrettc123/ai-powered-deal-desk/actions/workflows/ci.yml)
[![Deploy](https://img.shields.io/badge/Deploy-Railway-blueviolet)](https://railway.app)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![Win Rate](https://img.shields.io/badge/Win_Rate-42%25+-success.svg)]()

---

## Revenue Model

| Plan | Price | Features |
|------|-------|----------|
| Basic | $99/month | 10 proposals/mo, standard templates, email support |
| Pro | $299/month | Unlimited proposals, AI optimization, priority support |
| Enterprise | $999/month | Everything in Pro + dedicated AM, SLA, white-label |

**Target: $18K MRR** — powered by Stripe subscriptions

---

## What It Does

Turns "needs call notes" into a signed proposal in 60 seconds:

- Auto-generates custom proposals via GPT-4
- Dynamic pricing optimization (3 tiers, urgency-aware)
- ROI calculators built-in
- Competitive positioning
- Win/loss tracking
- **Stripe billing** — subscription checkout, webhooks, live revenue dashboard
- **Lead capture** — auto-creates proposal + triggers Stripe checkout in one request

**42% average win rate** (vs 25% industry average)

---

## Project Structure

```
ai-powered-deal-desk/
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions: lint, test, Docker build, Railway deploy
├── src/
│   ├── server.py           # FastAPI application (proposals + Stripe billing)
│   └── static/
│       └── index.html      # Revenue dashboard UI
├── tests/
│   └── test_server.py      # Pytest test suite (60+ tests)
├── .env.example            # All configurable env vars documented
├── Dockerfile              # Multi-stage build, non-root user, health check
├── docker-compose.yml      # Local Docker Compose setup
├── railway.toml            # Railway auto-deploy configuration
├── pytest.ini              # Test configuration
├── requirements.txt        # Pinned production + test dependencies
└── README.md
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info & pricing |
| GET | `/dashboard` | Revenue dashboard UI |
| GET | `/health` | Health check (OpenAI + Stripe status) |
| GET | `/api/v1/plans` | Available subscription plans |
| POST | `/api/v1/leads` | Lead capture → proposal + Stripe checkout |
| POST | `/api/v1/checkout` | Create Stripe checkout session |
| POST | `/api/v1/stripe/webhook` | Stripe webhook receiver |
| POST | `/api/v1/proposals` | Generate a sales proposal (API-only) |
| GET | `/api/v1/revenue` | Live MRR, subscriptions, target progress |
| GET | `/api/v1/stats` | Platform statistics |
| GET | `/docs` | Interactive Swagger UI |
| GET | `/redoc` | ReDoc API documentation |

### Lead Capture (creates proposal + triggers checkout)

```json
POST /api/v1/leads
{
  "company_name": "Acme Corp",
  "contact_name": "Jane Smith",
  "contact_email": "jane@acme.com",
  "plan": "pro",
  "industry": "Manufacturing",
  "pain_points": ["manual invoicing", "high churn"],
  "budget_range": "$50K",
  "urgency": "high"
}
```

Response includes the generated proposal **and** a `checkout_url` to redirect the user to Stripe.

### Stripe Checkout (subscription only)

```json
POST /api/v1/checkout
{
  "plan": "pro",
  "customer_email": "jane@acme.com",
  "success_url": "https://yourdomain.com/dashboard?success=1",
  "cancel_url": "https://yourdomain.com/dashboard?cancelled=1"
}
```

### Proposal Generation (API-only)

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
# Edit .env — add OPENAI_API_KEY, STRIPE_SECRET_KEY, etc.

# 3. Run the server
cd src && python server.py
# or: uvicorn src.server:app --reload
```

Open:
- **API**: http://localhost:8000/docs
- **Dashboard**: http://localhost:8000/dashboard

### Docker

```bash
docker build -t ai-deal-desk .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e STRIPE_SECRET_KEY=sk_test_... \
  ai-deal-desk
```

### Docker Compose

```bash
cp .env.example .env
# Fill in your keys in .env
docker compose up
```

---

## Stripe Setup

1. Create a [Stripe account](https://dashboard.stripe.com)
2. Create three recurring **prices** in your Stripe dashboard:
   - Basic: $99/month
   - Pro: $299/month
   - Enterprise: $999/month
3. Copy the price IDs (`price_...`) into your `.env` file:
   ```
   STRIPE_PRICE_BASIC=price_...
   STRIPE_PRICE_PRO=price_...
   STRIPE_PRICE_ENTERPRISE=price_...
   ```
4. Set your secret key and publishable key
5. Create a webhook pointing to `https://yourdomain.com/api/v1/stripe/webhook`
   - Events to listen for:
     - `checkout.session.completed`
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.payment_succeeded`
     - `invoice.payment_failed`
6. Copy the webhook signing secret (`whsec_...`) to `STRIPE_WEBHOOK_SECRET`

---

## Testing

```bash
pip install -r requirements.txt
pytest
```

Tests cover (60+ tests):
- All endpoints (root, health, stats, plans, revenue, dashboard, proposals)
- Stripe checkout session creation (with mock)
- Lead capture pipeline (proposal + checkout)
- Stripe webhook processing (all event types)
- Input validation (422 on invalid emails, urgency, short names, oversized lists)
- Pricing tier logic (urgency multipliers, recommended tier)
- Fallback behavior when OpenAI / Stripe keys are absent

---

## Deploy to Railway

### Option A: Automatic (CI/CD)

1. Fork this repo
2. In Railway, create a project and connect your fork
3. Add a `RAILWAY_TOKEN` secret to your GitHub repo settings
4. Set all required env vars in Railway
5. Push to `main` → auto-deploys via GitHub Actions

### Option B: Manual

```bash
npm install -g @railway/cli
railway login
railway up
```

---

## Configuration

See `.env.example` for all configurable variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `STRIPE_SECRET_KEY` | *(required for billing)* | Stripe secret key |
| `STRIPE_PUBLISHABLE_KEY` | *(required for billing)* | Stripe publishable key |
| `STRIPE_WEBHOOK_SECRET` | *(required for webhooks)* | Stripe webhook signing secret |
| `STRIPE_PRICE_BASIC` | *(required for billing)* | Stripe Price ID for Basic plan |
| `STRIPE_PRICE_PRO` | *(required for billing)* | Stripe Price ID for Pro plan |
| `STRIPE_PRICE_ENTERPRISE` | *(required for billing)* | Stripe Price ID for Enterprise plan |
| `CHECKOUT_SUCCESS_URL` | `http://localhost:8000/dashboard?success=1` | Redirect after successful payment |
| `CHECKOUT_CANCEL_URL` | `http://localhost:8000/dashboard?cancelled=1` | Redirect after cancelled checkout |
| `OPENAI_MODEL` | `gpt-4-turbo-preview` | Model for generation |
| `PORT` | `8000` | Server port |
| `HOST` | `0.0.0.0` | Server host |
| `ALLOWED_ORIGINS` | `localhost:3000,8080` | CORS allowed origins |
| `BASE_PRICE` | `10000` | Professional tier base price (proposal tiers) |
| `RELOAD` | `false` | Hot-reload in dev |

---

## Security Notes

- CORS is restricted to explicit origins (no wildcard `*`)
- Docker container runs as non-root user
- OpenAI and Stripe keys are read from environment, never hardcoded
- Stripe webhooks are verified using HMAC signature
- All list inputs are capped at 20 items to prevent abuse
- `urgency` field accepts only `low | medium | high` (validated by Pydantic Literal)
- `plan` field accepts only `basic | pro | enterprise` (validated by Pydantic Literal)

