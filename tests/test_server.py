"""Tests for the AI-Powered Deal Desk API."""
import json
import os
import sys
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# Ensure the src directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from server import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# Root / info endpoint
# ---------------------------------------------------------------------------
class TestRoot:
    def test_root_returns_200(self):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_contains_service_name(self):
        data = client.get("/").json()
        assert data["service"] == "AI-Powered Deal Desk"

    def test_root_contains_pricing(self):
        data = client.get("/").json()
        assert "pricing" in data
        assert "basic" in data["pricing"]
        assert "pro" in data["pricing"]
        assert "enterprise" in data["pricing"]

    def test_root_contains_dashboard_link(self):
        data = client.get("/").json()
        assert "dashboard" in data


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------
class TestHealth:
    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_status_is_healthy(self):
        data = client.get("/health").json()
        assert data["status"] == "healthy"

    def test_health_contains_timestamp(self):
        data = client.get("/health").json()
        assert "timestamp" in data

    def test_health_contains_version(self):
        data = client.get("/health").json()
        assert data["version"] == "1.0.0"

    def test_health_openai_configured_false_without_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["openai_configured"] is False

    def test_health_stripe_configured_false_without_key(self, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["stripe_configured"] is False


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------
class TestStats:
    def test_stats_returns_200(self):
        response = client.get("/api/v1/stats")
        assert response.status_code == 200

    def test_stats_contains_required_keys(self):
        data = client.get("/api/v1/stats").json()
        assert "proposals_generated_today" in data
        assert "average_win_rate" in data
        assert "average_generation_time" in data
        assert "revenue_impact" in data


# ---------------------------------------------------------------------------
# Plans endpoint
# ---------------------------------------------------------------------------
class TestPlans:
    def test_plans_returns_200(self):
        response = client.get("/api/v1/plans")
        assert response.status_code == 200

    def test_plans_contains_all_three_plans(self):
        data = client.get("/api/v1/plans").json()
        assert "basic" in data
        assert "pro" in data
        assert "enterprise" in data

    def test_plans_basic_price(self):
        data = client.get("/api/v1/plans").json()
        assert data["basic"]["price_monthly"] == 99

    def test_plans_pro_price(self):
        data = client.get("/api/v1/plans").json()
        assert data["pro"]["price_monthly"] == 299

    def test_plans_enterprise_price(self):
        data = client.get("/api/v1/plans").json()
        assert data["enterprise"]["price_monthly"] == 999

    def test_plans_have_features(self):
        data = client.get("/api/v1/plans").json()
        for key in ("basic", "pro", "enterprise"):
            assert len(data[key]["features"]) > 0

    def test_plans_have_price_configured_flag(self):
        data = client.get("/api/v1/plans").json()
        for key in ("basic", "pro", "enterprise"):
            assert "price_configured" in data[key]


# ---------------------------------------------------------------------------
# Revenue endpoint
# ---------------------------------------------------------------------------
class TestRevenue:
    def test_revenue_returns_200_without_stripe(self, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        response = client.get("/api/v1/revenue")
        assert response.status_code == 200

    def test_revenue_no_stripe_shows_unconfigured(self, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        data = client.get("/api/v1/revenue").json()
        assert data["stripe_configured"] is False

    def test_revenue_contains_required_keys(self, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        data = client.get("/api/v1/revenue").json()
        assert "mrr" in data
        assert "active_subscriptions" in data
        assert "revenue_target" in data
        assert "target_progress_pct" in data
        assert "plans" in data

    def test_revenue_target_is_18k(self, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        data = client.get("/api/v1/revenue").json()
        assert data["revenue_target"] == 18000

    def test_revenue_plans_breakdown(self, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        data = client.get("/api/v1/revenue").json()
        for key in ("basic", "pro", "enterprise"):
            assert key in data["plans"]
            assert "name" in data["plans"][key]
            assert "price_monthly" in data["plans"][key]


# ---------------------------------------------------------------------------
# Dashboard endpoint
# ---------------------------------------------------------------------------
class TestDashboard:
    def test_dashboard_returns_html(self):
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_dashboard_contains_deal_desk_title(self):
        response = client.get("/dashboard")
        assert b"AI Deal Desk" in response.content

    def test_dashboard_contains_revenue_target(self):
        response = client.get("/dashboard")
        assert b"18K" in response.content or b"18,000" in response.content

    def test_dashboard_contains_lead_form(self):
        response = client.get("/dashboard")
        assert b"lead-form" in response.content


# ---------------------------------------------------------------------------
# Checkout endpoint
# ---------------------------------------------------------------------------
class TestCheckout:
    def test_checkout_without_stripe_returns_503(self, monkeypatch):
        monkeypatch.setattr("server.STRIPE_SECRET_KEY", "")
        response = client.post(
            "/api/v1/checkout",
            json={"plan": "pro", "success_url": "http://x.com/ok", "cancel_url": "http://x.com/cancel"},
        )
        assert response.status_code == 503

    def test_checkout_invalid_plan_returns_400(self, monkeypatch):
        monkeypatch.setattr("server.STRIPE_SECRET_KEY", "sk_test_fake")
        response = client.post(
            "/api/v1/checkout",
            json={"plan": "invalid", "success_url": "http://x.com/ok", "cancel_url": "http://x.com/cancel"},
        )
        assert response.status_code == 422  # Pydantic Literal validation

    def test_checkout_unconfigured_price_returns_503(self, monkeypatch):
        monkeypatch.setattr("server.STRIPE_SECRET_KEY", "sk_test_fake")
        monkeypatch.setattr("server.SUBSCRIPTION_PLANS", {
            **{k: v for k, v in __import__("server").SUBSCRIPTION_PLANS.items()},
            "pro": {**__import__("server").SUBSCRIPTION_PLANS["pro"], "price_id": ""},
        })
        response = client.post(
            "/api/v1/checkout",
            json={"plan": "pro", "success_url": "http://x.com/ok", "cancel_url": "http://x.com/cancel"},
        )
        assert response.status_code == 503

    def test_checkout_with_stripe_configured_calls_stripe(self, monkeypatch):
        """When Stripe is configured and price ID is set, a checkout URL is returned."""
        import server
        monkeypatch.setattr("server.STRIPE_SECRET_KEY", "sk_test_fake")
        monkeypatch.setattr("server.SUBSCRIPTION_PLANS", {
            **server.SUBSCRIPTION_PLANS,
            "pro": {**server.SUBSCRIPTION_PLANS["pro"], "price_id": "price_test_123"},
        })

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test_123"

        with patch("stripe.checkout.Session.create", return_value=mock_session):
            response = client.post(
                "/api/v1/checkout",
                json={
                    "plan": "pro",
                    "customer_email": "test@example.com",
                    "success_url": "http://x.com/ok",
                    "cancel_url": "http://x.com/cancel",
                },
            )
        assert response.status_code == 201
        data = response.json()
        assert data["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_123"
        assert data["plan"] == "pro"
        assert data["price_monthly"] == 299


# ---------------------------------------------------------------------------
# Lead capture endpoint
# ---------------------------------------------------------------------------
class TestLeadCapture:
    BASE_PAYLOAD = {
        "company_name": "Acme Corporation",
        "contact_name": "Jane Smith",
        "contact_email": "jane@acme.com",
        "plan": "pro",
        "industry": "Manufacturing",
        "pain_points": ["slow invoicing", "manual data entry"],
        "budget_range": "$50K-$100K",
        "urgency": "high",
        "success_url": "http://localhost/ok",
        "cancel_url": "http://localhost/cancel",
    }

    def test_lead_capture_returns_201(self):
        response = client.post("/api/v1/leads", json=self.BASE_PAYLOAD)
        assert response.status_code == 201

    def test_lead_capture_returns_proposal(self):
        data = client.post("/api/v1/leads", json=self.BASE_PAYLOAD).json()
        assert "proposal" in data
        assert data["proposal"]["proposal_id"].startswith("PROP-")

    def test_lead_capture_returns_proposal_id_at_top_level(self):
        data = client.post("/api/v1/leads", json=self.BASE_PAYLOAD).json()
        assert "proposal_id" in data
        assert data["proposal_id"] == data["proposal"]["proposal_id"]

    def test_lead_capture_has_message(self):
        data = client.post("/api/v1/leads", json=self.BASE_PAYLOAD).json()
        assert "message" in data
        assert len(data["message"]) > 0

    def test_lead_capture_no_checkout_url_without_stripe(self, monkeypatch):
        monkeypatch.setattr("server.STRIPE_SECRET_KEY", "")
        data = client.post("/api/v1/leads", json=self.BASE_PAYLOAD).json()
        assert data["checkout_url"] is None

    def test_lead_capture_checkout_url_with_stripe(self, monkeypatch):
        import server
        monkeypatch.setattr("server.STRIPE_SECRET_KEY", "sk_test_fake")
        monkeypatch.setattr("server.SUBSCRIPTION_PLANS", {
            **server.SUBSCRIPTION_PLANS,
            "pro": {**server.SUBSCRIPTION_PLANS["pro"], "price_id": "price_test_123"},
        })

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test_456"

        with patch("stripe.checkout.Session.create", return_value=mock_session):
            data = client.post("/api/v1/leads", json=self.BASE_PAYLOAD).json()

        assert data["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_456"

    def test_lead_missing_email_returns_422(self):
        payload = {**self.BASE_PAYLOAD}
        del payload["contact_email"]
        response = client.post("/api/v1/leads", json=payload)
        assert response.status_code == 422

    def test_lead_invalid_email_returns_422(self):
        response = client.post(
            "/api/v1/leads",
            json={**self.BASE_PAYLOAD, "contact_email": "not-an-email"},
        )
        assert response.status_code == 422

    def test_lead_missing_company_name_returns_422(self):
        payload = {**self.BASE_PAYLOAD}
        del payload["company_name"]
        response = client.post("/api/v1/leads", json=payload)
        assert response.status_code == 422

    def test_lead_invalid_plan_returns_422(self):
        response = client.post(
            "/api/v1/leads",
            json={**self.BASE_PAYLOAD, "plan": "ultra"},
        )
        assert response.status_code == 422

    def test_lead_proposal_has_three_pricing_tiers(self):
        data = client.post("/api/v1/leads", json=self.BASE_PAYLOAD).json()
        assert len(data["proposal"]["pricing_tiers"]) == 3


# ---------------------------------------------------------------------------
# Stripe webhook endpoint
# ---------------------------------------------------------------------------
class TestStripeWebhook:
    def test_webhook_without_secret_accepts_valid_json(self, monkeypatch):
        monkeypatch.setattr("server.STRIPE_WEBHOOK_SECRET", "")
        response = client.post(
            "/api/v1/stripe/webhook",
            content=json.dumps({"type": "checkout.session.completed", "data": {"object": {}}}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json()["received"] is True

    def test_webhook_without_secret_rejects_bad_json(self, monkeypatch):
        monkeypatch.setattr("server.STRIPE_WEBHOOK_SECRET", "")
        response = client.post(
            "/api/v1/stripe/webhook",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_webhook_with_secret_rejects_missing_signature(self, monkeypatch):
        monkeypatch.setattr("server.STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        response = client.post(
            "/api/v1/stripe/webhook",
            content=json.dumps({"type": "test"}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_webhook_event_types_handled(self, monkeypatch):
        monkeypatch.setattr("server.STRIPE_WEBHOOK_SECRET", "")
        event_types = [
            "checkout.session.completed",
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "invoice.payment_succeeded",
            "invoice.payment_failed",
        ]
        for event_type in event_types:
            response = client.post(
                "/api/v1/stripe/webhook",
                content=json.dumps({"type": event_type, "data": {"object": {}}}),
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200, f"Failed for event type: {event_type}"
            assert response.json()["type"] == event_type


# ---------------------------------------------------------------------------
# Proposals endpoint - validation
# ---------------------------------------------------------------------------
class TestProposalValidation:
    def test_missing_company_name_returns_422(self):
        response = client.post("/api/v1/proposals", json={})
        assert response.status_code == 422

    def test_company_name_too_short_returns_422(self):
        response = client.post("/api/v1/proposals", json={"company_name": "A"})
        assert response.status_code == 422

    def test_invalid_urgency_returns_422(self):
        response = client.post(
            "/api/v1/proposals",
            json={"company_name": "Acme Corp", "urgency": "critical"},
        )
        assert response.status_code == 422

    def test_valid_urgency_values(self):
        for urgency in ("low", "medium", "high"):
            response = client.post(
                "/api/v1/proposals",
                json={"company_name": "Acme Corp", "urgency": urgency},
            )
            # 201 or 500 (OpenAI not configured) but not 422
            assert response.status_code != 422, f"urgency={urgency} failed validation"

    def test_pain_points_list_too_long_returns_422(self):
        response = client.post(
            "/api/v1/proposals",
            json={
                "company_name": "Acme Corp",
                "pain_points": [f"pain_{i}" for i in range(21)],
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Proposals endpoint - successful creation (fallback path, no OpenAI key)
# ---------------------------------------------------------------------------
class TestProposalCreation:
    BASE_PAYLOAD = {
        "company_name": "Acme Corporation",
        "industry": "Manufacturing",
        "pain_points": ["slow invoicing", "manual data entry"],
        "budget_range": "$50K-$100K",
        "decision_makers": ["CFO", "VP Operations"],
        "competitors": ["SAP", "Oracle"],
        "urgency": "high",
    }

    def test_create_proposal_returns_201(self):
        response = client.post("/api/v1/proposals", json=self.BASE_PAYLOAD)
        assert response.status_code == 201

    def test_create_proposal_has_proposal_id(self):
        data = client.post("/api/v1/proposals", json=self.BASE_PAYLOAD).json()
        assert "proposal_id" in data
        assert data["proposal_id"].startswith("PROP-")

    def test_create_proposal_has_three_pricing_tiers(self):
        data = client.post("/api/v1/proposals", json=self.BASE_PAYLOAD).json()
        assert len(data["pricing_tiers"]) == 3

    def test_create_proposal_professional_tier_is_recommended(self):
        data = client.post("/api/v1/proposals", json=self.BASE_PAYLOAD).json()
        recommended = [t for t in data["pricing_tiers"] if t["recommended"]]
        assert len(recommended) == 1
        assert recommended[0]["name"] == "Professional"

    def test_create_proposal_high_urgency_increases_price(self):
        high = client.post(
            "/api/v1/proposals",
            json={**self.BASE_PAYLOAD, "urgency": "high"},
        ).json()
        low = client.post(
            "/api/v1/proposals",
            json={**self.BASE_PAYLOAD, "urgency": "low"},
        ).json()
        high_price = next(t["price"] for t in high["pricing_tiers"] if t["name"] == "Professional")
        low_price = next(t["price"] for t in low["pricing_tiers"] if t["name"] == "Professional")
        assert high_price > low_price

    def test_create_proposal_has_generated_at(self):
        data = client.post("/api/v1/proposals", json=self.BASE_PAYLOAD).json()
        assert "generated_at" in data

    def test_create_proposal_pdf_url_contains_proposal_id(self):
        data = client.post("/api/v1/proposals", json=self.BASE_PAYLOAD).json()
        assert data["proposal_id"] in data["pdf_url"]

    def test_create_proposal_default_urgency(self):
        response = client.post(
            "/api/v1/proposals",
            json={"company_name": "Beta Inc"},
        )
        assert response.status_code == 201
