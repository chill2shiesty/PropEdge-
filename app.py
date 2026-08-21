import requests
import pandas as pd
import streamlit as st


# ============================================================
# PropEdge
# ============================================================

st.set_page_config(
    page_title="PropEdge",
    page_icon="🏈",
    layout="wide",
)

st.title("🏈 PropEdge")
st.subheader("NFL Player Prop Market Scanner")

st.write(
    "Compare Underdog lines against FanDuel, DraftKings, "
    "PrizePicks, and BetMGM."
)


# ============================================================
# SETTINGS
# ============================================================

SPORT_KEY = "americanfootball_nfl"

BOOKMAKERS = [
    "draftkings",
    "fanduel",
    "prizepicks",
    "betmgm",
    "underdog",
]

NFL_MARKETS = [
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
# GET PROPS
# ============================================================

def get_props():

    api_key = st.secrets["PARLAY_API_KEY"]

    url = (
        f"https://parlay-api.com/v1/sports/"
        f"{SPORT_KEY}/props"
    )

    params = {
        "bookmakers": ",".join(BOOKMAKERS),
        "markets": ",".join(NFL_MARKETS),
        "limit": 10000,
        "maxAgeSec": 900,
        "dfsOdds": "midpoint",
    }

    headers = {
        "X-API-Key": api_key
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# NORMALIZE DATA
# ============================================================

def normalize_props(raw_props):

    if not raw_props:
        return pd.DataFrame()

    rows = []

    for prop in raw_props:

        rows.append({
            "Player": prop.get("player"),
            "Market Key": prop.get("market_key"),
            "Prop": prop.get("market"),
            "Book": prop.get("bookmaker"),
            "Book Title": prop.get("bookmaker_title"),
            "Line": prop.get("line"),
            "Over Odds": prop.get("over_price"),
            "Under Odds": prop.get("under_price"),
            "Game": (
                f"{prop.get('away_team')} @ "
                f"{prop.get('home_team')}"
            ),
            "Game Time": prop.get("commence_time"),
            "Age Seconds": prop.get("age_seconds"),
            "Event ID": prop.get("canonical_event_id"),
        })

    return pd.DataFrame(rows)


# ============================================================
# COMPARE UNDERDOG TO MARKET
# ============================================================

def build_market_comparison(df):

    if df.empty:
        return pd.DataFrame()

    comparison_books = {
        "draftkings",
        "fanduel",
        "prizepicks",
        "betmgm",
    }

    df = df[
        df["Book"].isin(
            comparison_books | {"underdog"}
        )
    ].copy()

    df = df[
        df["Line"].notna()
    ].copy()

    results = []

    grouping = [
        "Player",
        "Market Key",
        "Prop",
        "Event ID",
    ]

    for group_values, group in df.groupby(
        grouping,
        dropna=False
    ):

        underdog = group[
            group["Book"] == "underdog"
        ]

        if underdog.empty:
            continue

        underdog_line = underdog.iloc[0]["Line"]

        other_books = group[
            group["Book"].isin(
                comparison_books
            )
        ]

        other_books = other_books[
            other_books["Line"].notna()
        ]

        if other_books.empty:
            continue

        market_line = other_books[
            "Line"
        ].mean()

        difference = (
            market_line - underdog_line
        )

        edge_pct = (
            difference / underdog_line
        ) * 100 if underdog_line else 0

        if difference > 0:
            pick = "HIGHER"
        elif difference < 0:
            pick = "LOWER"
        else:
            pick = "NEUTRAL"

        results.append({
            "Player": group_values[0],
            "Prop": group_values[2],
            "Underdog": underdog_line,
            "Market": market_line,
            "Difference": difference,
            "Edge %": edge_pct,
            "Pick": pick,
            "Books": other_books["Book"].nunique(),
            "Event ID": group_values[3],
        })

    return pd.DataFrame(results)


# ============================================================
# MANUAL SCAN
# ============================================================

if "scan_results" not in st.session_state:
    st.session_state.scan_results = None

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None


col1, col2 = st.columns([1, 3])

with col1:

    scan_button = st.button(
        "🔄 SCAN NOW",
        type="primary",
        use_container_width=True,
    )

with col2:

    if st.session_state.last_scan:

        st.caption(
            f"Last scan: "
            f"{st.session_state.last_scan}"
        )

    else:

        st.caption(
            "No scan performed yet."
        )


# ============================================================
# RUN SCAN
# ============================================================

if scan_button:

    try:

        with st.spinner(
            "Scanning NFL player props..."
        ):

            raw_props = get_props()

            props_df = normalize_props(
                raw_props
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
                pd.Timestamp.now()
                .strftime(
                    "%b %d, %Y %I:%M %p"
                )
            )

    except requests.exceptions.HTTPError as e:

        st.error(
            f"API error: {e}"
        )

    except Exception as e:

        st.error(
            f"Something went wrong: {e}"
        )


# ============================================================
# DISPLAY RESULTS
# ============================================================

comparison_df = (
    st.session_state.scan_results
)


if comparison_df is None:

    st.info(
        "Click **SCAN NOW** to retrieve the latest "
        "NFL player prop lines."
    )

else:

    if comparison_df.empty:

        st.warning(
            "No matching Underdog props were found "
            "in this scan."
        )

    else:

        comparison_df = comparison_df.copy()

        comparison_df["Abs Edge"] = (
            comparison_df["Edge %"].abs()
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

        # ---------------------------------------------
        # Metrics
        # ---------------------------------------------

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric(
                "Matched Props",
                len(comparison_df)
            )

        with c2:
            st.metric(
                "Highest Edge",
                f"{comparison_df['Abs Edge'].max():.2f}%"
            )

        with c3:
            st.metric(
                "Books Compared",
                "4"
            )

        # ---------------------------------------------
        # Table
        # ---------------------------------------------

        st.header("🔥 Best Props")

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
                display_df[column].round(1)
            )

        display_df["Edge %"] = (
            display_df["Edge %"].round(2)
        )

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )

        # ---------------------------------------------
        # Chart
        # ---------------------------------------------

        st.header(
            "📊 Top Market Discrepancies"
        )

        chart_df = comparison_df.head(10).copy()

        chart_df["Label"] = (
            chart_df["Player"]
            + " — "
            + chart_df["Prop"]
            + " — "
            + chart_df["Pick"]
        )

        chart_df = chart_df.set_index(
            "Label"
        )

        st.bar_chart(
            chart_df["Edge %"]
        )
