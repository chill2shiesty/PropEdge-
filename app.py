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
    "FanDuel, DraftKings, PrizePicks, and BetMGM."
)


# ============================================================
# SETTINGS
# ============================================================

SPORT_KEY = "americanfootball_nfl"

# Books we want to compare against Underdog.
# ParlayAPI may not currently have live data for every requested
# source. The app now reports which sources actually returned.
REQUESTED_BOOKMAKERS = [
    "draftkings",
    "fanduel",
    "prizepicks",
    "betmgm",
    "underdog",
]

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

if "coverage_results" not in st.session_state:
    st.session_state.coverage_results = None


# ============================================================
# API HELPERS
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
    Retrieve NFL player props from ParlayAPI.

    The request explicitly asks for all comparison sources plus
    Underdog. ParlayAPI can still omit a source when it does not
    have fresh/current data for the requested market.
    """

    url = (
        f"https://parlay-api.com/v1/sports/"
        f"{SPORT_KEY}/props"
    )

    params = {
        "bookmakers": ",".join(REQUESTED_BOOKMAKERS),
        "markets": ",".join(REQUESTED_MARKETS),
        "limit": 10000,
        "maxAgeSec": 900,
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


def get_props_coverage():
    """
    Ask ParlayAPI which books survive the exact prop filters.

    This endpoint is diagnostic and does not consume credits.
    """

    url = (
        f"https://parlay-api.com/v1/sports/"
        f"{SPORT_KEY}/props/coverage"
    )

    params = {
        "bookmakers": ",".join(REQUESTED_BOOKMAKERS),
        "markets": ",".join(REQUESTED_MARKETS),
        "limit": 5000,
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
# EXTRACT LIST FROM API RESPONSE
# ============================================================

def extract_prop_list(raw_response):
    """
    ParlayAPI normally returns a list of prop rows, but this
    function also supports common wrapped response structures.
    """

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

    prop_list = extract_prop_list(raw_response)

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
# CLEANING HELPERS
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


def clean_player_name(player):

    if pd.isna(player):
        return ""

    # Remove punctuation differences such as apostrophes.
    return re.sub(
        r"[^a-z0-9]",
        "",
        str(player).strip().lower(),
    )


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
# PROP PERIOD / SCOPE DETECTION
# ============================================================

def detect_period(market, market_key):
    """
    Prevent accidental comparisons such as:

        Underdog: 1Q Receptions 0.5
        PrizePicks: Receptions 5.5

    Those are different props even if both use
    player_receptions as the underlying market key.
    """

    text = " ".join(
        [
            clean_market_name(market),
            clean_market_key(market_key),
        ]
    )

    # Quarter-specific props.
    if re.search(r"\b1q\b|first quarter|1st quarter", text):
        return "1Q"

    if re.search(r"\b2q\b|second quarter|2nd quarter", text):
        return "2Q"

    if re.search(r"\b3q\b|third quarter|3rd quarter", text):
        return "3Q"

    if re.search(r"\b4q\b|fourth quarter|4th quarter", text):
        return "4Q"

    # Half-specific props.
    if re.search(r"\b1h\b|first half|1st half", text):
        return "1H"

    if re.search(r"\b2h\b|second half|2nd half", text):
        return "2H"

    # Game / full-game props.
    if re.search(r"\bgame\b|full game|full-game", text):
        return "GAME"

    # If no period is specified, treat the prop as full game.
    return "GAME"


def build_match_key(row):
    """
    Primary identity for a prop.

    We deliberately include:
      - event
      - player
      - market key
      - period/scope

    This is much safer than grouping only by player + market.
    """

    event_id = str(row.get("Event ID", "") or "").strip()
    player = clean_player_name(row.get("Player"))
    market_key = clean_market_key(row.get("Market Key"))

    if not market_key:
        market_key = clean_market_name(row.get("Market"))

    period = detect_period(
        row.get("Market"),
        row.get("Market Key"),
    )

    return (
        event_id,
        player,
        market_key,
        period,
    )


# ============================================================
# BUILD MARKET COMPARISON
# ============================================================

def build_market_comparison(df):

    if df.empty:
        return pd.DataFrame()

    working = df.copy()

    # Normalize book names.
    working["Book Clean"] = (
        working["Book"]
        .apply(clean_book_name)
    )

    # Normalize players.
    working["Player Clean"] = (
        working["Player"]
        .apply(clean_player_name)
    )

    # Normalize market key.
    working["Market Clean"] = (
        working["Market Key"]
        .fillna(working["Market"])
        .apply(clean_market_key)
    )

    # Detect whether the prop is full-game, quarter, half, etc.
    working["Period"] = working.apply(
        lambda row: detect_period(
            row["Market"],
            row["Market Key"],
        ),
        axis=1,
    )

    # Normalize lines.
    working["Line"] = pd.to_numeric(
        working["Line"],
        errors="coerce",
    )

    # Normalize age.
    working["Age Numeric"] = pd.to_numeric(
        working["Age Seconds"],
        errors="coerce",
    )

    working = working[
        working["Line"].notna()
    ].copy()

    # Create strict match key.
    working["Match Key"] = working.apply(
        build_match_key,
        axis=1,
    )

    results = []

    for match_key, group in working.groupby(
        "Match Key",
        dropna=False,
    ):

        # ----------------------------------------------------
        # Find Underdog
        # ----------------------------------------------------

        underdog_rows = group[
            group["Book Clean"].isin(
                UNDERDOG_NAMES
            )
        ].copy()

        if underdog_rows.empty:
            continue

        # Use the freshest Underdog observation.
        underdog_rows = (
            underdog_rows
            .sort_values(
                "Age Numeric",
                na_position="last",
            )
        )

        underdog = underdog_rows.iloc[0]

        underdog_line = float(
            underdog["Line"]
        )

        # ----------------------------------------------------
        # Find OTHER BOOKS
        # ----------------------------------------------------

        other_books = group[
            group["Book Clean"].isin(
                COMPARISON_BOOKS
            )
        ].copy()

        if other_books.empty:
            continue

        # One row per sportsbook.
        other_books = (
            other_books
            .sort_values(
                "Age Numeric",
                na_position="last",
            )
            .drop_duplicates(
                subset=["Book Clean"],
                keep="first",
            )
        )

        if other_books.empty:
            continue

        # ----------------------------------------------------
        # Market average
        # ----------------------------------------------------

        market_line = float(
            other_books["Line"].mean()
        )

        difference = (
            market_line - underdog_line
        )

        # ----------------------------------------------------
        # SAFE / SYMMETRIC LINE DIFFERENCE
        # ----------------------------------------------------
        #
        # We DO NOT use:
        #
        #   difference / underdog_line * 100
        #
        # because 0.5 -> 5.5 becomes 1000%, which is
        # mathematically valid but misleading for this UI.
        #
        # Instead, normalize by the average absolute line.
        #
        # Example:
        #   UD = 0.5
        #   Market = 5.5
        #
        #   midpoint = 3.0
        #   difference = 5.0
        #   symmetric difference = 166.67%
        #
        # More importantly, the strict period matching above
        # should prevent this particular bad 1Q/full-game
        # comparison from happening at all.
        # ----------------------------------------------------

        denominator = (
            abs(underdog_line) +
            abs(market_line)
        ) / 2

        if denominator > 0:
            line_diff_pct = (
                abs(difference)
                / denominator
            ) * 100
        else:
            line_diff_pct = 0.0

        if difference > 0:
            pick = "HIGHER"

        elif difference < 0:
            pick = "LOWER"

        else:
            pick = "NEUTRAL"

        # ----------------------------------------------------
        # BOOK DETAILS
        # ----------------------------------------------------

        books_present = (
            other_books["Book Clean"]
            .dropna()
            .unique()
            .tolist()
        )

        book_count = len(
            books_present
        )

        results.append({
            "Player": underdog["Player"],
            "Prop": (
                underdog["Market"]
                if pd.notna(underdog["Market"])
                else underdog["Market Key"]
            ),
            "Market Key": underdog["Market Key"],
            "Period": underdog["Period"],
            "Event ID": underdog["Event ID"],
            "Underdog": underdog_line,
            "Market": market_line,
            "Difference": difference,
            "Line Diff %": line_diff_pct,
            "Pick": pick,
            "Books": book_count,
            "Book List": ", ".join(
                books_present
            ),
        })

    return pd.DataFrame(results)


# ============================================================
# COVERAGE NORMALIZATION
# ============================================================

def extract_coverage_rows(raw_response):
    """
    Coverage responses can vary slightly in wrapper structure.
    Find a list of dictionaries wherever possible.
    """

    if isinstance(raw_response, list):
        return raw_response

    if not isinstance(raw_response, dict):
        return []

    possible_keys = [
        "data",
        "coverage",
        "results",
        "books",
        "sources",
    ]

    for key in possible_keys:

        value = raw_response.get(key)

        if isinstance(value, list):
            return value

    # Some API responses may return a dict keyed by bookmaker.
    rows = []

    for key, value in raw_response.items():

        if isinstance(value, dict):

            row = value.copy()
            row.setdefault(
                "bookmaker",
                key,
            )
            rows.append(row)

    return rows


def normalize_coverage(raw_response):

    rows = extract_coverage_rows(
        raw_response
    )

    if not rows:
        return pd.DataFrame()

    normalized = []

    for row in rows:

        if not isinstance(row, dict):
            continue

        bookmaker = (
            row.get("bookmaker")
            or row.get("book")
            or row.get("source")
            or row.get("key")
        )

        normalized.append({
            "Book": bookmaker,
            "Book Clean": clean_book_name(
                bookmaker
            ),
            "Raw": row,
        })

    return pd.DataFrame(normalized)


# ============================================================
# HEADER / SCAN BUTTON
# ============================================================

left, right = st.columns([1, 3])

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
# RUN MANUAL SCAN
# ============================================================

if scan_button:

    st.session_state.scan_error = None

    try:

        with st.spinner(
            "Getting current NFL player props..."
        ):

            # Coverage is diagnostic and does not consume credits.
            try:

                coverage_response = (
                    get_props_coverage()
                )

                st.session_state.coverage_results = (
                    coverage_response
                )

            except Exception:

                # Coverage failure should not prevent
                # the main prop scan from running.
                st.session_state.coverage_results = None

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
            f"API returned an HTTP error: "
            f"{error}"
        )

    except Exception as error:

        st.session_state.scan_error = (
            f"Something went wrong: "
            f"{error}"
        )


# ============================================================
# SHOW ERROR
# ============================================================

if st.session_state.scan_error:

    st.error(
        st.session_state.scan_error
    )

    st.stop()


# ============================================================
# DISPLAY RESULTS
# ============================================================

comparison_df = (
    st.session_state.scan_results
)


# ============================================================
# NO SCAN YET
# ============================================================

if comparison_df is None:

    st.info(
        "Click **SCAN NOW** to retrieve "
        "the latest NFL player props."
    )

    st.stop()


# ============================================================
# DEBUG / RAW DATA
# ============================================================

raw_props = (
    st.session_state.raw_props
)

props_df = normalize_props(
    raw_props
)


# ============================================================
# DATA SUMMARY
# ============================================================

st.divider()

st.header("📡 Data Summary")

c1, c2, c3, c4 = st.columns(4)

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
# SHOW BOOKS FOUND
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
        book_counts.rename("Records"),
        use_container_width=True,
    )

    # --------------------------------------------------------
    # Explicit requested-book status
    # --------------------------------------------------------

    st.subheader(
        "Requested Comparison Books"
    )

    status_rows = []

    actual_books = {
        clean_book_name(book)
        for book in props_df["Book"]
        .dropna()
        .tolist()
    }

    display_names = {
        "draftkings": "DraftKings",
        "fanduel": "FanDuel",
        "prizepicks": "PrizePicks",
        "betmgm": "BetMGM",
        "underdog": "Underdog",
    }

    for book_key in REQUESTED_BOOKMAKERS:

        status_rows.append({
            "Book": display_names.get(
                book_key,
                book_key,
            ),
            "Requested": "YES",
            "Returned": (
                "YES"
                if book_key in actual_books
                else "NO"
            ),
            "Records": int(
                (
                    props_df["Book"]
                    .apply(clean_book_name)
                    == book_key
                ).sum()
            ),
        })

    st.dataframe(
        pd.DataFrame(status_rows),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# SHOW COVERAGE DIAGNOSTICS
# ============================================================

if st.session_state.coverage_results is not None:

    with st.expander(
        "📡 ParlayAPI Coverage Diagnostics"
    ):

        st.write(
            "This is the response from ParlayAPI's "
            "props coverage endpoint for the exact "
            "book and market filters used by PropEdge."
        )

        coverage_df = normalize_coverage(
            st.session_state.coverage_results
        )

        if not coverage_df.empty:

            coverage_display = coverage_df[
                ["Book"]
            ].copy()

            coverage_display[
                "Book"
            ] = coverage_display[
                "Book"
            ].astype(str)

            coverage_display = (
                coverage_display
                .drop_duplicates()
                .reset_index(drop=True)
            )

            st.dataframe(
                coverage_display,
                use_container_width=True,
                hide_index=True,
            )

        st.json(
            st.session_state.coverage_results
        )


# ============================================================
# SHOW DEBUG DATA IF NO MATCHES
# ============================================================

if comparison_df.empty:

    st.warning(
        "No matching Underdog props were found "
        "against the requested comparison books."
    )

    st.subheader(
        "🔎 Debug Information"
    )

    st.write(
        "The API returned data, but PropEdge "
        "could not find a strict match. "
        "Matching now requires the same event, "
        "player, market key, and betting period."
    )

    if not props_df.empty:

        st.write(
            "**Book values returned by the API:**"
        )

        st.write(
            props_df["Book"]
            .dropna()
            .unique()
            .tolist()
        )

        st.write(
            "**Market values returned by the API:**"
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

        # Show detected periods so quarter/full-game
        # mismatches are obvious.
        debug_periods = props_df[
            [
                "Player",
                "Market",
                "Market Key",
                "Book",
            ]
        ].copy()

        debug_periods["Period"] = debug_periods.apply(
            lambda row: detect_period(
                row["Market"],
                row["Market Key"],
            ),
            axis=1,
        )

        st.write(
            "**Detected prop periods:**"
        )

        st.dataframe(
            debug_periods.head(100),
            use_container_width=True,
            hide_index=True,
        )

        st.subheader(
            "First 100 Records"
        )

        st.dataframe(
            props_df.head(100),
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

comparison_df = comparison_df.copy()

comparison_df["Abs Line Diff"] = (
    comparison_df["Difference"]
    .abs()
)

comparison_df = (
    comparison_df
    .sort_values(
        "Abs Line Diff",
        ascending=False,
    )
    .reset_index(drop=True)
)

comparison_df["Rank"] = (
    comparison_df.index + 1
)


# ============================================================
# MAIN METRICS
# ============================================================

st.header("🔥 Best Props")

c1, c2, c3 = st.columns(3)

with c1:

    st.metric(
        "Matched Props",
        len(comparison_df),
    )

with c2:

    st.metric(
        "Largest Line Difference",
        f"{comparison_df['Abs Line Diff'].max():.1f}",
    )

with c3:

    actual_comparison_books = sorted(
        set(
            book
            for book in props_df["Book"]
            .dropna()
            .apply(clean_book_name)
            .tolist()
            if book in COMPARISON_BOOKS
        )
    )

    st.metric(
        "Comparison Books",
        f"{len(actual_comparison_books)} / "
        f"{len(COMPARISON_BOOKS)}",
    )


# ============================================================
# MAIN TABLE
# ============================================================

display_df = comparison_df[
    [
        "Rank",
        "Player",
        "Prop",
        "Period",
        "Underdog",
        "Market",
        "Difference",
        "Line Diff %",
        "Pick",
        "Books",
        "Book List",
    ]
].copy()

for column in [
    "Underdog",
    "Market",
    "Difference",
]:

    display_df[column] = (
        display_df[column]
        .round(1)
    )

display_df["Line Diff %"] = (
    display_df["Line Diff %"]
    .round(2)
)

display_df = display_df.rename(
    columns={
        "Line Diff %": "Line Diff %",
        "Book List": "Comparison Books",
    }
)

st.dataframe(
    display_df,
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

chart_df = chart_df.set_index(
    "Label"
)

st.bar_chart(
    chart_df["Line Diff %"]
)


# ============================================================
# RAW DATA
# ============================================================

with st.expander(
    "🔎 View Raw API Data"
):

    st.write(
        "This section is for development/debugging. "
        "It lets us verify exactly what the data provider "
        "is returning before we build the final EV model."
    )

    if not props_df.empty:

        st.dataframe(
            props_df,
            use_container_width=True,
            hide_index=True,
        )
