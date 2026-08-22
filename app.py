import re
import requests
import pandas as pd
import streamlit as st
from datetime import datetime


# ============================================================
# PROPEdge
# NFL PLAYER PROP MARKET SCANNER
# ============================================================

st.set_page_config(
    page_title="PropEdge",
    page_icon="🏈",
    layout="wide",
)

st.title("🏈 PropEdge")
st.subheader("NFL Player Prop Market Scanner")

st.write(
    "Compare Underdog player-prop lines against "
    "DraftKings, FanDuel, PrizePicks, and BetMGM."
)


# ============================================================
# SETTINGS
# ============================================================

SPORT_KEY = "americanfootball_nfl"

# IMPORTANT:
#
# We intentionally DO NOT send a "bookmakers" filter.
#
# ParlayAPI's /props endpoint returns all available books
# in one call. We want the API to return everything it has,
# then our code will identify the books we care about.
#
# This is important because our previous version returned
# only Underdog + PrizePicks.

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

REQUESTED_MARKETS = [
    "player_pass_yds",
    "player_pass_tds",
    "player_pass_completions",
    "player_rush_yds",
    "player_rec_yds",
    "player_receptions",
    "player_anytime_td",
    "player_interceptions",
]

DISPLAY_NAMES = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "prizepicks": "PrizePicks",
    "betmgm": "BetMGM",
    "underdog": "Underdog",
}

# ParlayAPI's props endpoint can serve the latest row per
# book from the last 60 minutes.
#
# We previously used 900 seconds / 15 minutes, which may
# unnecessarily eliminate books that haven't updated recently.
MAX_AGE_SECONDS = 3600


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


# ============================================================
# API
# ============================================================

def get_api_key():

    if "PARLAY_API_KEY" not in st.secrets:
        raise ValueError(
            "PARLAY_API_KEY is missing from Streamlit Secrets."
        )

    return st.secrets["PARLAY_API_KEY"]


def get_headers():

    return {
        "X-API-Key": get_api_key(),
        "Accept": "application/json",
    }


def get_props():

    """
    Retrieve NFL player props.

    IMPORTANT:
    We do NOT send a bookmakers parameter.

    This allows ParlayAPI to return all available books.
    PropEdge then filters the returned data locally.
    """

    url = (
        f"https://parlay-api.com/v1/sports/"
        f"{SPORT_KEY}/props"
    )

    params = {
        "markets": ",".join(REQUESTED_MARKETS),
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
# EXTRACT API LIST
# ============================================================

def extract_prop_list(raw_response):

    if isinstance(raw_response, list):
        return raw_response

    if not isinstance(raw_response, dict):
        return []

    possible_keys = [
        "data",
        "props",
        "results",
        "events",
        "odds",
    ]

    for key in possible_keys:

        value = raw_response.get(key)

        if isinstance(value, list):
            return value

    return []


# ============================================================
# NORMALIZE API DATA
# ============================================================

def normalize_props(raw_response):

    prop_list = extract_prop_list(
        raw_response
    )

    rows = []

    for prop in prop_list:

        if not isinstance(prop, dict):
            continue

        rows.append({
            "Player": prop.get("player"),
            "Market": prop.get("market"),
            "Market Key": prop.get("market_key"),
            "Book": prop.get("bookmaker"),
            "Book Title": prop.get("bookmaker_title"),
            "Line": prop.get("line"),
            "Over Odds": prop.get("over_price"),
            "Under Odds": prop.get("under_price"),
            "Home Team": prop.get("home_team"),
            "Away Team": prop.get("away_team"),
            "Game Time": prop.get("commence_time"),
            "Age Seconds": prop.get("age_seconds"),
            "Event ID": prop.get("canonical_event_id"),
        })

    return pd.DataFrame(rows)


# ============================================================
# CLEAN BOOK
# ============================================================

def clean_book_name(book):

    if pd.isna(book):
        return ""

    return (
        str(book)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )


# ============================================================
# CLEAN PLAYER
# ============================================================

def clean_player_name(player):

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

def clean_market_name(market):

    if pd.isna(market):
        return ""

    return (
        str(market)
        .strip()
        .lower()
    )


def clean_market_key(market_key):

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

def clean_team_name(team):

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
# DETECT PROP PERIOD
# ============================================================

def detect_period(
    market,
    market_key,
):

    text = " ".join([
        clean_market_name(market),
        clean_market_key(market_key),
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

    if re.search(
        r"\bgame\b|full game|full-game",
        text,
    ):
        return "GAME"

    # Normal NFL player props are full-game unless
    # their market name explicitly indicates another period.
    return "GAME"


# ============================================================
# SAME GAME
# ============================================================

def same_game(
    underdog,
    comparison,
):

    underdog_event = str(
        underdog.get("Event ID", "")
        or ""
    ).strip()

    comparison_event = str(
        comparison.get("Event ID", "")
        or ""
    ).strip()

    # First choice:
    # If both sources have the same canonical event ID,
    # this is a definite match.
    if (
        underdog_event
        and comparison_event
        and underdog_event == comparison_event
    ):
        return True

    # Do NOT require Event ID equality.
    #
    # Different providers can represent the same game
    # differently. Fall back to normalized teams.

    underdog_home = clean_team_name(
        underdog.get("Home Team")
    )

    underdog_away = clean_team_name(
        underdog.get("Away Team")
    )

    comparison_home = clean_team_name(
        comparison.get("Home Team")
    )

    comparison_away = clean_team_name(
        comparison.get("Away Team")
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
        and underdog_teams == comparison_teams
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
        underdog.get("Player")
    ) != clean_player_name(
        comparison.get("Player")
    ):
        return False

    # --------------------------------------------------------
    # MARKET
    # --------------------------------------------------------

    underdog_market = clean_market_key(
        underdog.get("Market Key")
    )

    comparison_market = clean_market_key(
        comparison.get("Market Key")
    )

    # Fall back to display market if market key is missing.
    if not underdog_market:

        underdog_market = clean_market_name(
            underdog.get("Market")
        )

    if not comparison_market:

        comparison_market = clean_market_name(
            comparison.get("Market")
        )

    if underdog_market != comparison_market:
        return False

    # --------------------------------------------------------
    # PERIOD
    # --------------------------------------------------------

    underdog_period = detect_period(
        underdog.get("Market"),
        underdog.get("Market Key"),
    )

    comparison_period = detect_period(
        comparison.get("Market"),
        comparison.get("Market Key"),
    )

    if underdog_period != comparison_period:
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

def build_market_comparison(df):

    if df.empty:
        return pd.DataFrame()

    working = df.copy()

    # --------------------------------------------------------
    # NORMALIZE
    # --------------------------------------------------------

    working["Book Clean"] = (
        working["Book"]
        .apply(clean_book_name)
    )

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
        working["Book Clean"].isin(
            UNDERDOG_NAMES
        )
    ].copy()

    # --------------------------------------------------------
    # COMPARISON BOOKS
    # --------------------------------------------------------

    comparison_df = working[
        working["Book Clean"].isin(
            COMPARISON_BOOKS
        )
    ].copy()

    if underdog_df.empty:
        return pd.DataFrame()

    if comparison_df.empty:
        return pd.DataFrame()

    results = []

    # ========================================================
    # PROCESS EACH UNDERDOG PROP
    # ========================================================

    for _, underdog in underdog_df.iterrows():

        # ----------------------------------------------------
        # FIND MATCHES
        # ----------------------------------------------------

        matches = comparison_df[
            comparison_df.apply(
                lambda row: same_prop(
                    underdog,
                    row,
                ),
                axis=1,
            )
        ].copy()

        if matches.empty:
            continue

        # ----------------------------------------------------
        # FRESHEST ROW PER BOOK
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # BASE RESULT
        # ----------------------------------------------------

        result = {

            "Player": underdog["Player"],

            "Prop": (
                underdog["Market"]
                if pd.notna(
                    underdog["Market"]
                )
                else underdog["Market Key"]
            ),

            "Market Key": (
                underdog["Market Key"]
            ),

            "Period": detect_period(
                underdog["Market"],
                underdog["Market Key"],
            ),

            "Home Team": (
                underdog["Home Team"]
            ),

            "Away Team": (
                underdog["Away Team"]
            ),

            "Game Time": (
                underdog["Game Time"]
            ),

            "Event ID": (
                underdog["Event ID"]
            ),

            "Underdog": float(
                underdog["Line"]
            ),

            "DraftKings": None,

            "FanDuel": None,

            "PrizePicks": None,

            "BetMGM": None,

            "Books": 0,
        }

        # ----------------------------------------------------
        # INSERT BOOK LINES
        # ----------------------------------------------------

        for _, match in matches.iterrows():

            book = clean_book_name(
                match["Book"]
            )

            if book == "draftkings":

                result["DraftKings"] = float(
                    match["Line"]
                )

            elif book == "fanduel":

                result["FanDuel"] = float(
                    match["Line"]
                )

            elif book == "prizepicks":

                result["PrizePicks"] = float(
                    match["Line"]
                )

            elif book == "betmgm":

                result["BetMGM"] = float(
                    match["Line"]
                )

        # ----------------------------------------------------
        # CONSENSUS
        # ----------------------------------------------------

        book_values = [
            result["DraftKings"],
            result["FanDuel"],
            result["PrizePicks"],
            result["BetMGM"],
        ]

        valid_values = [
            value
            for value in book_values
            if value is not None
            and pd.notna(value)
        ]

        if not valid_values:
            continue

        result["Books"] = len(
            valid_values
        )

        result["Market Consensus"] = (
            sum(valid_values)
            / len(valid_values)
        )

        # ----------------------------------------------------
        # DIFFERENCE
        # ----------------------------------------------------

        result["Difference"] = (
            result["Market Consensus"]
            - result["Underdog"]
        )

        # ----------------------------------------------------
        # SAFE PERCENTAGE
        # ----------------------------------------------------
        #
        # DO NOT do:
        #
        # difference / underdog * 100
        #
        # because:
        #
        # 5.5 - 0.5 = 5
        # 5 / 0.5 = 1000%
        #
        # That creates a technically correct but misleading
        # percentage.
        #
        # Instead use the midpoint of the two lines.

        denominator = (
            abs(result["Market Consensus"])
            + abs(result["Underdog"])
        ) / 2

        if denominator > 0:

            result["Line Diff %"] = (
                abs(result["Difference"])
                / denominator
            ) * 100

        else:

            result["Line Diff %"] = 0.0

        # ----------------------------------------------------
        # PICK
        # ----------------------------------------------------

        if result["Difference"] > 0:

            result["Pick"] = "HIGHER"

        elif result["Difference"] < 0:

            result["Pick"] = "LOWER"

        else:

            result["Pick"] = "NEUTRAL"

        results.append(result)

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results)


# ============================================================
# BOOK STATUS
# ============================================================

def build_book_status(props_df):

    if props_df.empty:

        actual_books = set()

    else:

        actual_books = {
            clean_book_name(book)
            for book in props_df["Book"]
            .dropna()
            .tolist()
        }

    rows = []

    for book in [
        "draftkings",
        "fanduel",
        "prizepicks",
        "betmgm",
        "underdog",
    ]:

        if props_df.empty:

            records = 0

        else:

            records = int(
                (
                    props_df["Book"]
                    .apply(clean_book_name)
                    == book
                ).sum()
            )

        rows.append({
            "Book": DISPLAY_NAMES[book],

            "Requested": "YES",

            "Returned": (
                "YES"
                if book in actual_books
                else "NO"
            ),

            "Records": records,
        })

    return pd.DataFrame(rows)


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
            "Getting current NFL player props..."
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
# RESULTS
# ============================================================

comparison_df = (
    st.session_state.scan_results
)

if comparison_df is None:

    st.info(
        "Click **SCAN NOW** to retrieve "
        "the latest NFL player props."
    )

    st.stop()


# ============================================================
# NORMALIZE RAW DATA
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

    if not props_df.empty:

        unique_players = (
            props_df["Player"]
            .dropna()
            .nunique()
        )

    else:

        unique_players = 0

    st.metric(
        "Players",
        unique_players,
    )

with c4:

    if not props_df.empty:

        unique_books = (
            props_df["Book"]
            .dropna()
            .nunique()
        )

    else:

        unique_books = 0

    st.metric(
        "Books Found",
        unique_books,
    )


# ============================================================
# SPORTSBOOKS FOUND
# ============================================================

if not props_df.empty:

    st.subheader(
        "Sportsbooks / Sources Found"
    )

    book_counts = (
        props_df["Book"]
        .fillna("Unknown")
        .value_counts()
    )

    st.dataframe(
        book_counts.rename(
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
        "The API returned data, but PropEdge "
        "could not find a prop with the same "
        "player, market key, period, and game."
    )

    if not props_df.empty:

        st.write(
            "**Books returned by the API:**"
        )

        st.write(
            props_df["Book"]
            .dropna()
            .unique()
            .tolist()
        )

        st.write(
            "**Markets returned by the API:**"
        )

        st.write(
            props_df["Market"]
            .dropna()
            .unique()
            .tolist()
        )

        st.write(
            "**Market keys returned by the API:**"
        )

        st.write(
            props_df["Market Key"]
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

        debug_df["Period"] = (
            debug_df.apply(
                lambda row:
                    detect_period(
                        row["Market"],
                        row["Market Key"],
                    ),
                axis=1,
            )
        )

        st.subheader(
            "First 100 API Records"
        )

        st.dataframe(
            debug_df.head(100),
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
# RANK PROPS
# ============================================================

comparison_df = (
    comparison_df.copy()
)

comparison_df["Abs Difference"] = (
    comparison_df["Difference"]
    .abs()
)

# Props with more comparison books get priority.
# Within the same book count, largest line differences
# appear first.

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

comparison_df["Rank"] = (
    comparison_df.index + 1
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

    if not props_df.empty:

        actual_books = {
            clean_book_name(book)
            for book in props_df["Book"]
            .dropna()
            .tolist()
        }

    else:

        actual_books = set()

    available_comparison_books = (
        actual_books
        .intersection(
            COMPARISON_BOOKS
        )
    )

    st.metric(
        "Comparison Books",
        f"{len(available_comparison_books)} / "
        f"{len(COMPARISON_BOOKS)}",
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


# ------------------------------------------------------------
# ROUND LINES
# ------------------------------------------------------------

for column in [
    "Underdog",
    "DraftKings",
    "FanDuel",
    "PrizePicks",
    "BetMGM",
    "Market Consensus",
    "Difference",
]:

    display_df[column] = (
        pd.to_numeric(
            display_df[column],
            errors="coerce",
        )
        .round(1)
    )


# ------------------------------------------------------------
# ROUND PERCENTAGE
# ------------------------------------------------------------

display_df["Line Diff %"] = (
    pd.to_numeric(
        display_df["Line Diff %"],
        errors="coerce",
    )
    .round(2)
)


st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# COMPARISON EXPLANATION
# ============================================================

st.subheader(
    "📖 How Each Prop Was Compared"
)

st.write(
    "Each row starts with an Underdog line. "
    "PropEdge then looks for the same player, "
    "market, betting period, and game at DraftKings, "
    "FanDuel, PrizePicks, and BetMGM. "
    "Only books that actually returned a matching line "
    "are included in the Market Consensus."
)


# ============================================================
# BOOK-BY-BOOK VIEW
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

    book_comparison_df[column] = (
        pd.to_numeric(
            book_comparison_df[column],
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

chart_df["Label"] = (
    chart_df["Player"].astype(str)
    + " — "
    + chart_df["Prop"].astype(str)
    + " — "
    + chart_df["Pick"].astype(str)
)

chart_df = (
    chart_df.set_index(
        "Label"
    )
)

st.bar_chart(
    chart_df["Line Diff %"]
)


# ============================================================
# RAW API DATA
# ============================================================

with st.expander(
    "🔎 View Raw API Data"
):

    st.write(
        "This section shows the exact records "
        "returned by ParlayAPI before PropEdge "
        "matches them."
    )

    if not props_df.empty:

        st.dataframe(
            props_df,
            use_container_width=True,
            hide_index=True,
        )
