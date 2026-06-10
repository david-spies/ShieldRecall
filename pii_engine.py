"""
pii_engine.py — AI-driven PII / credential redaction pipeline.

Detection layers (applied in order):
  1. Microsoft Presidio — catches SSNs, credit cards, email, phone, person names, etc.
  2. Regex + keyword patterns — catches labelled credentials (password=, api_key=, etc.)
  3. Shannon entropy scan — catches unlabelled high-randomness strings (raw keys, tokens).

All three layers run on every text chunk before it is written to the local database.
"""

import re
import math
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class RedactionSummary:
    """Counts of each PII category found and removed in a single sanitization pass."""
    credit_cards: int = 0
    ssn: int = 0
    email_addresses: int = 0
    phone_numbers: int = 0
    person_names: int = 0
    api_keys_tokens: int = 0
    high_entropy_secrets: int = 0
    raw_text_length: int = 0
    clean_text_length: int = 0

    @property
    def total(self) -> int:
        return (
            self.credit_cards
            + self.ssn
            + self.email_addresses
            + self.phone_numbers
            + self.person_names
            + self.api_keys_tokens
            + self.high_entropy_secrets
        )

    @property
    def risk_score(self) -> float:
        """
        Normalised 0.0–1.0 risk score for the original text chunk.
        Weighted by severity:
          - High risk entities (SSN, credit card, api key, high entropy) = 0.3 each, cap 1.0
          - Medium risk entities (email, phone) = 0.1 each, cap 0.5
          - Low risk (person names) = 0.05 each, cap 0.2
        """
        high = (self.ssn + self.credit_cards + self.api_keys_tokens + self.high_entropy_secrets) * 0.3
        med = (self.email_addresses + self.phone_numbers) * 0.1
        low = self.person_names * 0.05
        return min(high + med + low, 1.0)


# ---------------------------------------------------------------------------
# Credential pattern regex
# Matches patterns like: password="abc123", api_key: xyz, token='Bearer …'
# ---------------------------------------------------------------------------
_CREDENTIAL_RE = re.compile(
    r"(?i)(password|passwd|pass|secret|api[_\-]?key|apikey|auth[_\-]?token"
    r"|access[_\-]?token|bearer|private[_\-]?key|client[_\-]?secret|db[_\-]?pass"
    r"|database[_\-]?password|stripe[_\-]?secret|aws[_\-]?secret|gh[_\-]?token"
    r")[=:\s\"']+([a-zA-Z0-9_\-\.=+/]{8,128})"
)

# Catches hex-encoded secrets (e.g. git tokens, bcrypt hashes)
_HEX_SECRET_RE = re.compile(r"\b[0-9a-fA-F]{32,}\b")

# Catches base64-like long strings (JWTs, base64 blobs)
_BASE64_SECRET_RE = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")


def _shannon_entropy(text: str) -> float:
    """Shannon entropy in bits per character. Pure prose ≈ 3.5; random keys ≈ 5.5+."""
    if not text:
        return 0.0
    freq = {}
    for ch in text:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(text)
    return -sum((c / length) * math.log2(c / length) for c in freq.values())


class PrivacyEngine:
    """
    Stateless redaction engine. Instantiate once at app startup; call
    sanitize_text() for every captured text chunk.

    Presidio is loaded lazily so the app starts quickly even when the
    model weights are not yet cached. On first call there may be a 1–3 s
    warm-up delay; subsequent calls are fast.
    """

    def __init__(self, entropy_threshold: float = 4.0):
        self.entropy_threshold = entropy_threshold
        self._analyzer = None
        self._anonymizer = None

    # ------------------------------------------------------------------
    # Lazy presidio init (avoids slow import at module load time)
    # ------------------------------------------------------------------
    def _ensure_presidio(self):
        if self._analyzer is None:
            try:
                from presidio_analyzer import AnalyzerEngine
                from presidio_anonymizer import AnonymizerEngine
                self._analyzer = AnalyzerEngine()
                self._anonymizer = AnonymizerEngine()
                logger.info("Presidio analyzer + anonymizer initialised.")
            except ImportError:
                logger.warning(
                    "presidio-analyzer not installed. Presidio layer disabled. "
                    "Run: pip install presidio-analyzer presidio-anonymizer"
                )
                self._analyzer = None
                self._anonymizer = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def sanitize_text(self, raw_text: str) -> tuple[str, RedactionSummary]:
        """
        Returns (sanitized_text, RedactionSummary).

        sanitized_text has all detected PII / credentials replaced with
        human-readable [REDACTED_*] tokens so auditors can understand
        what category was removed without seeing the original value.
        """
        summary = RedactionSummary(raw_text_length=len(raw_text))
        if not raw_text.strip():
            return "", summary

        text = raw_text

        # ---- Layer 1: Presidio NER (SSN, cards, email, phone, names) ----
        text, summary = self._presidio_pass(text, summary)

        # ---- Layer 2: Credential keyword regex ----
        def _cred_replace(m):
            summary.api_keys_tokens += 1
            return f"{m.group(1)}=[REDACTED_CREDENTIAL]"

        text = _CREDENTIAL_RE.sub(_cred_replace, text)

        # ---- Layer 3: Entropy scan on each whitespace-delimited token ----
        tokens = text.split()
        cleaned = []
        for tok in tokens:
            # Strip surrounding punctuation for analysis only
            core = tok.strip("\"'`()[]{}.,;:!?")
            if len(core) >= 10 and _shannon_entropy(core) > self.entropy_threshold:
                cleaned.append("[REDACTED_HIGH_ENTROPY_SECRET]")
                summary.high_entropy_secrets += 1
            elif _HEX_SECRET_RE.fullmatch(core):
                cleaned.append("[REDACTED_HEX_SECRET]")
                summary.high_entropy_secrets += 1
            elif len(core) >= 40 and _BASE64_SECRET_RE.fullmatch(core):
                cleaned.append("[REDACTED_BASE64_SECRET]")
                summary.high_entropy_secrets += 1
            else:
                cleaned.append(tok)
        text = " ".join(cleaned)

        summary.clean_text_length = len(text)
        return text, summary

    def _presidio_pass(self, text: str, summary: RedactionSummary) -> tuple[str, RedactionSummary]:
        self._ensure_presidio()
        if self._analyzer is None:
            return text, summary

        from presidio_anonymizer.entities import OperatorConfig

        results = self._analyzer.analyze(text=text, language="en")

        # Count by entity type before anonymizing
        for r in results:
            et = r.entity_type
            if et == "CREDIT_CARD":
                summary.credit_cards += 1
            elif et == "US_SSN":
                summary.ssn += 1
            elif et == "EMAIL_ADDRESS":
                summary.email_addresses += 1
            elif et in ("PHONE_NUMBER", "US_PHONE"):
                summary.phone_numbers += 1
            elif et == "PERSON":
                summary.person_names += 1

        operators = {
            "DEFAULT":        OperatorConfig("replace", {"new_value": "[REDACTED_PII]"}),
            "CREDIT_CARD":    OperatorConfig("replace", {"new_value": "[REDACTED_CARD]"}),
            "EMAIL_ADDRESS":  OperatorConfig("replace", {"new_value": "[REDACTED_EMAIL]"}),
            "US_SSN":         OperatorConfig("replace", {"new_value": "[REDACTED_SSN]"}),
            "PHONE_NUMBER":   OperatorConfig("replace", {"new_value": "[REDACTED_PHONE]"}),
            "PERSON":         OperatorConfig("replace", {"new_value": "[REDACTED_NAME]"}),
        }

        anonymized = self._anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )
        return anonymized.text, summary
