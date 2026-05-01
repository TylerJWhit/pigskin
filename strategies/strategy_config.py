"""StrategyConfig Pydantic model — serializable strategy descriptor (issue #259)."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, field_validator


class StrategyConfig(BaseModel):
    """Serializable descriptor for a bidding strategy.

    Fields
    ------
    name:
        Machine key used in AVAILABLE_STRATEGIES / create_strategy() (e.g. 'vor').
    display_name:
        Human-readable label (e.g. 'Value Over Replacement').
    description:
        One-sentence description of the strategy's bidding approach.
    base_class:
        Fully-qualified class name string validated against _BASE_CLASS_ALLOWLIST
        in StrategyRegistry before instantiation.
    version:
        Semantic version of the config definition, defaults to '1.0.0'.
    parameters:
        Optional key-value overrides passed to the strategy constructor.
    tags:
        Arbitrary classification labels (e.g. ['benchmark', 'aggressive']).
    """

    name: str
    display_name: str
    description: str
    base_class: str
    version: str = "1.0.0"
    parameters: Dict[str, Any] = {}
    tags: List[str] = []

    @field_validator("name")
    @classmethod
    def _name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty")
        return v

    @field_validator("base_class")
    @classmethod
    def _base_class_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("base_class must not be empty")
        return v
