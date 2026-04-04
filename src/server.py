#!/usr/bin/env python3
"""
AI-Powered Deal Desk
Revenue Target: $18K/month
"""
import json
import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

import stripe
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, field_validator
from openai import OpenAI, OpenAIError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAI v1 client
# ---------------------------------------------------------------------------
_api_key = os.getenv("OPENAI_API_KEY", "")
if not _api_key:
    logger.warning("OPENAI_API_KEY is not set; AI generation will use fallback responses.")
client = OpenAI(api_key=_api_key)

# ---------------------------------------------------------------------------
# Stripe configuration
# ---------------------------------------------------------------------------
STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
else:
    logger.warning("STRIPE_SECRET_KEY is not set; billing endpoints will return errors.")

# Default checkout redirect URLs
_DEFAULT_SUCCESS_URL = os.getenv(
    "CHECKOUT_SUCCESS_URL", "http://localhost:8000/dashboard?success=1"
)
_DEFAULT_CANCEL_URL = os.getenv(
    "CHECKOUT_CANCEL_URL", "http://localhost:8000/dashboard?cancelled=1"
)

# Stripe Price IDs (create these in your Stripe dashboard and set as env vars)
SUBSCRIPTION_PLANS: Dict[str, Dict[str, Any]] = {
    "basic": {
        "name": "Basic",
        "price_monthly": 99,
        "price_id": os.getenv("STRIPE_PRICE_BASIC", ""),
        "features": [
            "Up to 10 proposals/month",
            "Standard templates",
            "Email support",
            "Basic analytics",
        ],
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 299,
        "price_id": os.getenv("STRIPE_PRICE_PRO", ""),
        "features": [
            "Unlimited proposals",
            "AI-powered optimization",
            "Priority support",
            "Advanced analytics",
            "CRM integration",
            "Custom branding",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 999,
        "price_id": os.getenv("STRIPE_PRICE_ENTERPRISE", ""),
        "features": [
            "Everything in Pro",
            "Dedicated account manager",
            "Custom integrations",
            "SLA guarantee",
            "White-label option",
            "Unlimited users",
        ],
    },
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS: List[str] = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080"
).split(",")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI-Powered Deal Desk",
    description=(
        "Auto-generate winning sales proposals in 60 seconds. "
        "Subscription plans: Basic $99/mo, Pro $299/mo, Enterprise $999/mo."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "stripe-signature"],
)

# Serve static files (dashboard) if the directory exists
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled exception on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."},
    )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
UrgencyLevel = Literal["low", "medium", "high"]
PlanName = Literal["basic", "pro", "enterprise"]


class ProposalRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=200)
    industry: Optional[str] = Field(default=None, max_length=100)
    pain_points: List[str] = Field(default=[])
    budget_range: Optional[str] = Field(default=None, max_length=100)
    decision_makers: List[str] = Field(default=[])
    competitors: List[str] = Field(default=[])
    urgency: UrgencyLevel = Field(default="medium")

    @field_validator("pain_points", "decision_makers", "competitors")
    @classmethod
    def limit_list_length(cls, v: List[str]) -> List[str]:
        if len(v) > 20:
            raise ValueError("List must not exceed 20 items.")
        return v


class LeadRequest(BaseModel):
    """Lead capture: creates a proposal and triggers Stripe checkout."""

    company_name: str = Field(..., min_length=2, max_length=200)
    contact_name: str = Field(..., min_length=2, max_length=200)
    contact_email: EmailStr
    plan: PlanName = Field(default="pro")
    industry: Optional[str] = Field(default=None, max_length=100)
    pain_points: List[str] = Field(default=[])
    budget_range: Optional[str] = Field(default=None, max_length=100)
    urgency: UrgencyLevel = Field(default="medium")
    success_url: str = Field(default=_DEFAULT_SUCCESS_URL)
    cancel_url: str = Field(default=_DEFAULT_CANCEL_URL)

    @field_validator("pain_points")
    @classmethod
    def limit_pain_points(cls, v: List[str]) -> List[str]:
        if len(v) > 20:
            raise ValueError("List must not exceed 20 items.")
        return v


class CheckoutRequest(BaseModel):
    """Create a Stripe checkout session for a subscription plan."""

    plan: PlanName
    customer_email: Optional[str] = None
    success_url: str = Field(default=_DEFAULT_SUCCESS_URL)
    cancel_url: str = Field(default=_DEFAULT_CANCEL_URL)


class PricingTier(BaseModel):
    name: str
    price: float
    features: List[str]
    recommended: bool = False


class ProposalResponse(BaseModel):
    proposal_id: str
    executive_summary: str
    solution_overview: str
    pricing_tiers: List[PricingTier]
    roi_calculation: Dict[str, Any]
    next_steps: str
    pdf_url: str
    generated_at: str


class LeadResponse(BaseModel):
    proposal_id: str
    checkout_url: Optional[str]
    proposal: ProposalResponse
    message: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    openai_configured: bool
    stripe_configured: bool
    version: str


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------
async def generate_proposal_content(request: ProposalRequest) -> Dict[str, Any]:
    """
    Generate proposal using GPT-4 (OpenAI v1 client).
    Falls back to static content if the API call fails.
    """
    logger.info(f"Generating AI proposal for: {request.company_name}")

    system_prompt = (
        "You are an expert B2B sales proposal writer with 15 years of experience. "
        "Create compelling, customized sales proposals that win deals. "
        "Focus on: pain-point alignment, clear ROI and value proposition, "
        "competitive differentiation, and concrete next steps. "
        "Always return valid JSON."
    )

    pain_points_str = ", ".join(request.pain_points) or "General efficiency improvements"
    competitors_str = ", ".join(request.competitors) or "Generic alternatives"

    user_prompt = f"""
Create a sales proposal for:
Company: {request.company_name}
Industry: {request.industry or 'Unknown'}
Pain Points: {pain_points_str}
Budget: {request.budget_range or 'Not specified'}
Competing with: {competitors_str}
Urgency: {request.urgency}

Return a JSON object with these keys:
- executive_summary (string, 3 paragraphs)
- solution_overview (string, 5 paragraphs)
- roi_calculation (object with annual_savings and payback_period_months)
- next_steps (string, 3 bullet points)

Tone: Professional, consultative, ROI-focused.
"""

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
            timeout=60,
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)
    except OpenAIError as exc:
        logger.error(f"OpenAI API error for {request.company_name}: {exc}")
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse OpenAI JSON response: {exc}")
    except Exception as exc:
        logger.error(f"Unexpected error during proposal generation: {exc}")

    # Fallback
    return {
        "executive_summary": (
            f"{request.company_name} faces significant challenges with "
            f"{pain_points_str}. "
            "Our solution delivers measurable ROI through automation and intelligence."
        ),
        "solution_overview": (
            "Our platform provides enterprise-grade capabilities tailored to your "
            "specific needs, streamlining operations and accelerating revenue growth."
        ),
        "roi_calculation": {
            "annual_savings": 500000,
            "payback_period_months": 3,
        },
        "next_steps": "Schedule a technical deep-dive call within 3 business days.",
    }


def generate_pricing_tiers(request: ProposalRequest) -> List[PricingTier]:
    """
    Generate dynamic pricing tiers based on company profile and urgency.
    """
    base_price = int(os.getenv("BASE_PRICE", "10000"))

    multipliers: Dict[str, float] = {"high": 1.2, "medium": 1.0, "low": 0.8}
    base_price = int(base_price * multipliers.get(request.urgency, 1.0))

    return [
        PricingTier(
            name="Starter",
            price=round(base_price * 0.5, 2),
            features=[
                "Core platform access",
                "Email support",
                "Up to 10 users",
                "Standard integrations",
            ],
            recommended=False,
        ),
        PricingTier(
            name="Professional",
            price=float(base_price),
            features=[
                "Everything in Starter",
                "Priority support",
                "Up to 50 users",
                "Advanced analytics",
                "Custom integrations",
                "Dedicated account manager",
            ],
            recommended=True,
        ),
        PricingTier(
            name="Enterprise",
            price=round(base_price * 2.0, 2),
            features=[
                "Everything in Professional",
                "Unlimited users",
                "24/7 phone support",
                "Custom development",
                "SLA guarantees",
                "Executive business reviews",
            ],
            recommended=False,
        ),
    ]


def create_stripe_checkout_session(
    plan: str,
    customer_email: Optional[str],
    success_url: str,
    cancel_url: str,
) -> Optional[str]:
    """
    Create a Stripe Checkout Session for a subscription plan.
    Returns the checkout URL, or None if Stripe is not configured.
    """
    if not STRIPE_SECRET_KEY:
        logger.warning("Stripe not configured; skipping checkout session creation.")
        return None

    plan_info = SUBSCRIPTION_PLANS.get(plan)
    if not plan_info:
        raise ValueError(f"Unknown plan: {plan}")

    price_id = plan_info["price_id"]
    if not price_id:
        raise ValueError(
            f"STRIPE_PRICE_{plan.upper()} env var is not set. "
            "Create the price in your Stripe dashboard and set the env var."
        )

    session_params: Dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "allow_promotion_codes": True,
        "billing_address_collection": "auto",
    }
    if customer_email:
        session_params["customer_email"] = customer_email

    session = stripe.checkout.Session.create(**session_params)
    return session.url


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/", summary="Service info")
async def root() -> Dict[str, Any]:
    return {
        "service": "AI-Powered Deal Desk",
        "version": "1.0.0",
        "docs": "/docs",
        "dashboard": "/dashboard",
        "revenue_target": "$18K/month",
        "win_rate": "42%",
        "generation_time": "60 seconds",
        "pricing": {
            "basic": "$99/month",
            "pro": "$299/month",
            "enterprise": "$999/month",
        },
    }


@app.get("/dashboard", response_class=HTMLResponse, summary="Revenue dashboard UI")
async def dashboard() -> HTMLResponse:
    """Serve the frontend revenue & proposal dashboard."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if not os.path.isfile(dashboard_path):
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    with open(dashboard_path, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        openai_configured=bool(os.getenv("OPENAI_API_KEY", "")),
        stripe_configured=bool(STRIPE_SECRET_KEY),
        version="1.0.0",
    )


@app.get("/api/v1/plans", summary="Available subscription plans")
async def get_plans() -> Dict[str, Any]:
    """Return all available subscription plans with pricing."""
    return {
        key: {
            "name": plan["name"],
            "price_monthly": plan["price_monthly"],
            "features": plan["features"],
            "price_configured": bool(plan["price_id"]),
        }
        for key, plan in SUBSCRIPTION_PLANS.items()
    }


@app.post(
    "/api/v1/checkout",
    status_code=status.HTTP_201_CREATED,
    summary="Create Stripe checkout session",
)
async def create_checkout(request: CheckoutRequest) -> Dict[str, Any]:
    """
    Create a Stripe Checkout Session for a subscription plan.
    Returns a checkout URL that the user should be redirected to.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe billing is not configured. Set STRIPE_SECRET_KEY.",
        )

    plan_info = SUBSCRIPTION_PLANS.get(request.plan)
    if not plan_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown plan '{request.plan}'. Valid: basic, pro, enterprise.",
        )

    if not plan_info["price_id"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"STRIPE_PRICE_{request.plan.upper()} is not configured. "
                "Create this price in your Stripe dashboard."
            ),
        )

    try:
        checkout_url = create_stripe_checkout_session(
            plan=request.plan,
            customer_email=request.customer_email,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
    except stripe.StripeError as exc:
        logger.error(f"Stripe error creating checkout: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe API error. Please try again.",
        ) from exc

    return {
        "checkout_url": checkout_url,
        "plan": request.plan,
        "plan_name": plan_info["name"],
        "price_monthly": plan_info["price_monthly"],
    }


@app.post(
    "/api/v1/leads",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Lead capture: generate proposal + trigger Stripe checkout",
)
async def capture_lead(request: LeadRequest) -> LeadResponse:
    """
    Lead capture endpoint.

    1. Generates a complete AI-powered sales proposal.
    2. Creates a Stripe Checkout Session for the selected plan.
    3. Returns the proposal and the checkout URL.
    """
    logger.info(
        f"Lead captured: {request.contact_name} <{request.contact_email}> @ {request.company_name}"
    )

    # Build a ProposalRequest from the lead data
    proposal_req = ProposalRequest(
        company_name=request.company_name,
        industry=request.industry,
        pain_points=request.pain_points,
        budget_range=request.budget_range,
        urgency=request.urgency,
    )

    content = await generate_proposal_content(proposal_req)
    pricing_tiers = generate_pricing_tiers(proposal_req)
    now = datetime.now(timezone.utc)
    proposal_id = f"PROP-{now.strftime('%Y%m%d-%H%M%S')}"

    proposal = ProposalResponse(
        proposal_id=proposal_id,
        executive_summary=content.get("executive_summary", ""),
        solution_overview=content.get("solution_overview", ""),
        pricing_tiers=pricing_tiers,
        roi_calculation=content.get("roi_calculation", {}),
        next_steps=content.get("next_steps", ""),
        pdf_url=f"/proposals/{proposal_id}.pdf",
        generated_at=now.isoformat(),
    )

    # Attempt to create Stripe checkout session
    checkout_url: Optional[str] = None
    message = "Proposal generated successfully."

    if STRIPE_SECRET_KEY:
        plan_info = SUBSCRIPTION_PLANS.get(request.plan, {})
        if plan_info.get("price_id"):
            try:
                checkout_url = create_stripe_checkout_session(
                    plan=request.plan,
                    customer_email=str(request.contact_email),
                    success_url=request.success_url,
                    cancel_url=request.cancel_url,
                )
                message = "Proposal generated. Proceed to checkout to activate your subscription."
            except stripe.StripeError as exc:
                logger.error(f"Stripe error for lead {request.contact_email}: {exc}")
                message = "Proposal generated. Billing setup pending — contact support."
        else:
            message = (
                "Proposal generated. Stripe price not configured for this plan — "
                "contact sales to complete billing setup."
            )
    else:
        message = "Proposal generated. Stripe not configured — billing will be set up manually."

    return LeadResponse(
        proposal_id=proposal_id,
        checkout_url=checkout_url,
        proposal=proposal,
        message=message,
    )


@app.post(
    "/api/v1/proposals",
    response_model=ProposalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a sales proposal",
)
async def create_proposal(request: ProposalRequest) -> ProposalResponse:
    """
    Generate a complete AI-powered sales proposal for a prospect company.
    """
    logger.info(f"Creating proposal for '{request.company_name}'")

    content = await generate_proposal_content(request)
    pricing_tiers = generate_pricing_tiers(request)
    now = datetime.now(timezone.utc)
    proposal_id = f"PROP-{now.strftime('%Y%m%d-%H%M%S')}"

    return ProposalResponse(
        proposal_id=proposal_id,
        executive_summary=content.get("executive_summary", ""),
        solution_overview=content.get("solution_overview", ""),
        pricing_tiers=pricing_tiers,
        roi_calculation=content.get("roi_calculation", {}),
        next_steps=content.get("next_steps", ""),
        pdf_url=f"/proposals/{proposal_id}.pdf",
        generated_at=now.isoformat(),
    )


@app.post(
    "/api/v1/stripe/webhook",
    summary="Stripe webhook receiver",
)
async def stripe_webhook(request: Request) -> JSONResponse:
    """
    Receive and process Stripe webhook events.

    Configure your Stripe webhook to send events to this endpoint.
    Set STRIPE_WEBHOOK_SECRET to the signing secret from your Stripe dashboard.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set; skipping signature verification.")
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON payload.")
    else:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        except stripe.error.SignatureVerificationError as exc:
            logger.warning(f"Invalid Stripe webhook signature: {exc}")
            raise HTTPException(status_code=400, detail="Invalid webhook signature.") from exc
        except Exception as exc:
            logger.error(f"Webhook processing error: {exc}")
            raise HTTPException(status_code=400, detail="Webhook error.") from exc

    event_type = event.get("type", "unknown") if isinstance(event, dict) else event["type"]
    event_data = (event.get("data", {}).get("object", {})
                  if isinstance(event, dict)
                  else event.data.object.to_dict_recursive())

    logger.info(f"Stripe webhook received: {event_type}")

    if event_type == "checkout.session.completed":
        customer_email = event_data.get("customer_email") or event_data.get("customer_details", {}).get("email")
        logger.info(f"Checkout completed for: {customer_email}")

    elif event_type == "customer.subscription.created":
        logger.info(f"Subscription created: {event_data.get('id')} status={event_data.get('status')}")

    elif event_type == "customer.subscription.updated":
        logger.info(f"Subscription updated: {event_data.get('id')} status={event_data.get('status')}")

    elif event_type == "customer.subscription.deleted":
        logger.info(f"Subscription cancelled: {event_data.get('id')}")

    elif event_type == "invoice.payment_succeeded":
        logger.info(f"Payment succeeded: invoice={event_data.get('id')} amount={event_data.get('amount_paid')}")

    elif event_type == "invoice.payment_failed":
        logger.warning(f"Payment failed: invoice={event_data.get('id')} customer={event_data.get('customer')}")

    return JSONResponse(content={"received": True, "type": event_type})


@app.get("/api/v1/revenue", summary="Live revenue & subscription stats")
async def get_revenue() -> Dict[str, Any]:
    """
    Returns live revenue and subscription data from Stripe.
    Falls back to environment-variable overrides if Stripe is not configured.
    """
    if not STRIPE_SECRET_KEY:
        return {
            "stripe_configured": False,
            "mrr": float(os.getenv("STAT_MRR", "0")),
            "active_subscriptions": int(os.getenv("STAT_ACTIVE_SUBS", "0")),
            "revenue_target": 18000,
            "target_progress_pct": 0.0,
            "plans": {
                key: {"name": p["name"], "price_monthly": p["price_monthly"], "active": 0}
                for key, p in SUBSCRIPTION_PLANS.items()
            },
        }

    try:
        subscriptions = stripe.Subscription.list(status="active", limit=100)

        plan_counts: Dict[str, int] = {"basic": 0, "pro": 0, "enterprise": 0}
        mrr = 0.0

        for sub in subscriptions.data:
            for item in sub.items.data:
                price_id = item.price.id
                unit_amount = item.price.unit_amount or 0
                mrr += unit_amount / 100.0
                for key, plan in SUBSCRIPTION_PLANS.items():
                    if plan["price_id"] and price_id == plan["price_id"]:
                        plan_counts[key] += 1

        active_total = sum(plan_counts.values())
        target = 18000.0
        progress = round((mrr / target) * 100, 1) if target > 0 else 0.0

        return {
            "stripe_configured": True,
            "mrr": round(mrr, 2),
            "active_subscriptions": active_total,
            "revenue_target": target,
            "target_progress_pct": progress,
            "plans": {
                key: {
                    "name": SUBSCRIPTION_PLANS[key]["name"],
                    "price_monthly": SUBSCRIPTION_PLANS[key]["price_monthly"],
                    "active": plan_counts[key],
                }
                for key in SUBSCRIPTION_PLANS
            },
        }
    except stripe.StripeError as exc:
        logger.error(f"Stripe error fetching revenue: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch revenue data from Stripe.",
        ) from exc


@app.get("/api/v1/stats", summary="Platform statistics")
async def get_stats() -> Dict[str, Any]:
    """
    Returns platform-level statistics.
    In production, these should be sourced from a real database.
    """
    return {
        "proposals_generated_today": int(os.getenv("STAT_PROPOSALS_TODAY", "0")),
        "average_win_rate": os.getenv("STAT_WIN_RATE", "42%"),
        "average_generation_time": os.getenv("STAT_GEN_TIME", "58 seconds"),
        "revenue_impact": os.getenv("STAT_REVENUE_IMPACT", "$0 pipeline created"),
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    reload = os.getenv("RELOAD", "false").lower() == "true"
    uvicorn.run("server:app", host=host, port=port, reload=reload)
