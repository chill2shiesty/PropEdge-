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

UNDERDOG_NAMES = {
    "underdog",
    "underdogfantasy",
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

    IMPORTANT:
    We intentionally do NOT send a bookmakers filter.

    ParlayAPI's /props endpoint returns all available books
    for the sport in one call.
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

        # ----------------------------------------------------
        # CURRENT PARLAYAPI FIELD NAMES
        # ----------------------------------------------------

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
        )

        under_price = first_value(
            prop,
            "under_price",
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

    # MLB props are generally full-game props.
    # NFL can contain quarter/half markets.

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

    # Best-case match.
    if (
        underdog_event
        and comparison_event
        and underdog_event
        == comparison_event
    ):

        return True

    # --------------------------------------------------------
    # FALLBACK TO TEAMS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # PLAYER
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # MARKET KEY
    # --------------------------------------------------------

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

    # If market keys are unavailable,
    # fall back to market labels.

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

    # --------------------------------------------------------
    # PERIOD
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # GAME
    # --------------------------------------------------------

    if not same_game(
        underdog,
        comparison,
    ):

        return False

    return True


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

    # Normalize PrizePicks Mobile.
    working.loc[
        working["Book Clean"]
        == "prizepicksmobile",
        "Book Clean",
    ] = "prizepicks"

    # Normalize Underdog.
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

            "Books": 0,
        }

        # ----------------------------------------------------
        # BOOK LINES
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

            if book == "draftkings":

                result[
                    "DraftKings"
                ] = float(
                    match[
                        "Line"
                    ]
                )

            elif book == "fanduel":

                result[
                    "FanDuel"
                ] = float(
                    match[
                        "Line"
                    ]
                )

            elif book == "prizepicks":

                result[
                    "PrizePicks"
                ] = float(
                    match[
                        "Line"
                    ]
                )

            elif book == "betmgm":

                result[
                    "BetMGM"
                ] = float(
                    match[
                        "Line"
                    ]
                )

        # ----------------------------------------------------
        # CONSENSUS
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
        # DIFFERENCE
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
# RANK
# ============================================================

comparison_df = (
    comparison_df.copy()
)

comparison_df[
    "Abs Difference"
] = (
    comparison_df[
        "Difference"
    ].abs()
)

comparison_df = (
    comparison_df
    .sort_values(
        [
            "Books",
            "Abs Difference",
        ],
        ascending=[
            False,
            False,
        ],
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

c1, c2, c3 = st.columns(
    3
)

with c1:

    st.metric(
        "Matched Props",
        len(comparison_df),
    )

with c2:

    st.metric(
        "Largest Line Difference",
        f"{comparison_df['Abs Difference'].max():.1f}",
    )

with c3:

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
    "Underdog",
    "DraftKings",
    "FanDuel",
    "PrizePicks",
    "BetMGM",
    "Market Consensus",
    "Difference",
    "Line Diff %",
    "Pick",
    "Books",
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
    "DraftKings",
    "FanDuel",
    "PrizePicks",
    "BetMGM",
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


# ============================================================
# DISPLAY
# ============================================================

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# EXPLANATION
# ============================================================

st.subheader(
    "📖 How PropEdge Compares Props"
)

if selected_sport == "MLB":

    st.write(
        "For MLB, PropEdge matches an Underdog prop "
        "to the same player, MLB market, and game "
        "across DraftKings, FanDuel, PrizePicks, "
        "and BetMGM."
    )

else:

    st.write(
        "For NFL, PropEdge matches an Underdog prop "
        "to the same player, market, period, and game "
        "across DraftKings, FanDuel, PrizePicks, "
        "and BetMGM."
    )

st.write(
    "Only books that actually return a matching line "
    "are included in the Market Consensus."
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
        "Underdog",
        "DraftKings",
        "FanDuel",
        "PrizePicks",
        "BetMGM",
        "Market Consensus",
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

chart_df = (
    comparison_df
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
    chart_df.set_index(
        "Label"
    )
)

st.bar_chart(
    chart_df[
        "Line Diff %"
    ]
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
        "matching logic."
    )

    if not props_df.empty:

        st.dataframe(
            props_df,
            use_container_width=True,
            hide_index=True,
        )
