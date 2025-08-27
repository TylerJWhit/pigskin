# Installation Guide

## Quick Install

1. **Download/Clone the project**
2. **Run setup script:**
   ```bash
   ./setup.sh
   ```
3. **Start using:**
   ```bash
   ./pigskin help
   ```

## Manual Installation

If you prefer manual setup:

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements-core.txt

# 3. Create config
cp config/config.json.example config/config.json

# 4. Make executable
chmod +x pigskin

# 5. Test
./pigskin help
```

## Development Setup

For development work:

```bash
# Install with dev dependencies
pip install -r requirements-dev.txt

# Run tests
make test

# Format code
make format
```

## Docker (Optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements-core.txt .
RUN pip install -r requirements-core.txt
COPY . .
CMD ["python", "cli/main.py", "help"]
```

## Troubleshooting

- **Permission denied**: Run `chmod +x setup.sh pigskin`
- **Python not found**: Install Python 3.8+
- **Import errors**: Activate virtual environment: `source venv/bin/activate`

## System Requirements

- Python 3.8 or higher
- 50MB disk space
- Internet connection (for data updates)
- Linux/macOS/Windows with bash
