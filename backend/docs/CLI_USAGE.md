# League CLI Tool

A beautiful command-line interface for managing your sports league, built with Typer and Rich.

## Installation

The CLI is already configured in `pyproject.toml`. After running `uv sync`, you can use it with:

```bash
# Direct script execution
uv run python cli.py [COMMAND] [OPTIONS]

# Or use the nice alias (recommended)
uv run mt-cli [COMMAND] [OPTIONS]
```

## Commands

### Add a Game

**Interactive mode** (recommended for ease of use):
```bash
uv run mt-cli add-game
```

This will:
- Show all available teams in a nice table
- Prompt for game date (defaults to today)
- Let you select home and away teams from a dropdown
- Ask for scores
- Show a summary and confirm before adding

**Command-line mode** (faster for scripting):
```bash
uv run mt-cli add-game \
  --date "2025-07-10" \
  --home "Bayside FC" \
  --away "Valeo Futbol Club" \
  --home-score 3 \
  --away-score 1
```

### List Teams

```bash
uv run mt-cli list-teams
```

Shows all teams in a formatted table.

### Recent Games

```bash
uv run mt-cli recent-games --limit 10
```

Shows the most recent games (default: 10).

### League Table

```bash
uv run mt-cli table
```

Shows the current league standings with:
- Position, Team, Games Played
- Wins, Draws, Losses
- Goals For, Goals Against, Goal Difference
- Points

## Features

- 🎨 **Beautiful output** with Rich formatting
- ✅ **Input validation** (team names, date format)
- 🔍 **Team selection** from dropdown menus
- 📊 **Real-time data** from your Supabase backend
- ⚡ **Fast commands** with optional parameters
- 🛡️ **Error handling** with helpful messages

## Requirements

- Backend API running on `http://localhost:8000`
- Supabase database with teams and games data

## Examples

```bash
# Quick game entry
uv run mt-cli add-game

# Show recent results
uv run mt-cli recent-games --limit 5

# Check league standings
uv run mt-cli table

# List all teams
uv run mt-cli list-teams
```

The CLI automatically validates team names against your database and provides helpful error messages for any issues.