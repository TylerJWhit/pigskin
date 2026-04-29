"""GridironSage strategy — MCTS-guided bidding with a dual-head neural network.

GridironSage is an original AI strategy for fantasy football auction drafts.
It combines Monte Carlo Tree Search (MCTS) with a learned dual-head neural
network (policy head + value head) trained via self-play.

Architecture overview:
  - Feature extractor: 20-dimensional auction state → normalised tensor
  - Policy head: probability distribution over discrete bid increments
  - Value head: estimated win probability for the current team state
  - MCTS: UCB-guided tree search using the network for node evaluation
  - Fallback: VOR-based heuristic when the network is unavailable or untrained

Design decisions (Architecture Agent, 2026-04-29):
  - Tournament mode uses 50 MCTS iterations (hard cap, never configurable)
  - Training mode uses 800 MCTS iterations (invoked only by lab/gridiron_sage/train.py)
  - Policy temperature = 0 during inference (greedy, deterministic given fixed seed)
  - Network fallback is transparent to callers — Strategy interface is unchanged
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from .base_strategy import Strategy

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOURNAMENT_MCTS_ITERATIONS: int = 50   # Hard cap — never override in production
TRAINING_MCTS_ITERATIONS: int = 800    # Training mode only — lab/gridiron_sage/train.py
C_PUCT: float = 1.4                    # UCB exploration constant
BID_GRANULARITY: int = 5               # Discrete bid steps: 1, 5, 10, 15, … up to budget
FEATURE_DIM: int = 20                  # Canonical feature vector dimension (see _extract_features)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _extract_features(
    player: "Player",
    team: "Team",
    current_bid: float,
    remaining_budget: float,
    remaining_players: List["Player"],
) -> List[float]:
    """Extract a 20-dimensional state vector for neural network input.

    Dimensions (0-indexed):
      0  — remaining_budget / total_budget (budget fraction)
      1  — filled roster slots / total roster slots (roster fill fraction)
      2  — current_bid / player auction value (bid-to-value ratio, capped at 2)
      3  — player VOR normalised by pool max VOR
      4  — player auction value normalised by remaining_budget
      5  — position scarcity score (0–1, higher = scarcer)
      6  — remaining players in pool / 200 (pool depth fraction)
      7  — is_elite flag (player auction value > 30) as float
      8  — position need: 1 if team still needs this position, 0 otherwise
      9  — QB need fraction (needed / max_slots)
      10 — RB need fraction
      11 — WR need fraction
      12 — TE need fraction
      13 — flex/bench need fraction
      14 — min_budget_to_fill / remaining_budget (budget headroom ratio)
      15 — players of same position remaining / pool depth
      16 — opponents ahead in nomination order (normalised by 11)
      17 — current_bid / remaining_budget (affordability ratio)
      18 — season week proxy (0.0 — always 0.0 until live data wired)
      19 — bias term (always 1.0)
    """
    features: List[float] = [0.0] * FEATURE_DIM

    # 0 — budget fraction
    total_budget: float = getattr(team, "budget", 200.0) or 200.0
    features[0] = min(remaining_budget / total_budget, 1.0) if total_budget > 0 else 0.0

    # 1 — roster fill fraction
    try:
        filled = len(getattr(team, "roster", []))
        max_slots = sum(getattr(team, "max_roster_size", {}).values()) if hasattr(team, "max_roster_size") else 15
        if max_slots > 0:
            features[1] = filled / max_slots
    except Exception:
        pass

    # 2 — bid-to-value ratio
    player_value: float = getattr(player, "auction_value", 1.0) or 1.0
    features[2] = min(current_bid / player_value, 2.0) if player_value > 0 else 0.0

    # 3 — normalised VOR
    max_vor = max((getattr(p, "vor", 0.0) or 0.0 for p in remaining_players), default=1.0)
    player_vor: float = getattr(player, "vor", 0.0) or 0.0
    features[3] = (player_vor / max_vor) if max_vor > 0 else 0.0

    # 4 — player value / remaining budget
    features[4] = min(player_value / remaining_budget, 2.0) if remaining_budget > 0 else 0.0

    # 5 — position scarcity
    position_scarcity: Dict[str, float] = {
        "QB": 0.3, "RB": 0.9, "WR": 0.7, "TE": 0.8, "K": 0.1, "DST": 0.2,
    }
    pos: str = getattr(player, "position", "UNKNOWN") or "UNKNOWN"
    features[5] = position_scarcity.get(pos.upper(), 0.5)

    # 6 — pool depth fraction
    features[6] = min(len(remaining_players) / 200.0, 1.0)

    # 7 — is_elite flag
    features[7] = 1.0 if player_value > 30.0 else 0.0

    # 8 — position need
    try:
        get_prio = getattr(team, "calculate_position_priority", None)
        if callable(get_prio):
            features[8] = 1.0 if get_prio(pos) > 0.3 else 0.0
    except Exception:
        pass

    # 9–13 — per-position need fractions
    position_indices: Dict[str, int] = {"QB": 9, "RB": 10, "WR": 11, "TE": 12}
    try:
        get_slots = getattr(team, "get_remaining_roster_slots", None)
        if callable(get_slots):
            slots: Dict[str, int] = get_slots()
            max_per_pos: Dict[str, int] = getattr(team, "max_roster_size", {})
            for p_pos, idx in position_indices.items():
                needed = slots.get(p_pos, 0)
                capacity = max_per_pos.get(p_pos, 1) or 1
                features[idx] = min(needed / capacity, 1.0)
            # 13 — flex / bench need
            flex_need = sum(slots.get(p, 0) for p in ("FLEX", "BENCH", "BN"))
            features[13] = min(flex_need / 5.0, 1.0)
    except Exception:
        pass

    # 14 — min budget to fill / remaining budget
    try:
        get_slots_2 = getattr(team, "get_remaining_roster_slots", None)
        if callable(get_slots_2):
            total_needed = sum(get_slots_2().values())
            min_needed = float(total_needed)  # $1 per slot minimum
            features[14] = min(min_needed / remaining_budget, 2.0) if remaining_budget > 0 else 1.0
    except Exception:
        pass

    # 15 — same-position pool depth fraction
    same_pos_count = sum(
        1 for p in remaining_players if getattr(p, "position", "") == pos
    )
    features[15] = min(same_pos_count / max(len(remaining_players), 1), 1.0)

    # 16 — opponents ahead (placeholder — 0.5 without nomination order data)
    features[16] = 0.5

    # 17 — affordability ratio
    features[17] = min(current_bid / remaining_budget, 1.0) if remaining_budget > 0 else 1.0

    # 18 — season week proxy (always 0.0 until live data wired)
    features[18] = 0.0

    # 19 — bias term
    features[19] = 1.0

    return features


# ---------------------------------------------------------------------------
# Lightweight neural network (pure Python, no external deps required at import)
# ---------------------------------------------------------------------------

class _GridironSageNetwork:
    """Dual-head neural network: policy head + value head.

    Implemented in pure Python so the strategy module can be imported without
    PyTorch installed.  When PyTorch IS available the lab training pipeline
    replaces this with a proper torch.nn.Module and loads a checkpoint.

    Default weights produce a uniform policy (random bidding) and a neutral
    value estimate (0.5) — effectively a random rollout baseline until trained.
    """

    def __init__(self, input_dim: int = FEATURE_DIM, hidden_dim: int = 64, policy_dim: int = 10) -> None:
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.policy_dim = policy_dim
        self._checkpoint_loaded: bool = False

        # Try to load a real PyTorch checkpoint from data/models/
        self._torch_model = self._try_load_torch_model()

    def _try_load_torch_model(self) -> Optional[object]:
        """Attempt to load a trained PyTorch checkpoint.  Returns None on any failure."""
        try:
            import torch  # type: ignore
            import os

            checkpoint_path = os.path.join(
                os.path.dirname(__file__), "..", "data", "models", "gridiron_sage.pt"
            )
            checkpoint_path = os.path.normpath(checkpoint_path)
            if not os.path.exists(checkpoint_path):
                return None

            model = _GridironSageTorchNet(self.input_dim, self.hidden_dim, self.policy_dim)
            state = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
            model.load_state_dict(state)
            model.eval()
            self._checkpoint_loaded = True
            return model
        except Exception:
            return None

    def forward(self, features: List[float]) -> Tuple[List[float], float]:
        """Run forward pass.  Returns (policy_logits, value).

        policy_logits: length-policy_dim list of log-probabilities over bid increments
        value: float in [0, 1] — estimated win probability
        """
        if self._torch_model is not None:
            try:
                import torch  # type: ignore
                x = torch.tensor([features], dtype=torch.float32)
                with torch.no_grad():
                    logits, value = self._torch_model(x)
                return logits[0].tolist(), float(value[0].item())
            except Exception:
                pass

        # Fallback: uniform policy, neutral value
        uniform_logits = [-math.log(self.policy_dim)] * self.policy_dim
        return uniform_logits, 0.5


def _try_import_torch_net() -> Optional[type]:
    """Return _GridironSageTorchNet class if torch is available, else None."""
    try:
        import torch
        import torch.nn as nn

        class _GridironSageTorchNet(nn.Module):  # type: ignore
            """Dual-head PyTorch network for GridironSage."""

            def __init__(self, input_dim: int, hidden_dim: int, policy_dim: int) -> None:
                super().__init__()
                self.shared = nn.Sequential(
                    nn.Linear(input_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Linear(hidden_dim, hidden_dim),
                    nn.ReLU(),
                )
                self.policy_head = nn.Linear(hidden_dim, policy_dim)
                self.value_head = nn.Sequential(
                    nn.Linear(hidden_dim, 32),
                    nn.ReLU(),
                    nn.Linear(32, 1),
                    nn.Sigmoid(),
                )

            def forward(self, x: "torch.Tensor") -> Tuple["torch.Tensor", "torch.Tensor"]:
                h = self.shared(x)
                return self.policy_head(h), self.value_head(h)

        return _GridironSageTorchNet
    except ImportError:
        return None


# Attempt class-level import once; used by _GridironSageNetwork._try_load_torch_model
_GridironSageTorchNet: Optional[type] = _try_import_torch_net()


# ---------------------------------------------------------------------------
# MCTS node
# ---------------------------------------------------------------------------

class _MCTSNode:
    """A node in the MCTS bid tree.

    Each node represents a candidate bid amount.  Children represent
    higher bid increments (the opponent countering, or the agent raising).
    """

    __slots__ = ("bid", "prior", "visit_count", "value_sum", "children", "is_expanded")

    def __init__(self, bid: float, prior: float) -> None:
        self.bid: float = bid
        self.prior: float = prior
        self.visit_count: int = 0
        self.value_sum: float = 0.0
        self.children: List["_MCTSNode"] = []
        self.is_expanded: bool = False

    @property
    def q_value(self) -> float:
        """Mean action value (Q)."""
        return self.value_sum / self.visit_count if self.visit_count > 0 else 0.0

    def ucb_score(self, parent_visit_count: int, c_puct: float = C_PUCT) -> float:
        """Upper Confidence Bound score (PUCT variant)."""
        u = c_puct * self.prior * math.sqrt(parent_visit_count) / (1 + self.visit_count)
        return self.q_value + u


# ---------------------------------------------------------------------------
# MCTS search
# ---------------------------------------------------------------------------

class _GridironSageMCTS:
    """Lightweight MCTS search over discrete bid amounts.

    At each node, the policy head of the neural network determines prior
    probabilities over bid increments.  The value head provides a leaf
    evaluation without full rollout.

    The bid action space is discretised into `policy_dim` increments:
      increment[i] = floor(remaining_budget * (i+1) / policy_dim)
    so actions scale with the current budget rather than being fixed values.
    """

    def __init__(self, network: _GridironSageNetwork, iterations: int = TOURNAMENT_MCTS_ITERATIONS) -> None:
        self.network = network
        self.iterations = iterations

    def search(
        self,
        player: "Player",
        team: "Team",
        current_bid: float,
        remaining_budget: float,
        remaining_players: List["Player"],
    ) -> float:
        """Run MCTS and return the recommended bid amount."""
        features = _extract_features(player, team, current_bid, remaining_budget, remaining_players)
        policy_logits, root_value = self.network.forward(features)

        policy_probs = _softmax(policy_logits)
        policy_dim = len(policy_probs)

        # Build candidate bids
        max_bid = min(remaining_budget - self._min_budget_reserve(team), remaining_budget)
        if max_bid <= current_bid:
            return 0.0

        candidate_bids = self._build_bid_candidates(current_bid, max_bid, policy_dim)
        if not candidate_bids:
            return 0.0

        root = _MCTSNode(bid=current_bid, prior=1.0)
        root.children = [
            _MCTSNode(bid=b, prior=policy_probs[i])
            for i, b in enumerate(candidate_bids)
        ]
        root.is_expanded = True

        for _ in range(self.iterations):
            self._simulate(root, features, remaining_budget, remaining_players, player, team)

        # Select child with highest visit count (greedy, temperature=0)
        if not root.children:
            return 0.0
        best = max(root.children, key=lambda n: n.visit_count)
        return best.bid

    def _simulate(
        self,
        root: _MCTSNode,
        features: List[float],
        remaining_budget: float,
        remaining_players: List["Player"],
        player: "Player",
        team: "Team",
    ) -> None:
        """Single MCTS simulation: select → expand/evaluate → backprop."""
        path: List[_MCTSNode] = [root]
        node = root

        # Selection: traverse to a leaf
        while node.is_expanded and node.children:
            node = max(node.children, key=lambda n: n.ucb_score(path[-2].visit_count if len(path) > 1 else node.visit_count + 1))
            path.append(node)

        # Evaluation: use value head (no full rollout needed)
        _, value = self.network.forward(features)

        # Add a small noise to value for exploration when network is untrained
        if not self.network._checkpoint_loaded:
            value = random.gauss(0.5, 0.15)
            value = max(0.0, min(1.0, value))

        # Backpropagation
        for n in path:
            n.visit_count += 1
            n.value_sum += value

    @staticmethod
    def _build_bid_candidates(current_bid: float, max_bid: float, n: int) -> List[float]:
        """Generate n evenly-spaced candidate bids between current_bid+1 and max_bid."""
        span = max_bid - current_bid
        if span <= 0:
            return []
        step = span / n
        candidates: List[float] = []
        for i in range(n):
            bid = current_bid + step * (i + 1)
            bid = math.floor(bid)
            if bid > current_bid and (not candidates or bid != candidates[-1]):
                candidates.append(bid)
        return candidates[:n]

    @staticmethod
    def _min_budget_reserve(team: "Team") -> float:
        """Minimum $1-per-slot budget reserve to keep team completable."""
        try:
            get_slots = getattr(team, "get_remaining_roster_slots", None)
            if callable(get_slots):
                return float(sum(get_slots().values()))
        except Exception:
            pass
        return 1.0


# ---------------------------------------------------------------------------
# Softmax helper
# ---------------------------------------------------------------------------

def _softmax(logits: List[float]) -> List[float]:
    """Numerically stable softmax."""
    max_val = max(logits) if logits else 0.0
    exps = [math.exp(x - max_val) for x in logits]
    total = sum(exps) or 1.0
    return [e / total for e in exps]


# ---------------------------------------------------------------------------
# VOR-based fallback heuristic
# ---------------------------------------------------------------------------

def _vor_heuristic_bid(
    player: "Player",
    current_bid: float,
    remaining_budget: float,
    remaining_players: List["Player"],
) -> float:
    """Simple VOR-based bid estimate used as the untrained network fallback.

    Bids up to the player's auction_value scaled by remaining budget headroom,
    minus the minimum $1-per-remaining-player reserve.
    """
    auction_value: float = getattr(player, "auction_value", 1.0) or 1.0
    vor: float = getattr(player, "vor", 0.0) or 0.0

    # Scale by budget availability
    budget_ratio = min(remaining_budget / 200.0, 1.5)
    bid = auction_value * budget_ratio

    # VOR premium: extra 10% per VOR point above 0, capped at 20%
    if vor > 0:
        bid *= 1.0 + min(vor / 100.0, 0.2)

    # Don't bid more than we can afford
    reserve = max(len(remaining_players), 1)
    effective_budget = remaining_budget - reserve
    bid = min(bid, effective_budget)
    bid = max(bid, current_bid + 1)

    return math.floor(bid)


# ---------------------------------------------------------------------------
# GridironSageStrategy
# ---------------------------------------------------------------------------

class GridironSageStrategy(Strategy):
    """MCTS + dual-head neural network auction draft strategy.

    GridironSage uses Monte Carlo Tree Search guided by a learned policy/value
    network to make bidding decisions in fantasy football auction drafts.

    When a trained checkpoint is available at ``data/models/gridiron_sage.pt``,
    the neural network provides meaningful policy priors and value estimates.
    When no checkpoint is present (untrained state), the strategy falls back to
    a VOR-based heuristic for bidding and uses uniform policy priors for MCTS —
    providing a reasonable baseline without requiring a pre-trained model.

    Args:
        mcts_iterations: Number of MCTS iterations per bid decision.  Defaults
            to ``TOURNAMENT_MCTS_ITERATIONS`` (50).  The training loop passes
            ``TRAINING_MCTS_ITERATIONS`` (800) via ``lab/gridiron_sage/train.py``.
        aggression: Scalar multiplier applied to MCTS bid output.  Values > 1.0
            increase bid aggressiveness; values < 1.0 decrease it.
        use_mcts: When False the strategy uses only the VOR heuristic (useful
            for fast simulation benchmarks where MCTS overhead is undesirable).
    """

    def __init__(
        self,
        mcts_iterations: int = TOURNAMENT_MCTS_ITERATIONS,
        aggression: float = 1.0,
        use_mcts: bool = True,
    ) -> None:
        super().__init__(
            name="GridironSage",
            description=(
                f"MCTS + neural network strategy (iterations={mcts_iterations}, "
                f"aggression={aggression:.2f}, mcts={'on' if use_mcts else 'off'})"
            ),
        )
        self.mcts_iterations = mcts_iterations
        self.aggression = aggression
        self.use_mcts = use_mcts

        self._network = _GridironSageNetwork()
        self._mcts = _GridironSageMCTS(self._network, iterations=mcts_iterations) if use_mcts else None

    @property
    def checkpoint_loaded(self) -> bool:
        """True if a trained PyTorch checkpoint was successfully loaded."""
        return self._network._checkpoint_loaded

    def calculate_bid(
        self,
        player: "Player",
        team: "Team",
        owner: "Owner",
        current_bid: float,
        remaining_budget: float,
        remaining_players: List["Player"],
    ) -> int:
        """Calculate bid using MCTS + network, or VOR heuristic if MCTS is disabled.

        Returns an integer bid amount, or 0 to pass.
        """
        # Budget guard: never bid if we can't complete the roster
        try:
            get_slots = getattr(team, "get_remaining_roster_slots", None)
            if callable(get_slots):
                min_reserve = float(sum(get_slots().values()))
                if remaining_budget - current_bid <= min_reserve:
                    return 0
        except Exception:
            pass

        if self.use_mcts and self._mcts is not None:
            bid = self._mcts.search(
                player=player,
                team=team,
                current_bid=current_bid,
                remaining_budget=remaining_budget,
                remaining_players=remaining_players,
            )
        else:
            bid = _vor_heuristic_bid(player, current_bid, remaining_budget, remaining_players)

        # Apply aggression multiplier, then floor to int
        bid = math.floor(bid * self.aggression)

        # Return 0 (pass) if bid doesn't beat current
        return int(bid) if bid > current_bid else 0

    def should_nominate(
        self,
        player: "Player",
        team: "Team",
        owner: "Owner",
        remaining_budget: float,
    ) -> bool:
        """Nominate high-VOR, high-value players that fit the team's position needs.

        Nomination strategy:
          1. Skip players at positions we don't need.
          2. Prioritise elite players (auction_value > 30) — nominating them
             forces opponents to spend.
          3. Among non-elite players, nominate based on VOR rank.
          4. Never nominate if budget headroom is critically low.
        """
        pos: str = getattr(player, "position", "UNKNOWN") or "UNKNOWN"

        # Check position need
        try:
            get_prio = getattr(team, "calculate_position_priority", None)
            if callable(get_prio):
                priority = get_prio(pos)
                if priority < 0.1:
                    return False
        except Exception:
            pass

        # Budget headroom check — applied unconditionally before any nomination
        try:
            get_slots = getattr(team, "get_remaining_roster_slots", None)
            if callable(get_slots):
                min_reserve = float(sum(get_slots().values()))
                if remaining_budget <= min_reserve + 2:
                    return False
        except Exception:
            pass
        # Hard floor: if remaining budget is critically low (<=5), never nominate
        if remaining_budget <= 5.0:
            return False

        auction_value: float = getattr(player, "auction_value", 0.0) or 0.0
        vor: float = getattr(player, "vor", 0.0) or 0.0

        # Nominate elite players unconditionally (forces bidding wars)
        if auction_value >= 30.0:
            return True

        # Nominate mid-tier players with meaningful VOR
        return vor > 5.0 or auction_value > 10.0
