"""Tests for PersonaMemory types — validation, decay, serialization."""

import time
import pytest

from sense_memory.types import (
    PersonaMemory,
    IntrospectionReport,
    DEFAULT_DOMAINS,
    DEFAULT_FACETS,
    STATE_ACTIVE,
    STATE_FADING,
    STATE_FORGOTTEN,
    STATE_DISSOLVED,
    THRESHOLD_FADING,
    THRESHOLD_FORGOTTEN,
    THRESHOLD_DISSOLVED,
    DEFAULT_HALFLIFE_DAYS,
)


# ─── Construction ────────────────────────────────────────────────────

class TestPersonaMemoryConstruction:

    def test_basic_creation(self):
        m = PersonaMemory(domain="self", facet="beliefs", key="test-key", value="test value")
        assert m.domain == "self"
        assert m.facet == "beliefs"
        assert m.key == "test-key"
        assert m.value == "test value"
        assert m.relevance == 1.0
        assert m.state == STATE_ACTIVE
        assert m.confidence == 1.0
        assert m.connections == ()
        assert m.contradicts == ()
        assert m.themes == ()

    def test_with_themes_and_connections(self):
        m = PersonaMemory(
            domain="people", facet="facts", key="vergel-likes-js",
            value="Vergel prefers vanilla JS",
            themes=("javascript", "preferences"),
            connections=("vergel-role",),
        )
        assert m.themes == ("javascript", "preferences")
        assert m.connections == ("vergel-role",)

    def test_frozen(self):
        m = PersonaMemory(domain="self", facet="facts", key="test", value="val")
        with pytest.raises(AttributeError):
            m.value = "changed"

    def test_d_tag(self):
        m = PersonaMemory(domain="projects", facet="decisions", key="chose-orpheus", value="warm voice")
        assert m.d_tag == "sense-memory/persona/projects/decisions/chose-orpheus"


# ─── Validation ──────────────────────────────────────────────────────

class TestPersonaMemoryValidation:

    def test_empty_domain(self):
        with pytest.raises(ValueError, match="Domain"):
            PersonaMemory(domain="", facet="facts", key="k", value="v")

    def test_empty_facet(self):
        with pytest.raises(ValueError, match="Facet"):
            PersonaMemory(domain="self", facet="", key="k", value="v")

    def test_empty_key(self):
        with pytest.raises(ValueError, match="non-empty"):
            PersonaMemory(domain="self", facet="facts", key="", value="v")

    def test_slash_in_domain(self):
        with pytest.raises(ValueError, match="invalid"):
            PersonaMemory(domain="self/bad", facet="facts", key="k", value="v")

    def test_slash_in_facet(self):
        with pytest.raises(ValueError, match="invalid"):
            PersonaMemory(domain="self", facet="facts/bad", key="k", value="v")

    def test_invalid_state(self):
        with pytest.raises(ValueError, match="state"):
            PersonaMemory(domain="self", facet="facts", key="k", value="v", state="invalid")

    def test_confidence_out_of_range(self):
        with pytest.raises(ValueError, match="confidence"):
            PersonaMemory(domain="self", facet="facts", key="k", value="v", confidence=1.5)

    def test_negative_halflife(self):
        with pytest.raises(ValueError, match="halflife"):
            PersonaMemory(domain="self", facet="facts", key="k", value="v", halflife_days=-1)

    def test_value_too_long(self):
        with pytest.raises(ValueError, match="too long"):
            PersonaMemory(domain="self", facet="facts", key="k", value="x" * 70000)


# ─── Relevance Decay ────────────────────────────────────────────────

class TestRelevanceDecay:

    def test_fresh_memory_full_relevance(self):
        now = time.time()
        m = PersonaMemory(
            domain="self", facet="facts", key="test", value="v",
            last_accessed=now,
        )
        assert m.current_relevance(now) == pytest.approx(1.0, abs=0.01)

    def test_halflife_decay(self):
        now = time.time()
        thirty_days_ago = now - (30 * 86400)
        m = PersonaMemory(
            domain="self", facet="facts", key="test", value="v",
            halflife_days=30.0,
            last_accessed=thirty_days_ago,
        )
        # After one halflife, should be ~0.5
        assert m.current_relevance(now) == pytest.approx(0.5, abs=0.05)

    def test_two_halflives(self):
        now = time.time()
        sixty_days_ago = now - (60 * 86400)
        m = PersonaMemory(
            domain="self", facet="facts", key="test", value="v",
            halflife_days=30.0,
            last_accessed=sixty_days_ago,
        )
        # After two halflives, should be ~0.25
        assert m.current_relevance(now) == pytest.approx(0.25, abs=0.05)

    def test_connections_boost_relevance(self):
        now = time.time()
        thirty_days_ago = now - (30 * 86400)

        m_alone = PersonaMemory(
            domain="self", facet="facts", key="alone", value="v",
            halflife_days=30.0, last_accessed=thirty_days_ago,
        )
        m_connected = PersonaMemory(
            domain="self", facet="facts", key="connected", value="v",
            halflife_days=30.0, last_accessed=thirty_days_ago,
            connections=("a", "b", "c"),  # 3 connections = 30% boost
        )

        assert m_connected.current_relevance(now) > m_alone.current_relevance(now)

    def test_contradiction_penalty(self):
        now = time.time()
        m_clean = PersonaMemory(
            domain="self", facet="beliefs", key="clean", value="v",
            last_accessed=now,
        )
        m_contradicted = PersonaMemory(
            domain="self", facet="beliefs", key="contradicted", value="v",
            last_accessed=now,
            contradicts=("other-belief",),
        )

        assert m_contradicted.current_relevance(now) < m_clean.current_relevance(now)

    def test_superseded_decays_faster(self):
        now = time.time()
        ten_days_ago = now - (10 * 86400)

        m_normal = PersonaMemory(
            domain="self", facet="facts", key="normal", value="v",
            halflife_days=30.0, last_accessed=ten_days_ago,
        )
        m_superseded = PersonaMemory(
            domain="self", facet="facts", key="superseded", value="v",
            halflife_days=30.0, last_accessed=ten_days_ago,
            superseded_by="newer-fact",
        )

        assert m_superseded.current_relevance(now) < m_normal.current_relevance(now)


# ─── State Computation ───────────────────────────────────────────────

class TestComputeState:

    def test_fresh_is_active(self):
        m = PersonaMemory(domain="self", facet="facts", key="k", value="v")
        assert m.compute_state() == STATE_ACTIVE

    def test_old_is_fading(self):
        now = time.time()
        # After ~1.9 halflives, relevance drops clearly below 0.3
        old = now - (58 * 86400)  # ~58 days with 30-day halflife → 0.5^1.93 ≈ 0.26
        m = PersonaMemory(
            domain="self", facet="facts", key="k", value="v",
            halflife_days=30.0, last_accessed=old,
        )
        assert m.compute_state(now) == STATE_FADING

    def test_very_old_is_forgotten(self):
        now = time.time()
        very_old = now - (100 * 86400)  # ~100 days
        m = PersonaMemory(
            domain="self", facet="facts", key="k", value="v",
            halflife_days=30.0, last_accessed=very_old,
        )
        assert m.compute_state(now) == STATE_FORGOTTEN

    def test_ancient_is_dissolved(self):
        now = time.time()
        ancient = now - (200 * 86400)  # ~200 days
        m = PersonaMemory(
            domain="self", facet="facts", key="k", value="v",
            halflife_days=30.0, last_accessed=ancient,
        )
        assert m.compute_state(now) == STATE_DISSOLVED


# ─── Serialization ───────────────────────────────────────────────────

class TestSerialization:

    def test_round_trip(self):
        m = PersonaMemory(
            domain="people", facet="facts", key="vergel-role",
            value="Solo founder, builds sovereign tools",
            themes=("identity", "humanjava"),
            connections=("vergel-likes-js",),
            confidence=0.9,
            source="conversation-2026-03-29",
        )
        d = m.to_dict()
        m2 = PersonaMemory.from_dict(d)

        assert m2.domain == m.domain
        assert m2.facet == m.facet
        assert m2.key == m.key
        assert m2.value == m.value
        assert m2.themes == m.themes
        assert m2.connections == m.connections
        assert m2.confidence == m.confidence
        assert m2.source == m.source

    def test_to_dict_type_field(self):
        m = PersonaMemory(domain="self", facet="facts", key="k", value="v")
        d = m.to_dict()
        assert d["type"] == "sense-memory:persona"

    def test_from_dict_defaults(self):
        m = PersonaMemory.from_dict({
            "domain": "self", "facet": "facts", "key": "k", "value": "v",
        })
        assert m.relevance == 1.0
        assert m.state == STATE_ACTIVE
        assert m.connections == ()


# ─── IntrospectionReport ─────────────────────────────────────────────

class TestIntrospectionReport:

    def test_creation(self):
        r = IntrospectionReport(
            total_memories=50, active=30, fading=15, forgotten=5,
        )
        assert r.total_memories == 50
        assert r.active == 30

    def test_to_dict(self):
        r = IntrospectionReport(total_memories=10, active=8, fading=2)
        d = r.to_dict()
        assert d["type"] == "sense-memory:introspection"
        assert d["total_memories"] == 10

    def test_frozen(self):
        r = IntrospectionReport()
        with pytest.raises(AttributeError):
            r.total_memories = 99


# ─── Constants ───────────────────────────────────────────────────────

class TestConstants:

    def test_default_domains(self):
        assert "self" in DEFAULT_DOMAINS
        assert "people" in DEFAULT_DOMAINS
        assert "projects" in DEFAULT_DOMAINS

    def test_default_facets(self):
        assert "facts" in DEFAULT_FACETS
        assert "beliefs" in DEFAULT_FACETS
        assert "decisions" in DEFAULT_FACETS
