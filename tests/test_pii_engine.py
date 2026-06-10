"""
tests/test_pii_engine.py — Unit tests for the PrivacyEngine redaction pipeline.

Run with: pytest tests/ -v
"""

import pytest
from pii_engine import PrivacyEngine, RedactionSummary


@pytest.fixture(scope="module")
def engine():
    """Shared PrivacyEngine instance — Presidio loads once per test session."""
    return PrivacyEngine(entropy_threshold=4.0)


# ─────────────────────────────────────────────────────────────────────────────
# Credential regex tests (no Presidio dependency)
# ─────────────────────────────────────────────────────────────────────────────

class TestCredentialRegex:
    def test_password_equals(self, engine):
        text, summary = engine.sanitize_text('password=MySecretPass123')
        assert "[REDACTED_CREDENTIAL]" in text
        assert summary.api_keys_tokens >= 1

    def test_api_key_colon(self, engine):
        text, summary = engine.sanitize_text('api_key: sk-abcdef123456789012345678901234')
        assert "[REDACTED" in text

    def test_stripe_secret(self, engine):
        text, summary = engine.sanitize_text('STRIPE_SECRET=sk_live_ABCDEF1234567890abcdef')
        assert "[REDACTED" in text

    def test_bearer_token(self, engine):
        text, summary = engine.sanitize_text('Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9')
        assert "[REDACTED" in text

    def test_clean_text_unchanged(self, engine):
        clean = "The quarterly revenue target is $4.2 million."
        text, summary = engine.sanitize_text(clean)
        # No credentials — content should survive
        assert "quarterly revenue" in text
        assert summary.api_keys_tokens == 0


# ─────────────────────────────────────────────────────────────────────────────
# Shannon entropy tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEntropyScanner:
    def test_high_entropy_hex_token(self, engine):
        # Simulated raw OAuth token — very high entropy
        text, summary = engine.sanitize_text(
            "Token value: a3f9c2d8b1e7f4a6c9d2e8f3b7a1c6d9"
        )
        # Either entropy or hex regex should catch it
        assert "[REDACTED" in text or summary.high_entropy_secrets >= 1

    def test_normal_prose_passes(self, engine):
        prose = "The board meeting is scheduled for Tuesday afternoon."
        text, summary = engine.sanitize_text(prose)
        assert "board meeting" in text
        assert summary.high_entropy_secrets == 0

    def test_empty_string(self, engine):
        text, summary = engine.sanitize_text("")
        assert text == ""
        assert summary.total == 0


# ─────────────────────────────────────────────────────────────────────────────
# Risk score
# ─────────────────────────────────────────────────────────────────────────────

class TestRiskScore:
    def test_zero_risk_clean_text(self, engine):
        _, summary = engine.sanitize_text("Hello world, today is a nice day.")
        assert summary.risk_score == 0.0

    def test_risk_caps_at_one(self):
        s = RedactionSummary(ssn=10, credit_cards=10, api_keys_tokens=10)
        assert s.risk_score == 1.0

    def test_medium_risk(self):
        s = RedactionSummary(email_addresses=3, phone_numbers=2)
        # 3*0.1 + 2*0.1 = 0.5
        assert abs(s.risk_score - 0.5) < 0.01

    def test_high_risk(self):
        s = RedactionSummary(ssn=1, credit_cards=1)
        # 0.3 + 0.3 = 0.6
        assert abs(s.risk_score - 0.6) < 0.01


# ─────────────────────────────────────────────────────────────────────────────
# Redaction summary totals
# ─────────────────────────────────────────────────────────────────────────────

class TestRedactionSummary:
    def test_total_aggregates_all_fields(self):
        s = RedactionSummary(
            credit_cards=1, ssn=1, email_addresses=2, phone_numbers=1,
            person_names=3, api_keys_tokens=1, high_entropy_secrets=2
        )
        assert s.total == 11

    def test_empty_summary_total_zero(self):
        assert RedactionSummary().total == 0
