"""Tests for the AI-Powered Deal Desk API."""
import os
import sys

import pytest
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
        assert "solo" in data["pricing"]


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
