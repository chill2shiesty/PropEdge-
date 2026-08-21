import streamlit as st
import pandas as pd


# -----------------------------
# PropEdge - First Prototype
# -----------------------------

st.set_page_config(
    page_title="PropEdge",
    page_icon="🏈",
    layout="wide"
)

st.title("🏈 PropEdge")
st.subheader("NFL Player Prop Market Scanner")

st.write(
    "Compare Underdog lines against the broader player-prop market."
)

# Sample data for our first prototype
data = [
    {
        "Player": "Ja'Marr Chase",
        "Prop": "Receiving Yards",
        "Underdog": 82.5,
        "FanDuel": 88.5,
        "DraftKings": 87.5,
        "PrizePicks": 86.5,
        "BetMGM": 88.5,
    },
    {
        "Player": "Derrick Henry",
        "Prop": "Rushing Yards",
        "Underdog": 71.5,
        "FanDuel": 78.5,
        "DraftKings": 77.5,
        "PrizePicks": 76.5,
        "BetMGM": 79.5,
    },
    {
        "Player": "CeeDee Lamb",
        "Prop": "Receiving Yards",
        "Underdog": 74.5,
        "FanDuel": 79.5,
        "DraftKings": 78.5,
        "PrizePicks": 80.5,
        "BetMGM": 79.5,
    },
    {
        "Player": "Lamar Jackson",
        "Prop": "Passing Yards",
        "Underdog": 241.5,
        "FanDuel": 253.5,
        "DraftKings": 251.5,
        "PrizePicks": 252.5,
        "BetMGM": 255.5,
    },
]

df = pd.DataFrame(data)

# Calculate market consensus
books = [
    "FanDuel",
    "DraftKings",
    "PrizePicks",
    "BetMGM"
]

df["Market Consensus"] = df[books].mean(axis=1)

# Difference between market and Underdog
df["Difference"] = (
    df["Market Consensus"] - df["Underdog"]
)

# Percentage difference
df["Edge %"] = (
    df["Difference"] / df["Underdog"]
) * 100

# Determine direction
df["Pick"] = df["Difference"].apply(
    lambda x: "HIGHER" if x > 0 else "LOWER"
)

# Rank by absolute discrepancy
df["Rank"] = (
    df["Edge %"]
    .abs()
    .rank(
        ascending=False,
        method="first"
    )
    .astype(int)
)

df = df.sort_values("Rank")

# -----------------------------
# Dashboard
# -----------------------------

st.header("🔥 Best Props")

display_columns = [
    "Rank",
    "Player",
    "Prop",
    "Underdog",
    "Market Consensus",
    "Difference",
    "Edge %",
    "Pick",
]

display_df = df[display_columns].copy()

display_df["Difference"] = display_df[
    "Difference"
].round(2)

display_df["Edge %"] = display_df[
    "Edge %"
].round(2)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)

# -----------------------------
# Chart
# -----------------------------

st.header("📊 Market Discrepancy")

chart_df = df[
    ["Player", "Edge %"]
].set_index("Player")

st.bar_chart(chart_df)

# -----------------------------
# Explanation
# -----------------------------

st.divider()

st.subheader("How PropEdge Works")

st.write(
    """
    PropEdge compares Underdog's player-prop lines against
    the corresponding lines from FanDuel, DraftKings,
    PrizePicks, and BetMGM.

    A positive discrepancy means the broader market is
    currently higher than Underdog's line.

    A negative discrepancy means the broader market is
    currently lower than Underdog's line.

    This prototype uses sample data. No live sportsbook
    data is being collected yet.
    """
)
