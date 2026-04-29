"""Test script to demonstrate FantasyPros data loading."""

from data import FantasyProsLoader, load_fantasypros_players, get_position_rankings
from classes import DraftSetup


def test_fantasypros_loading():
    """Test loading FantasyPros data."""
    print("=== FantasyPros Data Loading Test ===\n")
    
    # Test basic data loading
    print("1. Testing data summary:")
    loader = FantasyProsLoader()
    
    try:
        summary = loader.get_data_summary()
        print(f"   Data summary: {summary}")
        print(f"   Total players: {summary.get('total', 0)}")
    except Exception as e:
        print(f"   Error getting summary: {e}")
        return
    
    print()
    
    # Test loading players for each position
    print("2. Testing position data loading:")
    for position in ['QB', 'RB', 'WR', 'TE', 'K', 'DST']:
        try:
            players = loader.load_position_data(position)
            print(f"   {position}: {len(players)} players loaded")
            
            if players:
                top_player = max(players, key=lambda p: p['projected_points'])
                print(f"      Top player: {top_player['name']} ({top_player['projected_points']} pts)")
        except Exception as e:
            print(f"   {position}: Error loading - {e}")
    
    print()
    
    # Test convenience function
    print("3. Testing convenience function:")
    try:
        all_players = load_fantasypros_players(min_projected_points=50.0)
        print(f"   Loaded {len(all_players)} players with 50+ projected points")
        
        if all_players:
            # Show top 5 by auction value
            top_players = sorted(all_players, key=lambda p: p.auction_value, reverse=True)[:5]
            print("   Top 5 players by auction value:")
            for i, player in enumerate(top_players, 1):
                print(f"      {i}. {player.name} ({player.position}) - ${player.auction_value:.2f} ({player.projected_points} pts)")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test position rankings
    print("4. Testing QB rankings:")
    try:
        qb_rankings = get_position_rankings('QB', top_n=10)
        print(f"   Top 10 QBs:")
        for i, qb in enumerate(qb_rankings, 1):
            print(f"      {i}. {qb['name']} ({qb['team']}) - {qb['projected_points']} pts")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test draft creation with FantasyPros data
    print("5. Testing draft creation with FantasyPros data:")
    try:
        draft = DraftSetup.create_mock_draft(
            num_teams=6,
            include_humans=1,
            use_fantasypros_data=True,
            use_sleeper_data=False
        )
        
        print(f"   Draft created: {draft.name}")
        print(f"   Teams: {len(draft.teams)}")
        print(f"   Players available: {len(draft.available_players)}")
        
        if draft.available_players:
            # Show some player examples
            qbs = [p for p in draft.available_players if p.position == 'QB'][:3]
            rbs = [p for p in draft.available_players if p.position == 'RB'][:3]
            
            print("   Sample QBs:")
            for qb in qbs:
                print(f"      {qb.name} - ${qb.auction_value:.2f} ({qb.projected_points} pts)")
                
            print("   Sample RBs:")
            for rb in rbs:
                print(f"      {rb.name} - ${rb.auction_value:.2f} ({rb.projected_points} pts)")
                
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test player search
    print("6. Testing player search:")
    try:
        josh_allen = loader.get_player_by_name("Josh Allen", "QB")
        if josh_allen:
            print(f"   Found Josh Allen: {josh_allen['projected_points']} projected points")
        else:
            print("   Josh Allen not found")
            
        # Try partial name search in all positions
        print("   Searching for players with 'Jackson' in name:")
        found_players = []
        for position in ['QB', 'RB', 'WR', 'TE']:
            try:
                players = loader.load_position_data(position)
                jackson_players = [p for p in players if 'jackson' in p['name'].lower()]
                found_players.extend(jackson_players)
            except Exception:
                continue
                
        for player in found_players[:5]:  # Show first 5
            print(f"      {player['name']} ({player['position']}, {player['team']}) - {player['projected_points']} pts")
            
    except Exception as e:
        print(f"   Error: {e}")


if __name__ == "__main__":
    test_fantasypros_loading()
