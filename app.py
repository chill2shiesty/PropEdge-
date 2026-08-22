import re
import requests
import pandas as pd
import streamlit as st
from datetime import datetime


# ============================================================
# PROPEdge
# NFL + MLB PLAYER PROP MARKET SCANNER
# ============================================================

st.set_page_config(
    page_title="PropEdge",
    page_icon="📊",
    layout="wide",
)

st.title("📊 PropEdge")
st.subheader("Player Prop Market Scanner")


# ============================================================
# SPORT CONFIGURATION
# ============================================================

SPORT_CONFIG = {

    "NFL": {
        "sport_key": "americanfootball_nfl",

        "markets": [
            "player_pass_yds",
            "player_pass_tds",
            "player_pass_completions",
            "player_rush_yds",
            "player_rec_yds",
            "player_receptions",
            "player_anytime_td",
            "player_interceptions",
        ],

        "description": "NFL Player Props",
    },

    "MLB": {
        "sport_key": "baseball_mlb",

        "markets": [
            "player_total_bases",
            "player_hits",
            "player_home_runs",
            "player_rbis",
            "player_runs",
            "player_singles",
            "player_doubles",
            "player_triples",
            "player_walks",
            "player_strikeouts",
            "player_pitcher_outs",
            "player_hits_allowed",
            "player_earned_runs",
            "player_hits_runs_rbis",
        ],

        "description": "MLB Player Props",
    },
}


# ============================================================
# BOOK CONFIGURATION
# ============================================================

COMPARISON_BOOKS = {
    "draftkings",
    "fanduel",
    "prizepicks",
    "betmgm",
}

DISPLAY_NAMES = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "prizepicks": "PrizePicks",
    "prizepicks_mobile": "PrizePicks",
    "betmgm": "BetMGM",
    "underdog": "Underdog",
    "underdogfantasy": "Underdog",
}


# ============================================================
# API SETTINGS
# ============================================================

MAX_AGE_SECONDS = 3600


# ============================================================
# RANKING SETTINGS
# ============================================================

# These weights control the Final Score.
#
# No-Vig Probability is the most important factor.
# Line Edge is the second factor.
# Book Confirmation rewards edges that appear across
# multiple sportsbooks.
#
# The MAIN CHART is NOT ranked by this score.
# The main chart is always ranked by Average No-Vig Probability.

NO_VIG_WEIGHT = 0.70
LINE_EDGE_WEIGHT = 0.20
BOOK_CONFIRMATION_WEIGHT = 0.10


# ============================================================
# SPORT SELECTOR
# ============================================================

selected_sport = st.selectbox(
    "Sport",
    list(SPORT_CONFIG.keys()),
)

SPORT_KEY = SPORT_CONFIG[
    selected_sport
]["sport_key"]

REQUESTED_MARKETS = SPORT_CONFIG[
    selected_sport
]["markets"]

st.caption(
    SPORT_CONFIG[selected_sport]["description"]
)


# ============================================================
# SESSION STATE
# ============================================================

if "scan_results" not in st.session_state:
    st.session_state.scan_results = None

if "raw_props" not in st.session_state:
    st.session_state.raw_props = None

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None

if "scan_error" not in st.session_state:
    st.session_state.scan_error = None

if "last_sport" not in st.session_state:
    st.session_state.last_sport = None


# ============================================================
# API HELPERS
# ============================================================

def get_api_key():

    if "PARLAY_API_KEY" not in st.secrets:

        raise ValueError(
            "PARLAY_API_KEY is missing from Streamlit Secrets."
        )

    return st.secrets[
        "PARLAY_API_KEY"
    ]


def get_headers():

    return {
        "X-API-Key": get_api_key(),
        "Accept": "application/json",
    }


def get_props():

    """
    Get all available player props for the selected sport.

    We intentionally do NOT send a bookmakers filter.

    ParlayAPI's /props endpoint returns all available
    books for the sport in one call.
    """

    url = (
        f"https://parlay-api.com/v1/sports/"
        f"{SPORT_KEY}/props"
    )

    params = {
        "markets": ",".join(
            REQUESTED_MARKETS
        ),
        "limit": 10000,
        "maxAgeSec": MAX_AGE_SECONDS,
        "dfsOdds": "midpoint",
    }

    response = requests.get(
        url,
        params=params,
        headers=get_headers(),
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# API RESPONSE EXTRACTION
# ============================================================

def extract_prop_list(raw_response):

    if isinstance(
        raw_response,
        list,
    ):
        return raw_response

    if not isinstance(
        raw_response,
        dict,
    ):
        return []

    possible_keys = [
        "data",
        "props",
        "results",
        "events",
        "odds",
    ]

    for key in possible_keys:

        value = raw_response.get(
            key
        )

        if isinstance(
            value,
            list,
        ):
            return value

    return []


# ============================================================
# FLEXIBLE FIELD GETTER
# ============================================================

def first_value(
    obj,
    *keys,
):

    for key in keys:

        value = obj.get(
            key
        )

        if value is not None:

            return value

    return None


# ============================================================
# NORMALIZE API RESPONSE
# ============================================================

def normalize_props(
    raw_response,
):

    prop_list = extract_prop_list(
        raw_response
    )

    rows = []

    for prop in prop_list:

        if not isinstance(
            prop,
            dict,
        ):
            continue

        player = first_value(
            prop,
            "player_name",
            "player",
        )

        market = first_value(
            prop,
            "market_label",
            "market",
        )

        market_key = first_value(
            prop,
            "market_key",
        )

        book = first_value(
            prop,
            "source",
            "bookmaker",
            "book",
        )

        book_title = first_value(
            prop,
            "source_title",
            "bookmaker_title",
        )

        line = first_value(
            prop,
            "line",
        )

        over_price = first_value(
            prop,
            "over_price",
            "over_odds",
            "over",
        )

        under_price = first_value(
            prop,
            "under_price",
            "under_odds",
            "under",
        )

        home_team = first_value(
            prop,
            "home_team",
        )

        away_team = first_value(
            prop,
            "away_team",
        )

        game_time = first_value(
            prop,
            "commence_time",
        )

        age_seconds = first_value(
            prop,
            "age_seconds",
        )

        event_id = first_value(
            prop,
            "canonical_event_id",
            "event_id",
        )

        rows.append({

            "Player": player,

            "Market": market,

            "Market Key": market_key,

            "Book": book,

            "Book Title": book_title,

            "Line": line,

            "Over Odds": over_price,

            "Under Odds": under_price,

            "Home Team": home_team,

            "Away Team": away_team,

            "Game Time": game_time,

            "Age Seconds": age_seconds,

            "Event ID": event_id,
        })

    return pd.DataFrame(
        rows
    )


# ============================================================
# CLEAN BOOK NAME
# ============================================================

def clean_book_name(
    book,
):

    if pd.isna(book):

        return ""

    return (
        str(book)
        .strip()
        .lower()
        .replace(
            " ",
            "",
        )
        .replace(
            "-",
            "",
        )
        .replace(
            "_",
            "",
        )
    )


# ============================================================
# CLEAN PLAYER
# ============================================================

def clean_player_name(
    player,
):

    if pd.isna(player):

        return ""

    return re.sub(
        r"[^a-z0-9]",
        "",
        str(player)
        .strip()
        .lower(),
    )


# ============================================================
# CLEAN MARKET
# ============================================================

def clean_market_name(
    market,
):

    if pd.isna(market):

        return ""

    return (
        str(market)
        .strip()
        .lower()
    )


def clean_market_key(
    market_key,
):

    if pd.isna(market_key):

        return ""

    return (
        str(market_key)
        .strip()
        .lower()
    )


# ============================================================
# CLEAN TEAM
# ============================================================

def clean_team_name(
    team,
):

    if pd.isna(team):

        return ""

    return re.sub(
        r"[^a-z0-9]",
        "",
        str(team)
        .strip()
        .lower(),
    )


# ============================================================
# PERIOD
# ============================================================

def detect_period(
    market,
    market_key,
):

    text = " ".join([
        clean_market_name(
            market
        ),
        clean_market_key(
            market_key
        ),
    ])

    if re.search(
        r"\b1q\b|first quarter|1st quarter",
        text,
    ):
        return "1Q"

    if re.search(
        r"\b2q\b|second quarter|2nd quarter",
        text,
    ):
        return "2Q"

    if re.search(
        r"\b3q\b|third quarter|3rd quarter",
        text,
    ):
        return "3Q"

    if re.search(
        r"\b4q\b|fourth quarter|4th quarter",
        text,
    ):
        return "4Q"

    if re.search(
        r"\b1h\b|first half|1st half",
        text,
    ):
        return "1H"

    if re.search(
        r"\b2h\b|second half|2nd half",
        text,
    ):
        return "2H"

    return "GAME"


# ============================================================
# SAME GAME
# ============================================================

def same_game(
    underdog,
    comparison,
):

    underdog_event = str(
        underdog.get(
            "Event ID",
            "",
        )
        or ""
    ).strip()

    comparison_event = str(
        comparison.get(
            "Event ID",
            "",
        )
        or ""
    ).strip()

    if (
        underdog_event
        and comparison_event
        and underdog_event
        == comparison_event
    ):

        return True

    underdog_home = clean_team_name(
        underdog.get(
            "Home Team"
        )
    )

    underdog_away = clean_team_name(
        underdog.get(
            "Away Team"
        )
    )

    comparison_home = clean_team_name(
        comparison.get(
            "Home Team"
        )
    )

    comparison_away = clean_team_name(
        comparison.get(
            "Away Team"
        )
    )

    underdog_teams = {
        underdog_home,
        underdog_away,
    } - {""}

    comparison_teams = {
        comparison_home,
        comparison_away,
    } - {""}

    if (
        underdog_teams
        and comparison_teams
        and underdog_teams
        == comparison_teams
    ):

        return True

    return False


# ============================================================
# SAME PROP
# ============================================================

def same_prop(
    underdog,
    comparison,
):

    if clean_player_name(
        underdog.get(
            "Player"
        )
    ) != clean_player_name(
        comparison.get(
            "Player"
        )
    ):

        return False

    underdog_market = clean_market_key(
        underdog.get(
            "Market Key"
        )
    )

    comparison_market = clean_market_key(
        comparison.get(
            "Market Key"
        )
    )

    if not underdog_market:

        underdog_market = (
            clean_market_name(
                underdog.get(
                    "Market"
                )
            )
        )

    if not comparison_market:

        comparison_market = (
            clean_market_name(
                comparison.get(
                    "Market"
                )
            )
        )

    if (
        underdog_market
        != comparison_market
    ):

        return False

    underdog_period = detect_period(
        underdog.get(
            "Market"
        ),
        underdog.get(
            "Market Key"
        ),
    )

    comparison_period = detect_period(
        comparison.get(
            "Market"
        ),
        comparison.get(
            "Market Key"
        ),
    )

    if (
        underdog_period
        != comparison_period
    ):

        return False

    if not same_game(
        underdog,
        comparison,
    ):

        return False

    return True


# ============================================================
# AMERICAN ODDS -> IMPLIED PROBABILITY
# ============================================================

def american_to_implied_probability(
    odds,
):

    try:

        odds = float(
            odds
        )

    except (
        TypeError,
        ValueError,
    ):

        return None

    if odds == 0:

        return None

    if odds > 0:

        return (
            100
            / (
                odds
                + 100
            )
        )

    return (
        abs(odds)
        / (
            abs(odds)
            + 100
        )
    )


# ============================================================
# NO-VIG PROBABILITY
# ============================================================

def calculate_no_vig_probability(
    over_odds,
    under_odds,
):

    over_implied = (
        american_to_implied_probability(
            over_odds
        )
    )

    under_implied = (
        american_to_implied_probability(
            under_odds
        )
    )

    if (
        over_implied is None
        or under_implied is None
    ):

        return None, None

    total = (
        over_implied
        + under_implied
    )

    if total <= 0:

        return None, None

    over_no_vig = (
        over_implied
        / total
    )

    under_no_vig = (
        under_implied
        / total
    )

    return (
        over_no_vig,
        under_no_vig,
    )


# ============================================================
# PROBABILITY -> AMERICAN ODDS
# ============================================================

def probability_to_american_odds(
    probability,
):

    try:

        probability = float(
            probability
        )

    except (
        TypeError,
        ValueError,
    ):

        return None

    if (
        probability <= 0
        or probability >= 1
    ):

        return None

    if probability >= 0.5:

        return -(
            probability
            / (
                1
                - probability
            )
        ) * 100

    return (
        (
            1
            - probability
        )
        / probability
    ) * 100


# ============================================================
# SELECTED-SIDE NO-VIG PROBABILITY
# ============================================================

def selected_side_no_vig_probability(
    pick,
    over_odds,
    under_odds,
):

    over_no_vig, under_no_vig = (
        calculate_no_vig_probability(
            over_odds,
            under_odds,
        )
    )

    if pick == "HIGHER":

        return over_no_vig

    if pick == "LOWER":

        return under_no_vig

    return None


# ============================================================
# BUILD COMPARISON
# ============================================================

def build_market_comparison(
    df,
):

    if df.empty:

        return pd.DataFrame()

    working = df.copy()

    # --------------------------------------------------------
    # CLEAN BOOK
    # --------------------------------------------------------

    working["Book Clean"] = (
        working[
            "Book"
        ].apply(
            clean_book_name
        )
    )

    working.loc[
        working["Book Clean"]
        == "prizepicksmobile",
        "Book Clean",
    ] = "prizepicks"

    working.loc[
        working["Book Clean"]
        == "underdogfantasy",
        "Book Clean",
    ] = "underdog"

    # --------------------------------------------------------
    # LINE
    # --------------------------------------------------------

    working["Line"] = pd.to_numeric(
        working["Line"],
        errors="coerce",
    )

    working["Over Odds"] = pd.to_numeric(
        working["Over Odds"],
        errors="coerce",
    )

    working["Under Odds"] = pd.to_numeric(
        working["Under Odds"],
        errors="coerce",
    )

    working["Age Numeric"] = pd.to_numeric(
        working["Age Seconds"],
        errors="coerce",
    )

    working = working[
        working["Line"].notna()
    ].copy()

    # --------------------------------------------------------
    # UNDERDOG
    # --------------------------------------------------------

    underdog_df = working[
        working[
            "Book Clean"
        ].isin(
            {
                "underdog"
            }
        )
    ].copy()

    # --------------------------------------------------------
    # COMPARISON BOOKS
    # --------------------------------------------------------

    comparison_df = working[
        working[
            "Book Clean"
        ].isin(
            COMPARISON_BOOKS
        )
    ].copy()

    if underdog_df.empty:

        return pd.DataFrame()

    if comparison_df.empty:

        return pd.DataFrame()

    results = []

    # ========================================================
    # EACH UNDERDOG PROP
    # ========================================================

    for _, underdog in (
        underdog_df.iterrows()
    ):

        matches = comparison_df[
            comparison_df.apply(
                lambda row:
                    same_prop(
                        underdog,
                        row,
                    ),
                axis=1,
            )
        ].copy()

        if matches.empty:

            continue

        # Keep freshest row for each book.
        matches = (
            matches
            .sort_values(
                "Age Numeric",
                na_position="last",
            )
            .drop_duplicates(
                subset=[
                    "Book Clean"
                ],
                keep="first",
            )
        )

        result = {

            "Player": underdog[
                "Player"
            ],

            "Prop": underdog[
                "Market"
            ],

            "Market Key": underdog[
                "Market Key"
            ],

            "Period": detect_period(
                underdog[
                    "Market"
                ],
                underdog[
                    "Market Key"
                ],
            ),

            "Home Team": underdog[
                "Home Team"
            ],

            "Away Team": underdog[
                "Away Team"
            ],

            "Game Time": underdog[
                "Game Time"
            ],

            "Event ID": underdog[
                "Event ID"
            ],

            "Underdog": float(
                underdog[
                    "Line"
                ]
            ),

            "DraftKings": None,
            "FanDuel": None,
            "PrizePicks": None,
            "BetMGM": None,

            "DraftKings Over Odds": None,
            "DraftKings Under Odds": None,

            "FanDuel Over Odds": None,
            "FanDuel Under Odds": None,

            "PrizePicks Over Odds": None,
            "PrizePicks Under Odds": None,

            "BetMGM Over Odds": None,
            "BetMGM Under Odds": None,

            "Books": 0,
        }

        # ----------------------------------------------------
        # BOOK LINES + ODDS
        # ----------------------------------------------------

        for _, match in (
            matches.iterrows()
        ):

            book = clean_book_name(
                match[
                    "Book"
                ]
            )

            if book == "prizepicksmobile":

                book = "prizepicks"

            if book == "underdogfantasy":

                book = "underdog"

            line = pd.to_numeric(
                match[
                    "Line"
                ],
                errors="coerce",
            )

            over_odds = pd.to_numeric(
                match[
                    "Over Odds"
                ],
                errors="coerce",
            )

            under_odds = pd.to_numeric(
                match[
                    "Under Odds"
                ],
                errors="coerce",
            )

            if book == "draftkings":

                result[
                    "DraftKings"
                ] = float(
                    line
                )

                result[
                    "DraftKings Over Odds"
                ] = over_odds

                result[
                    "DraftKings Under Odds"
                ] = under_odds

            elif book == "fanduel":

                result[
                    "FanDuel"
                ] = float(
                    line
                )

                result[
                    "FanDuel Over Odds"
                ] = over_odds

                result[
                    "FanDuel Under Odds"
                ] = under_odds

            elif book == "prizepicks":

                result[
                    "PrizePicks"
                ] = float(
                    line
                )

                result[
                    "PrizePicks Over Odds"
                ] = over_odds

                result[
                    "PrizePicks Under Odds"
                ] = under_odds

            elif book == "betmgm":

                result[
                    "BetMGM"
                ] = float(
                    line
                )

                result[
                    "BetMGM Over Odds"
                ] = over_odds

                result[
                    "BetMGM Under Odds"
                ] = under_odds

        # ----------------------------------------------------
        # CONSENSUS LINE
        # ----------------------------------------------------

        values = [
            result[
                "DraftKings"
            ],
            result[
                "FanDuel"
            ],
            result[
                "PrizePicks"
            ],
            result[
                "BetMGM"
            ],
        ]

        valid_values = [
            value
            for value in values
            if value is not None
            and pd.notna(value)
        ]

        if not valid_values:

            continue

        result[
            "Books"
        ] = len(
            valid_values
        )

        result[
            "Market Consensus"
        ] = (
            sum(
                valid_values
            )
            / len(
                valid_values
            )
        )

        # ----------------------------------------------------
        # LINE DIFFERENCE
        # ----------------------------------------------------

        result[
            "Difference"
        ] = (
            result[
                "Market Consensus"
            ]
            - result[
                "Underdog"
            ]
        )

        # ----------------------------------------------------
        # SAFE DISCREPANCY %
        # ----------------------------------------------------

        denominator = (
            abs(
                result[
                    "Market Consensus"
                ]
            )
            +
            abs(
                result[
                    "Underdog"
                ]
            )
        ) / 2

        if denominator > 0:

            result[
                "Line Diff %"
            ] = (
                abs(
                    result[
                        "Difference"
                    ]
                )
                / denominator
            ) * 100

        else:

            result[
                "Line Diff %"
            ] = 0.0

        # ----------------------------------------------------
        # PICK
        # ----------------------------------------------------

        if (
            result[
                "Difference"
            ] > 0
        ):

            result[
                "Pick"
            ] = "HIGHER"

        elif (
            result[
                "Difference"
            ] < 0
        ):

            result[
                "Pick"
            ] = "LOWER"

        else:

            result[
                "Pick"
            ] = "NEUTRAL"

        # ----------------------------------------------------
        # NO-VIG PROBABILITIES
        # ----------------------------------------------------

        book_no_vig = []

        book_names = [
            "DraftKings",
            "FanDuel",
            "PrizePicks",
            "BetMGM",
        ]

        for book_name in book_names:

            over_column = (
                f"{book_name} Over Odds"
            )

            under_column = (
                f"{book_name} Under Odds"
            )

            probability = (
                selected_side_no_vig_probability(
                    result[
                        "Pick"
                    ],
                    result[
                        over_column
                    ],
                    result[
                        under_column
                    ],
                )
            )

            result[
                f"{book_name} No-Vig %"
            ] = (
                probability * 100
                if probability is not None
                else None
            )

            if probability is not None:

                book_no_vig.append(
                    probability
                )

        # ----------------------------------------------------
        # AVERAGE NO-VIG PROBABILITY
        # ----------------------------------------------------

        if book_no_vig:

            average_no_vig = (
                sum(
                    book_no_vig
                )
                / len(
                    book_no_vig
                )
            )

            result[
                "Average No-Vig %"
            ] = (
                average_no_vig
                * 100
            )

            result[
                "Average No-Vig Odds"
            ] = (
                probability_to_american_odds(
                    average_no_vig
                )
            )

            result[
                "No-Vig Books"
            ] = len(
                book_no_vig
            )

        else:

            result[
                "Average No-Vig %"
            ] = None

            result[
                "Average No-Vig Odds"
            ] = None

            result[
                "No-Vig Books"
            ] = 0

        # ----------------------------------------------------
        # BOOK CONFIRMATION
        # ----------------------------------------------------

        result[
            "Book Confirmation %"
        ] = (
            (
                result[
                    "No-Vig Books"
                ]
                / len(
                    COMPARISON_BOOKS
                )
            )
            * 100
        )

        # ----------------------------------------------------
        # FINAL SCORE
        #
        # We normalize the three components to a 0-100
        # style score:
        #
        # 1. No-vig probability
        # 2. Line edge
        # 3. Book confirmation
        #
        # The no-vig probability is the dominant factor.
        # ----------------------------------------------------

        no_vig_component = (
            result[
                "Average No-Vig %"
            ]
            if pd.notna(
                result[
                    "Average No-Vig %"
                ]
            )
            else 0
        )

        line_edge_component = min(
            max(
                result[
                    "Line Diff %"
                ],
                0,
            ),
            100,
        )

        confirmation_component = (
            result[
                "Book Confirmation %"
            ]
        )

        result[
            "Final Score"
        ] = (
            (
                no_vig_component
                * NO_VIG_WEIGHT
            )
            +
            (
                line_edge_component
                * LINE_EDGE_WEIGHT
            )
            +
            (
                confirmation_component
                * BOOK_CONFIRMATION_WEIGHT
            )
        )

        results.append(
            result
        )

    if not results:

        return pd.DataFrame()

    return pd.DataFrame(
        results
    )


# ============================================================
# BOOK STATUS
# ============================================================

def build_book_status(
    props_df,
):

    if props_df.empty:

        return pd.DataFrame()

    normalized_books = (
        props_df[
            "Book"
        ]
        .fillna("")
        .apply(
            clean_book_name
        )
        .replace(
            {
                "prizepicksmobile":
                    "prizepicks",
                "underdogfantasy":
                    "underdog",
            }
        )
    )

    rows = []

    for book in [
        "draftkings",
        "fanduel",
        "prizepicks",
        "betmgm",
        "underdog",
    ]:

        count = int(
            (
                normalized_books
                == book
            ).sum()
        )

        rows.append({

            "Book":
                DISPLAY_NAMES[
                    book
                ],

            "Requested":
                "YES",

            "Returned":
                "YES"
                if count > 0
                else "NO",

            "Records":
                count,
        })

    return pd.DataFrame(
        rows
    )


# ============================================================
# HEADER
# ============================================================

left, right = st.columns(
    [1, 3]
)

with left:

    scan_button = st.button(
        "🔄 SCAN NOW",
        type="primary",
        use_container_width=True,
    )

with right:

    if st.session_state.last_scan:

        st.write(
            f"**Last scan:** "
            f"{st.session_state.last_scan}"
        )

    else:

        st.write(
            "**Last scan:** Never"
        )


# ============================================================
# RUN SCAN
# ============================================================

if scan_button:

    st.session_state.scan_error = None

    try:

        with st.spinner(
            f"Getting current {selected_sport} "
            "player props..."
        ):

            raw_response = get_props()

            st.session_state.raw_props = (
                raw_response
            )

            props_df = normalize_props(
                raw_response
            )

            comparison_df = (
                build_market_comparison(
                    props_df
                )
            )

            st.session_state.scan_results = (
                comparison_df
            )

            st.session_state.last_sport = (
                selected_sport
            )

            st.session_state.last_scan = (
                datetime.now().strftime(
                    "%b %d, %Y %I:%M %p"
                )
            )

    except requests.exceptions.HTTPError as error:

        st.session_state.scan_error = (
            "API returned an HTTP error: "
            f"{error}"
        )

    except Exception as error:

        st.session_state.scan_error = (
            "Something went wrong: "
            f"{error}"
        )


# ============================================================
# ERROR
# ============================================================

if st.session_state.scan_error:

    st.error(
        st.session_state.scan_error
    )

    st.stop()


# ============================================================
# NO SCAN
# ============================================================

comparison_df = (
    st.session_state.scan_results
)

if comparison_df is None:

    st.info(
        "Select a sport and click "
        "**SCAN NOW**."
    )

    st.stop()


# ============================================================
# RAW DATA
# ============================================================

props_df = normalize_props(
    st.session_state.raw_props
)


# ============================================================
# DATA SUMMARY
# ============================================================

st.divider()

st.header(
    "📡 Data Summary"
)

c1, c2, c3, c4 = st.columns(
    4
)

with c1:

    st.metric(
        "Records Received",
        len(props_df),
    )

with c2:

    st.metric(
        "Matched Props",
        len(comparison_df),
    )

with c3:

    unique_players = (
        props_df[
            "Player"
        ]
        .dropna()
        .nunique()
        if not props_df.empty
        else 0
    )

    st.metric(
        "Players",
        unique_players,
    )

with c4:

    unique_books = (
        props_df[
            "Book"
        ]
        .dropna()
        .nunique()
        if not props_df.empty
        else 0
    )

    st.metric(
        "Books Found",
        unique_books,
    )


# ============================================================
# SOURCES
# ============================================================

if not props_df.empty:

    st.subheader(
        "Sportsbooks / Sources Found"
    )

    source_counts = (
        props_df[
            "Book"
        ]
        .fillna("Unknown")
        .value_counts()
    )

    st.dataframe(
        source_counts.rename(
            "Records"
        ),
        use_container_width=True,
    )

    st.subheader(
        "Requested Comparison Books"
    )

    st.dataframe(
        build_book_status(
            props_df
        ),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# NO MATCHES
# ============================================================

if comparison_df.empty:

    st.warning(
        "No matching Underdog props were found "
        "against the comparison books."
    )

    st.subheader(
        "🔎 Debug Information"
    )

    st.write(
        f"PropEdge received {len(props_df)} "
        f"{selected_sport} records, but could not "
        "find matching player props."
    )

    if not props_df.empty:

        st.write(
            "**Books returned by the API:**"
        )

        st.write(
            props_df[
                "Book"
            ]
            .dropna()
            .unique()
            .tolist()
        )

        st.write(
            "**Markets returned by the API:**"
        )

        st.write(
            props_df[
                "Market"
            ]
            .dropna()
            .unique()
            .tolist()
        )

        st.write(
            "**Market keys returned by the API:**"
        )

        st.write(
            props_df[
                "Market Key"
            ]
            .dropna()
            .unique()
            .tolist()
        )

        debug_df = props_df[
            [
                "Player",
                "Market",
                "Market Key",
                "Book",
                "Line",
                "Over Odds",
                "Under Odds",
                "Home Team",
                "Away Team",
                "Game Time",
                "Event ID",
                "Age Seconds",
            ]
        ].copy()

        debug_df[
            "Period"
        ] = debug_df.apply(
            lambda row:
                detect_period(
                    row[
                        "Market"
                    ],
                    row[
                        "Market Key"
                    ],
                ),
            axis=1,
        )

        st.subheader(
            "First 100 API Records"
        )

        st.dataframe(
            debug_df.head(
                100
            ),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.error(
            "The API response contained no "
            "recognizable prop records."
        )

    st.stop()


# ============================================================
# RANKING
# ============================================================

comparison_df = (
    comparison_df.copy()
)


# ------------------------------------------------------------
# ABSOLUTE LINE DIFFERENCE
# ------------------------------------------------------------

comparison_df[
    "Abs Difference"
] = (
    comparison_df[
        "Difference"
    ].abs()
)


# ------------------------------------------------------------
# PRIMARY SORT
#
# FINAL SCORE is used for the overall Best Props ranking.
#
# Average No-Vig Probability remains the primary ordering
# for the main chart.
# ------------------------------------------------------------

comparison_df = (
    comparison_df
    .sort_values(
        [
            "Final Score",
            "Average No-Vig %",
            "Line Diff %",
            "Books",
        ],
        ascending=[
            False,
            False,
            False,
            False,
        ],
        na_position="last",
    )
    .reset_index(
        drop=True
    )
)

comparison_df[
    "Rank"
] = (
    comparison_df.index
    + 1
)


# ============================================================
# BEST PROPS
# ============================================================

st.header(
    "🔥 Best Props"
)

c1, c2, c3, c4 = st.columns(
    4
)

with c1:

    st.metric(
        "Matched Props",
        len(comparison_df),
    )

with c2:

    st.metric(
        "Top No-Vig Probability",
        (
            f"{comparison_df['Average No-Vig %'].max():.1f}%"
            if comparison_df[
                "Average No-Vig %"
            ].notna().any()
            else "N/A"
        ),
    )

with c3:

    st.metric(
        "Largest Line Difference",
        f"{comparison_df['Abs Difference'].max():.1f}",
    )

with c4:

    normalized_books = (
        props_df[
            "Book"
        ]
        .fillna("")
        .apply(
            clean_book_name
        )
        .replace(
            {
                "prizepicksmobile":
                    "prizepicks",
                "underdogfantasy":
                    "underdog",
            }
        )
    )

    comparison_book_count = len(
        set(
            normalized_books
        )
        .intersection(
            COMPARISON_BOOKS
        )
    )

    st.metric(
        "Comparison Books",
        f"{comparison_book_count} / 4",
    )


# ============================================================
# MAIN TABLE
# ============================================================

display_columns = [
    "Rank",
    "Player",
    "Prop",
    "Period",
    "Pick",
    "Underdog",
    "Market Consensus",
    "Difference",
    "Line Diff %",
    "Average No-Vig %",
    "Average No-Vig Odds",
    "No-Vig Books",
    "Books",
    "Book Confirmation %",
    "Final Score",
]

display_df = (
    comparison_df[
        display_columns
    ].copy()
)


# ============================================================
# ROUND NUMBERS
# ============================================================

for column in [
    "Underdog",
    "Market Consensus",
    "Difference",
]:

    display_df[
        column
    ] = (
        pd.to_numeric(
            display_df[
                column
            ],
            errors="coerce",
        )
        .round(1)
    )


display_df[
    "Line Diff %"
] = (
    pd.to_numeric(
        display_df[
            "Line Diff %"
        ],
        errors="coerce",
    )
    .round(2)
)


display_df[
    "Average No-Vig %"
] = (
    pd.to_numeric(
        display_df[
            "Average No-Vig %"
        ],
        errors="coerce",
    )
    .round(2)
)


display_df[
    "Average No-Vig Odds"
] = (
    pd.to_numeric(
        display_df[
            "Average No-Vig Odds"
        ],
        errors="coerce",
    )
    .round(0)
)


display_df[
    "Book Confirmation %"
] = (
    pd.to_numeric(
        display_df[
            "Book Confirmation %"
        ],
        errors="coerce",
    )
    .round(1)
)


display_df[
    "Final Score"
] = (
    pd.to_numeric(
        display_df[
            "Final Score"
        ],
        errors="coerce",
    )
    .round(2)
)


# ============================================================
# DISPLAY
# ============================================================

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# RANKING EXPLANATION
# ============================================================

st.subheader(
    "📐 How PropEdge Ranks Props"
)

st.write(
    "PropEdge calculates no-vig probability separately "
    "for each sportsbook by removing the sportsbook's "
    "vig from its Over/Under prices."
)

st.write(
    "The overall Final Score combines average no-vig "
    "probability, line edge, and sportsbook confirmation. "
    "No-vig probability receives the largest weight."
)

st.write(
    "The main chart uses a different, intentional rule: "
    "it is ordered strictly by the highest average no-vig "
    "probability first. This keeps the chart's #1 prop "
    "as the highest-probability market signal."
)


# ============================================================
# SCORING WEIGHTS
# ============================================================

st.subheader(
    "⚙️ Current Ranking Weights"
)

weight_df = pd.DataFrame({

    "Factor": [
        "Average No-Vig Probability",
        "Line Edge",
        "Book Confirmation",
    ],

    "Weight": [
        f"{NO_VIG_WEIGHT * 100:.0f}%",
        f"{LINE_EDGE_WEIGHT * 100:.0f}%",
        f"{BOOK_CONFIRMATION_WEIGHT * 100:.0f}%",
    ],

})

st.dataframe(
    weight_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# BOOK-BY-BOOK TABLE
# ============================================================

st.subheader(
    "📚 Book-by-Book Comparison"
)

book_comparison_df = comparison_df[
    [
        "Player",
        "Prop",
        "Period",
        "Pick",
        "Underdog",

        "DraftKings",
        "DraftKings No-Vig %",

        "FanDuel",
        "FanDuel No-Vig %",

        "PrizePicks",
        "PrizePicks No-Vig %",

        "BetMGM",
        "BetMGM No-Vig %",

        "Market Consensus",
        "Average No-Vig %",
        "No-Vig Books",
        "Books",
    ]
].copy()


for column in [
    "Underdog",
    "DraftKings",
    "FanDuel",
    "PrizePicks",
    "BetMGM",
    "Market Consensus",
]:

    book_comparison_df[
        column
    ] = (
        pd.to_numeric(
            book_comparison_df[
                column
            ],
            errors="coerce",
        )
        .round(1)
    )


for column in [
    "DraftKings No-Vig %",
    "FanDuel No-Vig %",
    "PrizePicks No-Vig %",
    "BetMGM No-Vig %",
    "Average No-Vig %",
]:

    book_comparison_df[
        column
    ] = (
        pd.to_numeric(
            book_comparison_df[
                column
            ],
            errors="coerce",
        )
        .round(2)
    )


st.dataframe(
    book_comparison_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# CHART
# ============================================================

st.header(
    "📊 Top Market Discrepancies"
)


# ------------------------------------------------------------
# IMPORTANT:
#
# The chart is intentionally sorted by:
#
# 1. Highest Average No-Vig Probability
# 2. Highest Line Diff %
# 3. Most confirming books
#
# This fixes the previous problem where the chart was
# inheriting the old line-difference ranking.
# ------------------------------------------------------------

chart_df = (
    comparison_df
    .sort_values(
        [
            "Average No-Vig %",
            "Line Diff %",
            "No-Vig Books",
        ],
        ascending=[
            False,
            False,
            False,
        ],
        na_position="last",
    )
    .head(10)
    .copy()
)


chart_df[
    "Label"
] = (
    chart_df[
        "Player"
    ].astype(str)
    + " — "
    + chart_df[
        "Prop"
    ].astype(str)
    + " — "
    + chart_df[
        "Pick"
    ].astype(str)
)


chart_df = (
    chart_df
    .set_index(
        "Label"
    )
)


st.bar_chart(
    chart_df[
        "Average No-Vig %"
    ]
)


# ============================================================
# NO-VIG DETAIL
# ============================================================

st.subheader(
    "🎯 No-Vig Probability Board"
)

novig_columns = [
    "Player",
    "Prop",
    "Pick",
    "Average No-Vig %",
    "Average No-Vig Odds",
    "No-Vig Books",
    "Books",
    "Line Diff %",
    "Final Score",
]

novig_df = (
    comparison_df[
        novig_columns
    ]
    .sort_values(
        [
            "Average No-Vig %",
            "No-Vig Books",
            "Line Diff %",
        ],
        ascending=[
            False,
            False,
            False,
        ],
        na_position="last",
    )
    .head(25)
    .copy()
)


for column in [
    "Average No-Vig %",
    "Line Diff %",
    "Final Score",
]:

    novig_df[
        column
    ] = (
        pd.to_numeric(
            novig_df[
                column
            ],
            errors="coerce",
        )
        .round(2)
    )


novig_df[
    "Average No-Vig Odds"
] = (
    pd.to_numeric(
        novig_df[
            "Average No-Vig Odds"
        ],
        errors="coerce",
    )
    .round(0)
)


st.dataframe(
    novig_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# RAW API DATA
# ============================================================

with st.expander(
    "🔎 View Raw API Data"
):

    st.write(
        "This shows the normalized records returned "
        "by ParlayAPI before PropEdge performs its "
        "matching and ranking logic."
    )

    if not props_df.empty:

        st.dataframe(
            props_df,
            use_container_width=True,
            hide_index=True,
        )
