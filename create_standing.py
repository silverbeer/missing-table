import csv
from collections import defaultdict
from rich.console import Console
from rich.table import Table

def calculate_standings(csv_file):
    standings = defaultdict(lambda: {
        'wins': 0, 'losses': 0, 'ties': 0,
        'goals_for': 0, 'goals_against': 0
    })
    
    with open(csv_file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            home_team = row['Home Team']
            away_team = row['Away Team']
            home_score = int(row['Home Score'])
            away_score = int(row['Away Score'])
            
            # Update goals
            standings[home_team]['goals_for'] += home_score
            standings[home_team]['goals_against'] += away_score
            standings[away_team]['goals_for'] += away_score
            standings[away_team]['goals_against'] += home_score
            
            # Update wins, losses, and ties
            if home_score > away_score:
                standings[home_team]['wins'] += 1
                standings[away_team]['losses'] += 1
            elif away_score > home_score:
                standings[away_team]['wins'] += 1
                standings[home_team]['losses'] += 1
            else:
                standings[home_team]['ties'] += 1
                standings[away_team]['ties'] += 1

    return standings

def display_standings(standings):
    console = Console()
    table = Table(title="MLS NEXT U13 Northeast Standings", show_header=True, header_style="bold cyan")
    
    # Reordered columns
    table.add_column("Team", style="white", no_wrap=True)
    table.add_column("GP", justify="center", style="blue")
    table.add_column("W", justify="center", style="green")
    table.add_column("T", justify="center", style="yellow")
    table.add_column("L", justify="center", style="red")
    table.add_column("GF", justify="center")
    table.add_column("GA", justify="center")
    table.add_column("GD", justify="center", style="yellow")
    table.add_column("PTS", justify="center", style="bold magenta")
    
    # Calculate additional stats and sort
    standings_with_extras = []
    for team, stats in standings.items():
        games_played = stats['wins'] + stats['losses'] + stats['ties']
        points = (stats['wins'] * 3) + stats['ties']
        goal_diff = stats['goals_for'] - stats['goals_against']
        
        standings_with_extras.append({
            'team': team,
            'stats': stats,
            'games_played': games_played,
            'points': points,
            'goal_diff': goal_diff
        })
    
    # Sort by points, then goal differential, then goals for
    sorted_teams = sorted(
        standings_with_extras,
        key=lambda x: (
            x['points'],
            x['goal_diff'],
            x['stats']['goals_for']
        ),
        reverse=True
    )
    
    # Add rows
    for team_data in sorted_teams:
        stats = team_data['stats']
        gd = team_data['goal_diff']
        gd_str = f"+{gd}" if gd > 0 else str(gd)
        
        table.add_row(
            team_data['team'],
            str(team_data['games_played']),
            str(stats['wins']),
            str(stats['ties']),
            str(stats['losses']),
            str(stats['goals_for']),
            str(stats['goals_against']),
            gd_str,
            str(team_data['points'])
        )
    
    console.print(table)

def main():
    csv_file = 'mlsnext-u13-fall.csv'
    try:
        standings = calculate_standings(csv_file)
        display_standings(standings)
    except FileNotFoundError:
        print(f"Error: Could not find file '{csv_file}'")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()