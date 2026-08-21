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

REQUESTED_BOOKMAKERS = [
    "draftkings",
    "fanduel",
    "prizepicks",
    "betmgm",
    "underdog",
]

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


# ============================================================
# API FUNCTION
# ============================================================

def get_props():
    """
    Retrieve NFL player props from ParlayAPI.
    """

    if "PARLAY_API_KEY" not in st.secrets:
        raise ValueError(
            "PARLAY_API_KEY is missing from Streamlit Secrets."
        )

    api_key = st.secrets["PARLAY_API_KEY"]

    url = (
        f"https://parlay-api.com/v1/sports/"
        f"{SPORT_KEY}/props"
    )

    params = {
        "bookmakers": ",".join(
            REQUESTED_BOOKMAKERS
        ),
        "markets": ",".join(
            REQUESTED_MARKETS
        ),
        "limit": 10000,
        "maxAgeSec": 900,
        "dfsOdds": "midpoint",
    }

    headers = {
        "X-API-Key": api_key,
        "Accept": "application/json",
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# EXTRACT LIST FROM API RESPONSE
# ============================================================

def extract_prop_list(raw_response):
    """
    ParlayAPI responses can be wrapped in different structures.
    This function tries to find the actual list of props.
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
            "Book Title": prop.get(
                "bookmaker_title"
            ),
            "Line": prop.get("line"),
            "Over Odds": prop.get(
                "over_price"
            ),
            "Under Odds": prop.get(
                "under_price"
            ),
            "Home Team": prop.get(
                "home_team"
            ),
            "Away Team": prop.get(
                "away_team"
            ),
            "Game Time": prop.get(
                "commence_time"
            ),
            "Age Seconds": prop.get(
                "age_seconds"
            ),
            "Event ID": prop.get(
                "canonical_event_id"
            ),
        })

    return pd.DataFrame(rows)


# ============================================================
# CLEAN BOOK NAME
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
# CLEAN PLAYER NAME
# ============================================================

def clean_player_name(player):

    if pd.isna(player):
        return ""

    return (
        str(player)
        .strip()
        .lower()
    )


# ============================================================
# CLEAN MARKET NAME
# ============================================================

def clean_market_name(market):

    if pd.isna(market):
        return ""

    return (
        str(market)
        .strip()
        .lower()
    )


# ============================================================
# BUILD MARKET COMPARISON
# ============================================================

def build_market_comparison(df):

    if df.empty:
        return pd.DataFrame()

    working = df.copy()

    # Normalize book names so variations such as
    # "Underdog" / "underdog" don't break matching.

    working["Book Clean"] = (
        working["Book"]
        .apply(clean_book_name)
    )

    working["Player Clean"] = (
        working["Player"]
        .apply(clean_player_name)
    )

    working["Market Clean"] = (
        working["Market Key"]
        .fillna(
            working["Market"]
        )
        .apply(clean_market_name)
    )

    working["Line"] = pd.to_numeric(
        working["Line"],
        errors="coerce"
    )

    working = working[
        working["Line"].notna()
    ].copy()

    # We compare Underdog against these books.

    comparison_books = {
        "draftkings",
        "fanduel",
        "prizepicks",
        "betmgm",
    }

    # These are all possible ways a source might
    # identify Underdog.

    underdog_names = {
        "underdog",
        "underdogfantasy",
    }

    results = []

    # Group primarily by player + market.
    # We avoid relying exclusively on event IDs because
    # different providers may use different IDs.

    grouping = [
        "Player Clean",
        "Market Clean",
    ]

    for group_values, group in working.groupby(
        grouping,
        dropna=False
    ):

        underdog_rows = group[
            group["Book Clean"].isin(
                underdog_names
            )
        ].copy()

        if underdog_rows.empty:
            continue

        # If multiple Underdog rows exist for the same
        # player/market, use the freshest one when possible.

        if "Age Seconds" in underdog_rows.columns:

            underdog_rows["Age Numeric"] = (
                pd.to_numeric(
                    underdog_rows["Age Seconds"],
                    errors="coerce"
                )
            )

            underdog_rows = (
                underdog_rows
                .sort_values(
                    "Age Numeric",
                    na_position="last"
                )
            )

        underdog = underdog_rows.iloc[0]

        underdog_line = float(
            underdog["Line"]
        )

        # Find comparison books.

        other_books = group[
            group["Book Clean"].isin(
                comparison_books
            )
        ].copy()

        if other_books.empty:
            continue

        # Make sure we don't accidentally use multiple
        # duplicate entries from the same sportsbook.

        other_books = (
            other_books
            .drop_duplicates(
                subset=["Book Clean"],
                keep="first"
            )
        )

        if other_books.empty:
            continue

        market_line = float(
            other_books["Line"].mean()
        )

        difference = (
            market_line - underdog_line
        )

        if underdog_line != 0:

            edge_pct = (
                difference
                / abs(underdog_line)
            ) * 100

        else:

            edge_pct = 0

        if difference > 0:
            pick = "HIGHER"

        elif difference < 0:
            pick = "LOWER"

        else:
            pick = "NEUTRAL"

        results.append({
            "Player": underdog["Player"],
            "Prop": (
                underdog["Market"]
                if pd.notna(
                    underdog["Market"]
                )
                else underdog["Market Key"]
            ),
            "Underdog": underdog_line,
            "Market": market_line,
            "Difference": difference,
            "Edge %": edge_pct,
            "Pick": pick,
            "Books": other_books[
                "Book Clean"
            ].nunique(),
        })

    return pd.DataFrame(results)


# ============================================================
# HEADER / SCAN BUTTON
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
# RUN MANUAL SCAN
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
# DEBUG INFORMATION
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
        len(props_df)
    )

with c2:

    st.metric(
        "Matched Props",
        len(comparison_df)
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
        unique_players
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
        unique_books
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
        book_counts.rename(
            "Records"
        ),
        use_container_width=True
    )


# ============================================================
# SHOW DEBUG DATA IF NO MATCHES
# ============================================================

if comparison_df.empty:

    st.warning(
        "No matching Underdog props were found."
    )

    st.subheader(
        "🔎 Debug Information"
    )

    st.write(
        "The API returned data, but PropEdge "
        "could not find matching Underdog props."
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

comparison_df["Abs Edge"] = (
    comparison_df["Edge %"]
    .abs()
)

comparison_df = (
    comparison_df
    .sort_values(
        "Abs Edge",
        ascending=False
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
        len(comparison_df)
    )

with c2:

    st.metric(
        "Largest Discrepancy",
        f"{comparison_df['Abs Edge'].max():.2f}%"
    )

with c3:

    st.metric(
        "Comparison Books",
        "4"
    )


# ============================================================
# MAIN TABLE
# ============================================================

display_df = comparison_df[
    [
        "Rank",
        "Player",
        "Prop",
        "Underdog",
        "Market",
        "Difference",
        "Edge %",
        "Pick",
        "Books",
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


display_df["Edge %"] = (
    display_df["Edge %"]
    .round(2)
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
    chart_df["Edge %"]
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
