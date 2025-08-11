import time
from typing import List, Dict, Optional

from bs4 import BeautifulSoup
from selenium import webdriver


def save_html(html: str, path: str) -> None:
    """Save HTML content to a file."""
    with open(path, "w", encoding="utf-8") as file:
        file.write(html)


def open_html(path: str) -> str:
    """Read HTML content from a file."""
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def get_pages() -> None:
    """Open sportsbook websites, get HTML, save to files."""
    print(
        "What sport do you want to bet on?\n"
        "1. NFL\n"
        "2. MLB\n"
        "3. NBA\n"
        "4. NCAA Football"
    )
    while True:
        try:
            league_choice = int(input("Type your choice here: "))
            if league_choice in {1, 2, 3, 4}:
                break
            print("Please enter a number between 1 and 4.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # todo: Add urls for BallyBet like others
    urls = {
        1: {
            "draftkings": "https://sportsbook.draftkings.com/leagues/football/nfl",
            "betmgm": "https://sports.az.betmgm.com/en/sports/football-11/betting/usa-9/nfl-35",
        },
        2: {
            "draftkings": "https://sportsbook.draftkings.com/leagues/baseball/mlb",
            "betmgm": "https://sports.az.betmgm.com/en/sports/baseball-23/betting/usa-9/mlb-75",
        },
        3: {
            "draftkings": "https://sportsbook.draftkings.com/leagues/basketball/nba",
            "betmgm": "https://sports.az.betmgm.com/en/sports/basketball-7/betting/usa-9/nba-6004",
        },
        4: {
            "draftkings": "https://sportsbook.draftkings.com/leagues/football/ncaaf",
            "betmgm": "https://sports.az.betmgm.com/en/sports/football-11/betting/usa-9/college-football-211",
        },
    }

    ballybet_url = "https://play.ballybet.com/sports#sports-hub/baseball/mlb"

    driver = webdriver.Chrome()

    try:
        # DraftKings
        driver.get(urls[league_choice]["draftkings"])
        time.sleep(6)
        save_html(driver.page_source, "./webpages/draftkings_page.txt")

        # BetMGM
        driver.get(urls[league_choice]["betmgm"])
        time.sleep(6)
        save_html(driver.page_source, "./webpages/betmgm_page.txt")

        # BallyBet
        driver.get(ballybet_url)
        time.sleep(6)
        save_html(driver.page_source, "./webpages/ballybet_page.txt")
    finally:
        driver.quit()


def get_draft_kings() -> List[Dict[str, Optional[object]]]:
    """Parse DraftKings HTML and extract betting lines."""
    data = []
    soup = BeautifulSoup(open_html("webpages/draftkings_page.txt"), "html.parser")
    parlay_cards = soup.select(".parlay-card-10-a")

    for card in parlay_cards:
        rows = card.select("tbody tr")
        for row in rows:
            entry = {"sportbook": "DraftKings"}

            columns = row.select(".sportsbook-table__column-row")
            name_col, spread_col, _, moneyline_col = columns

            team_name = name_col.select_one(".event-cell__name-text")
            if not team_name:
                continue
            team_name_text = team_name.text.strip().split()
            entry["team_name"] = team_name_text[-1]

            def clean_float(value):
                try:
                    return float(value.replace("+", "").replace("−", "-"))
                except (ValueError, AttributeError):
                    return None

            def clean_int(value):
                try:
                    return int(value.replace("+", "").replace("−", "-"))
                except (ValueError, AttributeError):
                    return None

            spread = spread_col.select_one(".sportsbook-outcome-cell__line")
            entry["spread"] = clean_float(spread.text.strip()) if spread else None

            spread_line = spread_col.select_one(".sportsbook-outcome-cell__element span")
            entry["spread_line"] = clean_int(spread_line.text.strip()) if spread_line else None

            moneyline = moneyline_col.select_one(".sportsbook-outcome-cell__element span")
            entry["moneyline"] = clean_int(moneyline.text.strip()) if moneyline else None

            data.append(entry)

    return data


def get_ballybets() -> List[Dict[str, Optional[object]]]:
    """Parse BallyBet HTML and extract betting lines."""
    data = []
    soup = BeautifulSoup(open_html("webpages/ballybet_page.txt"), "html.parser")
    events = soup.find_all("li", class_="KambiBC-sandwich-filter__event-list-item")

    for event in events:
        team_divs = event.find_all("div", class_="KambiBC-event-participants__name-participant-name")
        teams = [t.get_text(strip=True).replace("@ ", "") for t in team_divs]

        if len(teams) != 2:
            continue

        team_away = {"sportbook": "BallyBet", "team_name": teams[0].split()[-1]}
        team_home = {"sportbook": "BallyBet", "team_name": teams[1].split()[-1]}

        # Moneyline
        moneyline_section = event.find("div", class_="KambiBC-bet-offer--onecrosstwo")
        moneyline_buttons = moneyline_section.find_all("button") if moneyline_section else []

        def parse_odds(aria_label: str) -> Optional[int]:
            if " at " in aria_label:
                odds_str = aria_label.split(" at ")[-1].strip()
                try:
                    return int(odds_str.replace("+", "").replace("−", "-"))
                except ValueError:
                    return None
            return None

        if len(moneyline_buttons) == 2:
            for btn, team in zip(moneyline_buttons, (team_away, team_home)):
                team["moneyline"] = parse_odds(btn.get("aria-label", ""))
        else:
            team_away["moneyline"] = None
            team_home["moneyline"] = None

        # Spread (Run Line)
        spread_section = event.find("div", class_="KambiBC-bet-offer--handicap")
        spread_buttons = spread_section.find_all("button") if spread_section else []

        for team in (team_away, team_home):
            team["spread"] = None
            team["spread_line"] = None

        for btn in spread_buttons:
            label = btn.get("aria-label", "")
            if "Run Line" in label:
                parts = label.split(" - ")
                if len(parts) >= 3:
                    team_and_spread = parts[2]
                    if " at " in team_and_spread:
                        team_spread_part, odds_str = team_and_spread.rsplit(" at ", 1)
                        tokens = team_spread_part.split()
                        spread_val = tokens[-1]
                        team_name = " ".join(tokens[:-1])

                        spread_val_clean = float(spread_val.replace("+", "").replace("−", "-"))
                        spread_line_clean = int(odds_str.replace("+", "").replace("−", "-"))

                        if team_name == team_away["team_name"]:
                            team_away["spread"] = spread_val_clean
                            team_away["spread_line"] = spread_line_clean
                        elif team_name == team_home["team_name"]:
                            team_home["spread"] = spread_val_clean
                            team_home["spread_line"] = spread_line_clean

        data.append(team_away)
        data.append(team_home)

    return data


def get_betmgm() -> List[Dict[str, Optional[object]]]:
    """Parse BetMGM HTML and extract betting lines."""
    soup = BeautifulSoup(open_html("webpages/betmgm_page.txt"), "html.parser")
    grid = soup.select("ms-six-pack-event")

    data = []

    for row in grid:
        team_1 = {"sportbook": "BetMGM"}
        team_2 = {"sportbook": "BetMGM"}

        game = row.select_one(".participants-pair-game")
        game_teams = game.select(".participant-wrapper")

        team_1["team_name"] = game_teams[0].select_one(".participant").text.strip()
        team_2["team_name"] = game_teams[1].select_one(".participant").text.strip()

        bets = row.select_one(".grid-six-pack-wrapper").select("ms-option-group")

        spread_opts = bets[0].select("ms-option")
        over_under_opts = bets[1]  # unused but kept for clarity
        moneyline_opts = bets[2].select("ms-option")

        def clean_float(value: Optional[str]) -> Optional[float]:
            if value is None:
                return None
            try:
                return float(value.replace("+", "").replace("−", "-"))
            except ValueError:
                return None

        def clean_int(value: Optional[str]) -> Optional[int]:
            if value is None:
                return None
            try:
                return int(value.replace("+", "").replace("−", "-"))
            except ValueError:
                return None

        # Spread for team 1 and 2
        team_1_spread_text = spread_opts[0].select_one(".option-attribute").text.strip() if spread_opts[0].select_one(".option-attribute") else None
        team_1["spread"] = clean_float(team_1_spread_text)

        team_2_spread_text = spread_opts[1].select_one(".option-attribute").text.strip() if spread_opts[1].select_one(".option-attribute") else None
        team_2["spread"] = clean_float(team_2_spread_text)

        # Spread line for team 1 and 2
        team_1_spread_line_text = spread_opts[0].select_one("ms-font-resizer span").text.strip() if spread_opts[0].select_one("ms-font-resizer span") else None
        team_1["spread_line"] = clean_int(team_1_spread_line_text)

        team_2_spread_line_text = spread_opts[1].select_one("ms-font-resizer span").text.strip() if spread_opts[1].select_one("ms-font-resizer span") else None
        team_2["spread_line"] = clean_int(team_2_spread_line_text)

        # Moneyline for team 1 and 2
        team_1_moneyline_text = moneyline_opts[0].select_one("ms-font-resizer").text.strip() if moneyline_opts[0].select_one("ms-font-resizer") else None
        team_1["moneyline"] = clean_int(team_1_moneyline_text)

        team_2_moneyline_text = moneyline_opts[1].select_one("ms-font-resizer").text.strip() if moneyline_opts[1].select_one("ms-font-resizer") else None
        team_2["moneyline"] = clean_int(team_2_moneyline_text)

        data.extend([team_1, team_2])

    return data


def print_lines(sportbooks: List[List[Dict[str, Optional[object]]]]) -> None:
    """Print all betting lines."""
    for sportsbook in sportbooks:
        for team in sportsbook:
            print(team)
        print()


def print_lines_by_team(sportbooks: List[List[Dict[str, Optional[object]]]], team_name: str) -> None:
    """Print betting lines for a specific team."""
    for sportsbook in sportbooks:
        for game in sportsbook:
            if game["team_name"].lower() == team_name.lower():
                print(game)
                break
    print()


def print_best_line_moneyline_by_team(sportbooks: List[List[Dict[str, Optional[object]]]], team_name: str) -> None:
    """Print best moneyline betting line for a team."""
    best_bet = None
    best_line = float("-inf")

    for sportsbook in sportbooks:
        for game in sportsbook:
            if game["team_name"].lower() == team_name.lower():
                moneyline = game.get("moneyline")
                if isinstance(moneyline, int) and moneyline > best_line:
                    best_bet = game
                    best_line = moneyline

    if best_bet:
        print(best_bet)
    else:
        print(f"No moneyline bets found for team: {team_name}")
    print()


def main() -> None:
    print("\nWelcome to Garrett's Sportbetting Program!!\n")
    quit_program = False

    while not quit_program:
        get_pages()
        print()

        betmgm_lines = get_betmgm()
        ballybets_lines = get_ballybets()
        draftkings_lines = get_draft_kings()

        sportsbooks = [betmgm_lines, ballybets_lines, draftkings_lines]

        print_lines(sportsbooks)

        team_name = input("Enter the team's name: ").strip()
        print()

        print(
            "What betting line do you want to optimize?\n"
            "1. Moneyline\n"
            "2. Spread"
        )
        while True:
            try:
                bet_choice = int(input("Type your choice here: "))
                if bet_choice in {1, 2}:
                    break
                print("Please enter 1 or 2.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        print()

        if bet_choice == 1:
            print_best_line_moneyline_by_team(sportsbooks, team_name)
        else:
            # TODO: Implement best spread
            print("Best spread option not yet implemented.")
            break

        print()

        quit_input = input("Enter 'q' to quit or any other key to continue: ").strip().lower()
        if quit_input == "q":
            quit_program = True
        print()


if __name__ == "__main__":
    main()
