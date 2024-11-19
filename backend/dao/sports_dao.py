import sqlite3
from sqlite3 import Error

class DbConnectionHolder(object):
    """ Enforce/manage the connection to the DB across these queries. """

    def __init__(self, db_file):

        """ Connect upon instantiation, RAII-style. """
        self.db_conn = None
        self.db_file = str(db_file)
        self.get_db_connection()

    def __del__(self):
        """ Leveraging the dtor to close the DB connection, RAII-style. """
        if self.db_conn is not None:
            self.db_conn.close()

    def get_db_connection(self):
        """ The first time you call this, you connect - on subsequent calls, you get a reference
        to the existing connection. """
        if self.db_conn is None:
            try:
                self.db_conn = sqlite3.connect(self.db_file)
                print(f"Connection to database '{self.db_file}' established.")
            except Exception as e:
                print("An error occurred while trying to connect to the database:")
                print(e)
        return self.db_conn

class SportsDAO(object):
    def __init__(self, db_conn_holder):
        assert type(db_conn_holder) is DbConnectionHolder
        self.db_conn_holder = db_conn_holder

    # Team Methods
    def get_all_teams(self):
        """Query all rows in the teams table."""
        cursor = self.db_conn_holder.get_db_connection().cursor()
        teams = []
        try:
            cursor.execute("SELECT * FROM teams ORDER BY name ASC")
            rows = cursor.fetchall()

            for row in rows:
                teams.append({
                    'id': row[0],
                    'name': row[1],
                    'city': row[2]
                })
        except Error as e:
            print(f"Error querying teams: {e}")
        return teams

    def add_team(self, name, city):
        """Add a new team to the teams table."""
        cursor = self.db_conn_holder.get_db_connection().cursor()
        try:
            cursor.execute("INSERT INTO teams (name, city) VALUES (?, ?)", (name, city))
            print(f"Team '{name}' added successfully.")
        except Error as e:
            print(f"Error adding team: {e}")

    # Game Methods
    def get_all_games(self):
        """Query all rows in the games table."""
        print("Getting all games")
        cursor = self.db_conn_holder.get_db_connection().cursor()
        games = []
        try:
            cursor.execute("SELECT * FROM games")
            rows = cursor.fetchall()

            for row in rows:
                print(row)
                games.append({
                    'game_date': row[0],
                    'home_team': row[1],
                    'away_team': row[2],
                    'home_score': row[3],
                    'away_score': row[4]
                })
        except Error as e:
            print(f"Error querying games: {e}")
        return games

    def get_games_by_team(self, team_name):
        """Query games for a specific team."""
        print(f"Getting games for team: {team_name}")
        cursor = self.db_conn_holder.get_db_connection().cursor()
        games = []
        try:
            cursor.execute("SELECT game_date, home_team, away_team, home_score, away_score FROM games WHERE home_team = ? OR away_team = ? ORDER BY game_date ASC", (team_name, team_name))
            rows = cursor.fetchall()
            print(rows)

            for row in rows:

                games.append({
                    'game_date': row[0],
                    'home_team': row[1],
                    'away_team': row[2],
                    'home_score': row[3],
                    'away_score': row[4]
                })
        except Error as e:
            print(f"Error querying games for team '{team_name}': {e}")
        return games

    def add_game(self, game_date, home_team, away_team, home_score, away_score):
        """Add a new game to the database."""
        cursor = self.db_conn_holder.get_db_connection().cursor()
        try:
            cursor.execute(
                "INSERT INTO games (game_date, home_team, away_team, home_score, away_score) VALUES (?, ?, ?, ?, ?)",
                (game_date, home_team, away_team, home_score, away_score)
            )
            cursor.connection.commit()  # Commit the transaction
        except Error as e:
            print(f"Error adding game: {e}")
            cursor.connection.rollback()  # Rollback in case of error


if __name__ == '__main__':
    # Test the DAO methods
    db_conn_holder_obj = DbConnectionHolder(db_file='../mlsnext_u13_fall.db')
    dao = SportsDAO(db_conn_holder_obj)
    print("All Teams:")
    print(dao.get_all_teams())
    print("All Games:")
    print(dao.get_all_games())
    print("Games for 'Test Team':")
    print(dao.get_games_by_team('Test Team'))
    print("Adding team 'Test Team'...")
    dao.add_team('Test Team', 'Test City')
    print("Adding game '2023-10-01', 'Test Team', 'Another Team', 2, 1...")
    dao.add_game('2023-10-01', 'Test Team', 'Another Team', 2, 1)
    print("All Teams:")
    print(dao.get_all_teams())
    print("All Games:")
    print(dao.get_all_games())
    print("Games for 'Test Team':")
    print(dao.get_games_by_team('Test Team'))