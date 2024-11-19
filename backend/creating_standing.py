import csv

def calculate_standings(games):
    standings = {}
    
    # Calculate points for each team
    for game in games:
        home_team = game['homeTeam']
        away_team = game['awayTeam']
        home_score = int(game['homeScore'])
        away_score = int(game['awayScore'])

        # Initialize teams in standings if not already present
        if home_team not in standings:
            standings[home_team] = {'points': 0, 'games': 0}
        if away_team not in standings:
            standings[away_team] = {'points': 0, 'games': 0}

        # Update games played
        standings[home_team]['games'] += 1
        standings[away_team]['games'] += 1

        # Determine points based on the score
        if home_score > away_score:
            standings[home_team]['points'] += 3  # Home team wins
        elif away_score > home_score:
            standings[away_team]['points'] += 3  # Away team wins
        else:
            standings[home_team]['points'] += 1  # Draw
            standings[away_team]['points'] += 1

    # Create a sorted list of standings
    sorted_standings = sorted(standings.items(), key=lambda x: x[1]['points'], reverse=True)

    # Prepare the final standings with rankings
    final_standings = []
    for rank, (team, data) in enumerate(sorted_standings, start=1):
        final_standings.append({
            'rank': rank,
            'team': team,
            'points': data['points'],
            'games': data['games']
        })

    return final_standings

def write_standings_to_csv(standings, filename='standings.csv'):
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['Rank', 'Team', 'Points', 'Games']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for standing in standings:
            writer.writerow({
                'Rank': standing['rank'],
                'Team': standing['team'],
                'Points': standing['points'],
                'Games': standing['games']
            })

# Example usage
if __name__ == "__main__":
    # Sample game data
    games = [
        {'homeTeam': 'Team A', 'awayTeam': 'Team B', 'homeScore': '2', 'awayScore': '1'},
        {'homeTeam': 'Team C', 'awayTeam': 'Team A', 'homeScore': '0', 'awayScore': '3'},
        {'homeTeam': 'Team B', 'awayTeam': 'Team C', 'homeScore': '1', 'awayScore': '1'},
    ]

    standings = calculate_standings(games)
    write_standings_to_csv(standings) 