# Craps Simulator

A comprehensive craps simulator with GUI for testing and analyzing betting strategies.

## Features

### Visual Craps Table
- Interactive craps table with draggable chips ($1, $5, $25, $100, $500)
- All standard bet types with correct pay tables
- Configurable table rules (minimums, maximums, field payouts)

### Bankroll Tracking
- Track each roll's impact on bankroll
- Per-shooter statistics (points made, bets won/lost)
- Visualize equity over time

### Strategy Testing
- **Continuous Mode**: Run strategies for a set number of rolls
- **Session Mode**: Simulate realistic casino sessions (N shooters per session)
- Compare multiple strategies on identical dice sequences
- Action-weighted house edge calculation

### Session Analysis
- Win rate across sessions
- Percentile breakdown (what unlucky vs lucky players experience)
- Distribution histograms and percentile comparison charts

### Built-in Strategies
- Pass Line + Odds (lowest house edge)
- Don't Pass + Lay Odds
- Place 6 & 8
- Iron Cross
- Regress and Press

## Installation

### Pre-built Binaries
Download the latest release for your platform from the [Releases](../../releases) page:
- **Windows**: `craps-sim-windows-amd64.exe`
- **Linux**: `craps-sim-linux-amd64`
- **macOS**: `craps-sim-macos-arm64.zip`

### From Source
```bash
# Clone the repository
git clone https://github.com/yourusername/craps-sim.git
cd craps-sim

# Create virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## Usage

### Main Table
- **Left-click** on chip tray to select denomination
- **Left-click** on table to place chips
- **Right-click** on betting spot to remove chips
- Click **Roll Dice** to roll

### Strategy Tester
1. Click **Strategy Tester** button
2. Select strategies to compare
3. Choose simulation mode:
   - **Continuous**: Set number of rolls
   - **Session**: Set shooters per session and number of sessions
4. Click **Run Test**
5. View results, statistics, and comparison graphs

## Requirements
- Python 3.10+
- matplotlib
- tkinter (included with Python on most systems)

## License
MIT License - see [LICENSE](LICENSE) for details.
