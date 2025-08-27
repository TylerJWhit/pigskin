#!/usr/bin/env python3

from classes.team import Team
from classes.player import Player

# Test roster configuration
roster_config = {
    "QB": 1,
    "RB": 2,
    "WR": 2, 
    "TE": 1,
    "FLEX": 2,
    "K": 1,
    "DST": 1,
    "BN": 5
}

team = Team("test", "owner1", "Test Team", roster_config=roster_config)

print(f"Roster config: {team.roster_config}")
print(f"Position limits: {team.position_limits}")
print(f"Total roster spots: {sum(roster_config.values())}")

# Create test players
players = [
    Player("1", "Josh Allen", "QB", "BUF"),
    Player("2", "Bijan Robinson", "RB", "ATL"),
    Player("3", "Saquon Barkley", "RB", "PHI"),
    Player("4", "Ja'Marr Chase", "WR", "CIN"),
    Player("5", "CeeDee Lamb", "WR", "DAL"),
    Player("6", "Brock Bowers", "TE", "LV"),
    Player("7", "Brandon Aubrey", "K", "DAL"),
    Player("8", "Buffalo Bills", "DST", "BUF"),
    # FLEX and BN players
    Player("9", "De'Von Achane", "RB", "MIA"),  # Should go to FLEX
    Player("10", "Amon-Ra St. Brown", "WR", "DET"),  # Should go to FLEX
    Player("11", "Travis Kelce", "TE", "KC"),  # Should go to BN
    Player("12", "Cooper Kupp", "WR", "LAR"),  # Should go to BN
    Player("13", "Joe Burrow", "QB", "CIN"),  # Should go to BN
    Player("14", "Kenneth Walker", "RB", "SEA"),  # Should go to BN
    Player("15", "Mike Evans", "WR", "TB"),  # Should go to BN
]

# Test adding players
for i, player in enumerate(players):
    success = team.add_player(player, 1)
    print(f"Player {i+1} ({player.name} - {player.position}): {'✓' if success else '✗'}")
    print(f"  Current roster size: {len(team.roster)}")
    if not success:
        print(f"  Failed to add - roster may be full or position limits reached")

print(f"\nFinal roster size: {len(team.roster)}")
print(f"Expected: {sum(roster_config.values())}")
