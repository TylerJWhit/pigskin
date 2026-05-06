# Pigskin Draft Assistant

An intuitive fantasy football draft assistant that helps you make smarter draft decisions — whether you're in an auction, a snake/round-robin, a dynasty startup, or a rookie draft. Includes advanced strategy analysis and backtesting tools so you can find what works before draft day.

## Goals

1. **Easy-to-use draft assistant** — Provide clear, actionable recommendations that any drafter can act on without needing to understand the underlying math.
2. **All draft formats** — Support auction drafts and normal snake/round-robin drafts equally well.
3. **All league types** — Help with standard redrafts, dynasty startup drafts, and rookie drafts.
4. **Strategy lab** — Side feature for testing and backtesting strategies to identify what actually works.

## Features

- **Multi-Format Draft Support**: Auction, snake/round-robin, dynasty startup, and rookie drafts
- **Live Draft Recommendations**: Position-aware pick and bid suggestions during any live draft
- **16 Bidding Strategies**: From conservative value-based to aggressive elite-targeting approaches
- **Strategy Backtesting**: Test strategies against historical data and simulated drafts to validate performance
- **Real-time Data Integration**: FantasyPros rankings and Sleeper API integration
- **Tournament Simulation**: Pit strategies against each other in elimination tournaments
- **Mock Drafts**: Practice with different strategies and team sizes
- **Sleeper Integration**: Direct integration with Sleeper fantasy leagues and drafts

## Quick Start

### 1. Setup
```bash
# Clone or download the project
cd pigskin

# Run the setup script (recommended)
./setup.sh

# Or manually create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration
Edit `config/config.json` to customize:
- Budget and roster settings
- Data sources (FantasyPros/Sleeper)
- Default strategies
- Sleeper username and draft ID

### 3. Basic Usage
```bash
# Get help
./pigskin help

# Get bid recommendation
./pigskin bid "Josh Allen" 25

# Run mock draft
./pigskin mock value 10

# Run strategy tournament
./pigskin tournament

# Sleeper integration
./pigskin sleeper cache info
./pigskin sleeper status
```

## Available Strategies

1. **value** - Value-based bidding on undervalued players
2. **aggressive** - Targets elite players aggressively
3. **conservative** - Budget-conscious, value-focused
4. **sigmoid** - Mathematical curve-based bidding
5. **improved_value** - Enhanced value calculations
6. **adaptive** - Adapts to draft conditions
7. **vor** - Value Over Replacement calculations
8. **random** - Random bidding for testing
9. **balanced** - Balanced approach to all positions
10. **basic** - Simple bidding logic
11. **elite_hybrid** - Targets elite players with value considerations
12. **value_random** - Combines value with randomization
13. **value_smart** - Smart value-based approach
14. **hybrid_improved_value** - Enhanced hybrid strategy
15. **league** - League-specific adjustments
16. **refined_value_random** - Refined randomized value approach

## Commands

### Bid Recommendations
```bash
# Single player bid
./pigskin bid "Christian McCaffrey" 50

# Multiple players
./pigskin bid "Josh Allen" 45 "Travis Kelce" 40
```

### Mock Drafts
```bash
# Use specific strategy
./pigskin mock aggressive 12

# Default settings
./pigskin mock
```

### Tournament Simulation
```bash
# Full tournament
./pigskin tournament

# Custom rounds and team size
./pigskin tournament 3 8
```

### Sleeper Integration
```bash
# Cache management
./pigskin sleeper cache info
./pigskin sleeper cache refresh

# Draft information
./pigskin sleeper status
./pigskin sleeper draft

# League information
./pigskin sleeper leagues
```

## Configuration

The `config/config.json` file controls all settings:

```json
{
    "budget": 200,
    "roster_positions": {
        "QB": 1,
        "RB": 2,
        "WR": 3,
        "TE": 1,
        "K": 1,
        "DST": 1,
        "BENCH": 6
    },
    "data_source": "fantasypros",
    "default_strategy": "value",
    "sleeper_username": "your_username",
    "sleeper_draft_id": "your_draft_id"
}
```

## Development

### Running Tests
```bash
# All tests
cd tests && python run_tests.py

# Comprehensive project test
cd tests && python test_project.py
```

### Project Structure
```
pigskin/
├── api/                 # API integrations (Sleeper)
├── classes/             # Core classes (Player, Team, Owner, etc.)
├── cli/                 # Command-line interface
├── config/              # Configuration files
├── data/                # Player data and cache
├── services/            # Business logic services
├── strategies/          # Bidding strategies
├── tests/               # Test suites
├── utils/               # Utility functions
├── pigskin              # Main executable
├── setup.py             # Python package setup
├── setup.sh             # Environment setup script
└── requirements.txt     # Python dependencies
```

## Architecture Decisions

Key architectural decisions are documented as ADRs in [`docs/adr/`](docs/adr/):

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](docs/adr/ADR-001-repo-structure.md) | Mono-Repo Package Structure (core / app / lab) | Accepted |
| [ADR-002](docs/adr/ADR-002-api-design.md) | FastAPI REST + WebSocket API Design | Revised and Accepted |
| [ADR-003](docs/adr/ADR-003-strategy-promotion-pipeline.md) | Strategy Promotion Pipeline | Revised and Accepted |
| [ADR-004](docs/adr/ADR-004-lab-data-store.md) | Lab Data Store | Revised and Accepted |

## Requirements

- Python 3.8+
- Internet connection (for data updates)
- Optional: Sleeper account for league integration

## Installation Methods

### Method 1: Setup Script (Recommended)
```bash
./setup.sh
```

### Method 2: Manual Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Method 3: Python Package
```bash
pip install -e .
```

## Data Sources

- **FantasyPros**: Player rankings and projections
- **Sleeper API**: Live draft data and league information
- **Local Cache**: Cached player data for offline use

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and add tests
4. Run the test suite
5. Submit a pull request

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure virtual environment is activated
2. **Data Loading**: Check internet connection and data sources
3. **Sleeper Integration**: Verify username and draft ID in config
4. **Performance**: Use player data cache for faster loading

### Getting Help

1. Run `./pigskin help` for command documentation
2. Check the test suite for examples: `cd tests && python run_tests.py`
3. Review configuration in `config/config.json`

## Examples

### Basic Workflow
```bash
# 1. Setup
./setup.sh

# 2. Configure Sleeper (optional)
# Edit config/config.json with your Sleeper username

# 3. Update player data
./pigskin sleeper cache refresh

# 4. Get bid recommendations during draft
./pigskin bid "Player Name" 25

# 5. Test strategies
./pigskin tournament
```

### Advanced Usage
```bash
# Compare multiple strategies
./pigskin tournament 5 12

# Test specific strategy
./pigskin mock vor 10

# Multiple bid analysis
./pigskin bid "Josh Allen" 45 "Christian McCaffrey" 60
```

---

**Happy Drafting!** 🏈
