"""Property tests for api/schemas/recommend.py — Pydantic DTO invariants (#340).

Tests:
- BidRecommendationRequest: valid inputs always construct successfully
- BidRecommendationRequest: current_bid < 0 raises ValidationError
- BidRecommendationRequest: team_budget < 0 raises ValidationError
- BidRecommendationRequest: roster_spots_remaining < 1 raises ValidationError
- BidRecommendationRequest: model_dump() round-trip preserves all fields
- BidRecommendationResponse: confidence in [0, 1] always constructs successfully
- BidRecommendationResponse: confidence outside [0, 1] raises ValidationError
- BidRecommendationResponse: recommended_bid is stored exactly
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from api.schemas.recommend import BidRecommendationRequest, BidRecommendationResponse


# ---------------------------------------------------------------------------
# BidRecommendationRequest — valid construction
# ---------------------------------------------------------------------------

@given(
    player_name=st.text(min_size=1, max_size=100),
    current_bid=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    team_budget=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    roster_spots=st.integers(min_value=1, max_value=50),
)
@settings(max_examples=50)
def test_request_valid_inputs_construct_successfully(player_name, current_bid, team_budget, roster_spots):
    """BidRecommendationRequest with valid fields always constructs without error."""
    req = BidRecommendationRequest(
        player_name=player_name,
        current_bid=current_bid,
        team_budget=team_budget,
        roster_spots_remaining=roster_spots,
    )
    assert req.player_name == player_name
    assert req.current_bid == current_bid
    assert req.team_budget == team_budget
    assert req.roster_spots_remaining == roster_spots


# ---------------------------------------------------------------------------
# BidRecommendationRequest — invalid inputs rejected
# ---------------------------------------------------------------------------

@given(
    player_name=st.text(min_size=1, max_size=50),
    current_bid=st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False),
    team_budget=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=30)
def test_request_negative_current_bid_rejected(player_name, current_bid, team_budget):
    """current_bid < 0 must raise ValidationError."""
    with pytest.raises(ValidationError):
        BidRecommendationRequest(
            player_name=player_name,
            current_bid=current_bid,
            team_budget=team_budget,
        )


@given(
    player_name=st.text(min_size=1, max_size=50),
    current_bid=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    team_budget=st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=30)
def test_request_negative_team_budget_rejected(player_name, current_bid, team_budget):
    """team_budget < 0 must raise ValidationError."""
    with pytest.raises(ValidationError):
        BidRecommendationRequest(
            player_name=player_name,
            current_bid=current_bid,
            team_budget=team_budget,
        )


@given(
    player_name=st.text(min_size=1, max_size=50),
    roster_spots=st.integers(max_value=0),
)
@settings(max_examples=30)
def test_request_zero_or_negative_roster_spots_rejected(player_name, roster_spots):
    """roster_spots_remaining < 1 must raise ValidationError."""
    with pytest.raises(ValidationError):
        BidRecommendationRequest(
            player_name=player_name,
            current_bid=0.0,
            team_budget=100.0,
            roster_spots_remaining=roster_spots,
        )


@given(
    player_name=st.just(""),
)
@settings(max_examples=5)
def test_request_empty_player_name_rejected(player_name):
    """Empty player_name (min_length=1) must raise ValidationError."""
    with pytest.raises(ValidationError):
        BidRecommendationRequest(
            player_name=player_name,
            current_bid=0.0,
            team_budget=100.0,
        )


# ---------------------------------------------------------------------------
# BidRecommendationRequest — round-trip
# ---------------------------------------------------------------------------

@given(
    player_name=st.text(min_size=1, max_size=50),
    current_bid=st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    team_budget=st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    roster_spots=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=30)
def test_request_model_dump_round_trip(player_name, current_bid, team_budget, roster_spots):
    """model.model_dump() → BidRecommendationRequest(**dict) preserves all fields."""
    original = BidRecommendationRequest(
        player_name=player_name,
        current_bid=current_bid,
        team_budget=team_budget,
        roster_spots_remaining=roster_spots,
    )
    reconstructed = BidRecommendationRequest(**original.model_dump())
    assert reconstructed.player_name == original.player_name
    assert reconstructed.current_bid == original.current_bid
    assert reconstructed.team_budget == original.team_budget
    assert reconstructed.roster_spots_remaining == original.roster_spots_remaining


# ---------------------------------------------------------------------------
# BidRecommendationResponse — valid confidence range
# ---------------------------------------------------------------------------

@given(
    recommended_bid=st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    rationale=st.text(min_size=1, max_size=200),
)
@settings(max_examples=50)
def test_response_valid_confidence_constructs(recommended_bid, confidence, rationale):
    """BidRecommendationResponse with confidence in [0, 1] always constructs."""
    resp = BidRecommendationResponse(
        recommended_bid=recommended_bid,
        confidence=confidence,
        rationale=rationale,
    )
    assert resp.recommended_bid == recommended_bid
    assert resp.confidence == confidence


@given(
    confidence=st.one_of(
        st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False),
        st.floats(min_value=1.001, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
)
@settings(max_examples=30)
def test_response_confidence_outside_unit_interval_rejected(confidence):
    """confidence outside [0, 1] must raise ValidationError."""
    with pytest.raises(ValidationError):
        BidRecommendationResponse(
            recommended_bid=10.0,
            confidence=confidence,
            rationale="test",
        )
