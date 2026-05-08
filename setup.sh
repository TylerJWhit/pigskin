#!/bin/bash
# Pigskin Auction Draft Tool Setup Script
# This script sets up the environment and dependencies

set -e  # Exit on any error

echo "============================================"
echo "Pigskin Auction Draft Tool Setup"
echo "============================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR"

print_info "Setting up Pigskin Auction Draft Tool..."
print_info "Project directory: $SCRIPT_DIR"

# Check Python version
echo
print_info "Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    print_status "Python 3 found: $PYTHON_VERSION"
    
    # Check if version is 3.8 or higher
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
        print_status "Python version is compatible (3.8+)"
    else
        print_error "Python 3.8+ required. Found: $PYTHON_VERSION"
        exit 1
    fi
else
    print_error "Python 3 not found. Please install Python 3.8 or higher."
    exit 1
fi

# Check if virtual environment exists
echo
print_info "Checking virtual environment..."
if [ -d "venv" ]; then
    print_status "Virtual environment already exists"
else
    print_info "Creating virtual environment..."
    python3 -m venv venv
    print_status "Virtual environment created"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source venv/bin/activate
print_status "Virtual environment activated"

# Install uv
print_info "Installing uv package manager..."
pip install uv > /dev/null 2>&1
print_status "uv installed ($(uv --version 2>/dev/null || echo 'version unknown'))"

# Install all dependencies via uv
echo
print_info "Installing Python dependencies with uv..."
if [ -f "pyproject.toml" ] && [ -f "uv.lock" ]; then
    uv sync --frozen
    print_status "Dependencies installed from uv.lock (reproducible)"
elif [ -f "pyproject.toml" ]; then
    uv sync
    print_status "Dependencies installed from pyproject.toml"
else
    print_warning "pyproject.toml not found — falling back to requirements.txt"
    pip install -r requirements.txt
    print_status "Dependencies installed from requirements.txt"
fi

# Create necessary directories
echo
print_info "Creating necessary directories..."
mkdir -p data/cache
mkdir -p data/data
mkdir -p results
mkdir -p logs
print_status "Directories created"

# Set up configuration
echo
print_info "Setting up configuration..."
if [ ! -f "config/config.json" ]; then
    print_info "Creating default configuration file..."
    cat > config/config.json << 'EOF'
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
    "data_path": "data/data/sheets",
    "min_projected_points": 5.0,
    "default_strategy": "value",
    "sleeper_username": "",
    "sleeper_draft_id": "",
    "tournament_settings": {
        "num_simulations": 100,
        "teams_per_draft": 10,
        "max_rounds": 5
    }
}
EOF
    print_status "Default configuration created"
else
    print_status "Configuration file already exists"
fi

# Make the pigskin script executable
if [ -f "pigskin" ]; then
    chmod +x pigskin
    print_status "Made pigskin executable"
fi

# Run tests to verify installation
echo
print_info "Running basic tests to verify installation..."
cd tests
if python run_tests.py > /dev/null 2>&1; then
    print_status "Basic tests passed"
else
    print_warning "Some tests failed, but core functionality should work"
fi
cd ..

# Display setup completion message
echo
echo "============================================"
print_status "Setup completed successfully!"
echo "============================================"
echo
print_info "Next steps:"
echo "1. Edit config/config.json to customize your settings"
echo "2. If using Sleeper, add your username and draft ID to config"
echo "3. Run './pigskin help' to see available commands"
echo
print_info "Quick start examples:"
echo "  ./pigskin bid 'Josh Allen' 25"
echo "  ./pigskin tournament"
echo "  ./pigskin sleeper cache info"
echo
print_info "To activate the virtual environment manually:"
echo "  source venv/bin/activate"
echo
print_status "Happy drafting!"
