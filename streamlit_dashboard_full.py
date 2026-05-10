#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VivaReal Multi-City Dashboard
Interactive Plotly version with property estimator
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import re
from pathlib import Path

# --------------------------------------------------
# Settings
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "vivareal_history.csv"

st.set_page_config(
    page_title="VivaReal Multi-City Dashboard",
    layout="wide"
)

# --------------------------------------------------
# Styling
# --------------------------------------------------
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1300px;
    }

    section[data-testid="stSidebar"] {
        background-color: #111827;
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {
        color: #f9fafb;
    }

    .main-title {
        font-size: 2.3rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
        letter-spacing: -0.03em;
    }

    .subtitle {
        color: #9ca3af;
        font-size: 1rem;
        margin-bottom: 1.6rem;
    }

    .metric-card {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        padding: 1.15rem;
        border-radius: 18px;
        border: 1px solid #374151;
        box-shadow: 0 8px 24px rgba(0,0,0,0.18);
        min-height: 105px;
    }

    .metric-label {
        color: #9ca3af;
        font-size: 0.82rem;
        margin-bottom: 0.45rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .metric-value {
        color: #f9fafb;
        font-size: 1.45rem;
        font-weight: 750;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 16px;
        overflow: hidden;
    }

    .stButton > button,
    .stDownloadButton > button {
        border-radius: 12px;
        border: 1px solid #374151;
        padding: 0.6rem 1rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------
# Data cleaning helpers
# --------------------------------------------------
def parse_brl(value):
    """
    Converts:
    'R$ 395.000' -> 395000
    'A partir de R$ 1.317.053' -> 1317053
    'R$ 395.000,00. extra' -> 395000
    """
    if pd.isna(value):
        return None

    value = str(value)
    match = re.search(r"R\$ ?([\d\.]+(?:,\d{1,2})?)", value)

    if not match:
        return None

    number = match.group(1)
    number = number.replace(".", "")
    number = number.replace(",", ".")

    try:
        return float(number)
    except ValueError:
        return None


def parse_first_number(value):
    """
    Converts:
    '78 m²' -> 78
    '105 - 160 m²' -> 105
    '1 - 2' -> 1
    """
    if pd.isna(value):
        return None

    value = str(value)
    match = re.search(r"(\d+(?:[.,]\d+)?)", value)

    if not match:
        return None

    number = match.group(1).replace(",", ".")

    try:
        return float(number)
    except ValueError:
        return None


@st.cache_data
def load_data():
    df = pd.read_csv(CSV_FILE)

    # Compatibility with older Fortaleza-only history files
    if "city" not in df.columns:
        df["city"] = "Fortaleza"

    if "state" not in df.columns:
        df["state"] = "Ceará"

    if "scrape_date" not in df.columns:
        df["scrape_date"] = None

    if "scrape_datetime" not in df.columns:
        df["scrape_datetime"] = None

    # Clean dates
    df["scrape_date"] = pd.to_datetime(df["scrape_date"], errors="coerce")

    # Clean numeric columns
    if "price_num" not in df.columns:
        df["price_num"] = df["price"].apply(parse_brl)
    else:
        df["price_num"] = pd.to_numeric(df["price_num"], errors="coerce")

    if "area_num" not in df.columns:
        df["area_num"] = df["area"].apply(parse_first_number)
    else:
        df["area_num"] = pd.to_numeric(df["area_num"], errors="coerce")

    if "bedrooms" in df.columns:
        df["bedrooms_clean"] = df["bedrooms"].apply(parse_first_number)
    elif "bedrooms_num" in df.columns:
        df["bedrooms_clean"] = pd.to_numeric(df["bedrooms_num"], errors="coerce")
    else:
        df["bedrooms_clean"] = None

    if "bathrooms" in df.columns:
        df["bathrooms_clean"] = df["bathrooms"].apply(parse_first_number)
    elif "bathrooms_num" in df.columns:
        df["bathrooms_clean"] = pd.to_numeric(df["bathrooms_num"], errors="coerce")
    else:
        df["bathrooms_clean"] = None

    if "parking" in df.columns:
        df["parking_clean"] = df["parking"].apply(parse_first_number)
    elif "parking_num" in df.columns:
        df["parking_clean"] = pd.to_numeric(df["parking_num"], errors="coerce")
    else:
        df["parking_clean"] = None

    if "page_number" in df.columns:
        df["page_number_clean"] = df["page_number"].apply(parse_first_number)
    else:
        df["page_number_clean"] = None

    # Price per square meter
    df["price_per_m2"] = df["price_num"] / df["area_num"]

    # Basic validity filters
    df = df.dropna(subset=["price_num", "area_num", "price_per_m2"])
    df = df[df["price_num"] > 0]
    df = df[df["area_num"] > 0]
    df = df[df["price_per_m2"] > 0]

    # Remove unrealistic values
    df = df[df["area_num"] <= 2000]
    df = df[df["price_num"] <= 30_000_000]
    df = df[df["price_per_m2"] <= 100_000]

    # Remove listings with unrealistic bedroom or bathroom counts
    # Keeps listings where bedroom/bathroom info is missing.
    df = df[
        (df["bedrooms_clean"].isna() | (df["bedrooms_clean"] <= 10)) &
        (df["bathrooms_clean"].isna() | (df["bathrooms_clean"] <= 10))
    ]

    return df


# --------------------------------------------------
# Load data
# --------------------------------------------------
df = load_data()

if df.empty:
    st.error("No valid data found after cleaning. Check your CSV file.")
    st.stop()

# --------------------------------------------------
# Sidebar: navigation first
# --------------------------------------------------
st.sidebar.title("Monitor imobiliário")
st.sidebar.caption("Vendas")

st.sidebar.divider()
st.sidebar.header("Sections")

section = st.sidebar.radio(
    "Choose a section",
    [
        "Overview",
        "Property estimator",
        "Price distribution",
        "Price/m² distribution",
        "Price/m² x Area",
        "Price/m² x Bedrooms",
        "Price/m² x Bathrooms",
        "Price/m² x Parking",
        "Median price over time",
        "City comparison",
        "Data table",
    ],
)

st.sidebar.divider()
st.sidebar.header("Filters")

# City filter
city_options = sorted(df["city"].dropna().unique())

selected_cities = st.sidebar.multiselect(
    "City",
    options=city_options,
    default=city_options,
)

if not selected_cities:
    st.warning("Please select at least one city.")
    st.stop()

# Filter by selected cities first, so sliders adapt to selected cities
df_city = df[df["city"].isin(selected_cities)]

if df_city.empty:
    st.warning("No data available for the selected cities.")
    st.stop()

# Price filter
min_price = int(df_city["price_num"].min())
max_price = int(df_city["price_num"].max())

price_range = st.sidebar.slider(
    "Price range R$",
    min_value=min_price,
    max_value=max_price,
    value=(min_price, max_price),
    step=10000,
)

# Area filter
min_area = int(df_city["area_num"].min())
max_area = int(df_city["area_num"].max())

area_range = st.sidebar.slider(
    "Area range m²",
    min_value=min_area,
    max_value=max_area,
    value=(min_area, max_area),
    step=5,
)

# Price/m² filter
max_price_m2 = int(df_city["price_per_m2"].quantile(0.99))

price_m2_range = st.sidebar.slider(
    "Price per m² range R$",
    min_value=0,
    max_value=max_price_m2,
    value=(0, max_price_m2),
    step=500,
)

# Date filter
valid_dates = df_city["scrape_date"].dropna()

if not valid_dates.empty:
    min_date = valid_dates.min().date()
    max_date = valid_dates.max().date()

    date_range = st.sidebar.date_input(
        "Scrape date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
else:
    date_range = None

# Apply filters
filtered = df_city[
    (df_city["price_num"] >= price_range[0]) &
    (df_city["price_num"] <= price_range[1]) &
    (df_city["area_num"] >= area_range[0]) &
    (df_city["area_num"] <= area_range[1]) &
    (df_city["price_per_m2"] >= price_m2_range[0]) &
    (df_city["price_per_m2"] <= price_m2_range[1])
]

if date_range and len(date_range) == 2:
    start_date = pd.to_datetime(date_range[0])
    end_date = pd.to_datetime(date_range[1])

    filtered = filtered[
        (filtered["scrape_date"] >= start_date) &
        (filtered["scrape_date"] <= end_date)
    ]

if filtered.empty:
    st.warning("No listings match the selected filters.")
    st.stop()

# --------------------------------------------------
# Summary data
# --------------------------------------------------
city_summary = (
    filtered
    .groupby("city")
    .agg(
        listings=("price_num", "count"),
        median_price=("price_num", "median"),
        median_area=("area_num", "median"),
        median_price_m2=("price_per_m2", "median"),
    )
    .sort_values("median_price_m2", ascending=False)
    .reset_index()
)

# --------------------------------------------------
# Interactive Plotly chart helpers
# --------------------------------------------------
def plot_histogram_by_city(data, column, title, xlabel, bins=40):
    fig = px.histogram(
        data,
        x=column,
        color="city",
        nbins=bins,
        title=title,
        labels={
            column: xlabel,
            "city": "City",
        },
        opacity=0.65,
    )

    fig.update_layout(
        bargap=0.05,
        hovermode="x unified",
        height=560,
        legend_title_text="City",
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_scatter(data, x_col, y_col, title, xlabel, ylabel):
    clean_data = data.dropna(subset=[x_col, y_col, "city"])

    if clean_data.empty:
        st.info("No data available for this chart.")
        return

    hover_cols = [
        col for col in [
            "city",
            "state",
            "title",
            "price",
            "area",
            "bedrooms",
            "bathrooms",
            "parking",
            "neighborhood_city",
            "street",
            "price_num",
            "area_num",
            "price_per_m2",
        ]
        if col in clean_data.columns
    ]

    fig = px.scatter(
        clean_data,
        x=x_col,
        y=y_col,
        color="city",
        title=title,
        labels={
            x_col: xlabel,
            y_col: ylabel,
            "city": "City",
        },
        hover_data=hover_cols,
        opacity=0.65,
    )

    fig.update_layout(
        height=560,
        hovermode="closest",
        legend_title_text="City",
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_median_bar_by_city(data, category_col, value_col, title, xlabel, ylabel):
    clean_data = data.dropna(subset=[category_col, value_col, "city"])

    if clean_data.empty:
        st.info("No data available for this chart.")
        return

    grouped = (
        clean_data
        .groupby(["city", category_col], as_index=False)
        .agg(
            median_value=(value_col, "median"),
            listings=(value_col, "count"),
        )
    )

    fig = px.bar(
        grouped,
        x=category_col,
        y="median_value",
        color="city",
        barmode="group",
        title=title,
        labels={
            category_col: xlabel,
            "median_value": ylabel,
            "city": "City",
            "listings": "Listings",
        },
        hover_data=["listings"],
    )

    fig.update_layout(
        height=560,
        legend_title_text="City",
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_city_bar(data, x_col, y_col, title, xlabel, ylabel):
    fig = px.bar(
        data,
        x=x_col,
        y=y_col,
        title=title,
        labels={
            x_col: xlabel,
            y_col: ylabel,
        },
        hover_data=data.columns,
    )

    fig.update_layout(
        height=500,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_time_series(data, y_col, title, ylabel):
    fig = px.line(
        data,
        x="scrape_date",
        y=y_col,
        color="city",
        markers=True,
        title=title,
        labels={
            "scrape_date": "Scrape date",
            y_col: ylabel,
            "city": "City",
        },
        hover_data=["listings"],
    )

    fig.update_layout(
        height=560,
        hovermode="x unified",
        legend_title_text="City",
    )

    st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------
# Header
# --------------------------------------------------
st.markdown(
    """
    <div class="main-title">Monitor imobiliáio de capitais Brasileiras</div>
    <div class="subtitle">Venda</div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------
# Sections
# --------------------------------------------------
if section == "Overview":
    st.subheader("Overview")

    metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)

    metrics = [
        ("Listings", f"{len(filtered):,}"),
        ("Cities", f"{filtered['city'].nunique():,}"),
        ("Median price", f"R$ {filtered['price_num'].median():,.0f}"),
        ("Median area", f"{filtered['area_num'].median():,.0f} m²"),
        ("Median R$/m²", f"R$ {filtered['price_per_m2'].median():,.0f}"),
    ]

    for col, (label, value) in zip(
        [metric_col1, metric_col2, metric_col3, metric_col4, metric_col5],
        metrics,
    ):
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    st.subheader("City summary")

    st.dataframe(
        city_summary,
        use_container_width=True,
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Listings by city")
        listings_by_city = city_summary.sort_values("listings", ascending=False)

        plot_city_bar(
            listings_by_city,
            x_col="city",
            y_col="listings",
            title="Number of listings by city",
            xlabel="City",
            ylabel="Listings",
        )

    with col2:
        st.subheader("Median R$/m² by city")
        price_m2_by_city = city_summary.sort_values("median_price_m2", ascending=False)

        plot_city_bar(
            price_m2_by_city,
            x_col="city",
            y_col="median_price_m2",
            title="Median price per m² by city",
            xlabel="City",
            ylabel="Median R$/m²",
        )


elif section == "Property estimator":
    st.subheader("Property Price Estimator")
    st.caption("Estimate a typical listing price using similar scraped VivaReal listings.")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        estimator_city = st.selectbox(
            "City",
            options=sorted(df["city"].dropna().unique()),
        )

    with col2:
        area_input = st.number_input(
            "Area m²",
            min_value=10,
            max_value=2000,
            value=80,
            step=5,
        )

    with col3:
        bedrooms_input = st.number_input(
            "Bedrooms",
            min_value=0,
            max_value=10,
            value=2,
            step=1,
        )

    with col4:
        bathrooms_input = st.number_input(
            "Bathrooms",
            min_value=0,
            max_value=10,
            value=2,
            step=1,
        )

    col5, col6 = st.columns(2)

    with col5:
        parking_input = st.number_input(
            "Parking spaces",
            min_value=0,
            max_value=10,
            value=1,
            step=1,
        )

    with col6:
        use_parking = st.checkbox(
            "Match parking spaces exactly",
            value=False,
        )

    area_tolerance = st.slider(
        "Area tolerance",
        min_value=5,
        max_value=50,
        value=20,
        step=5,
        help="Example: 20 means the app searches listings within ±20% of the area.",
    )

    min_area_match = area_input * (1 - area_tolerance / 100)
    max_area_match = area_input * (1 + area_tolerance / 100)

    similar = df[
        (df["city"] == estimator_city) &
        (df["area_num"] >= min_area_match) &
        (df["area_num"] <= max_area_match) &
        (df["bedrooms_clean"] == bedrooms_input) &
        (df["bathrooms_clean"] == bathrooms_input)
    ].copy()

    if use_parking:
        similar = similar[similar["parking_clean"] == parking_input]

    st.divider()

    if similar.empty:
        st.warning(
            "No similar listings found. Try increasing the area tolerance, "
            "changing bedrooms/bathrooms, or removing exact parking matching."
        )
    else:
        estimated_price = similar["price_num"].median()
        estimated_price_m2 = similar["price_per_m2"].median()
        listing_count = len(similar)

        metric_col1, metric_col2, metric_col3 = st.columns(3)

        estimator_metrics = [
            ("Estimated median price", f"R$ {estimated_price:,.0f}"),
            ("Estimated median R$/m²", f"R$ {estimated_price_m2:,.0f}"),
            ("Similar listings", f"{listing_count:,}"),
        ]

        for col, (label, value) in zip(
            [metric_col1, metric_col2, metric_col3],
            estimator_metrics,
        ):
            with col:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-label">{label}</div>
                        <div class="metric-value">{value}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.caption(
            f"Based on listings in {estimator_city} with area between "
            f"{min_area_match:.0f} m² and {max_area_match:.0f} m², "
            f"{bedrooms_input} bedrooms and {bathrooms_input} bathrooms."
        )

        fig = px.scatter(
            similar,
            x="area_num",
            y="price_num",
            color="city",
            title="Similar listings: price vs area",
            labels={
                "area_num": "Area m²",
                "price_num": "Price R$",
                "city": "City",
            },
            hover_data=[
                col for col in [
                    "title",
                    "price",
                    "area",
                    "bedrooms",
                    "bathrooms",
                    "parking",
                    "neighborhood_city",
                    "street",
                    "price_per_m2",
                ]
                if col in similar.columns
            ],
        )

        fig.update_layout(
            height=520,
            hovermode="closest",
        )

        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Similar listings used for estimate")

        display_cols = [
            "city",
            "price",
            "area",
            "bedrooms",
            "bathrooms",
            "parking",
            "neighborhood_city",
            "street",
            "title",
            "price_num",
            "area_num",
            "price_per_m2",
        ]

        display_cols = [col for col in display_cols if col in similar.columns]

        st.dataframe(
            similar.sort_values("price_per_m2", ascending=False)[display_cols],
            use_container_width=True,
        )


elif section == "Price distribution":
    st.subheader("Price Distribution")

    plot_histogram_by_city(
        filtered,
        column="price_num",
        title="Price Distribution by City",
        xlabel="Price R$",
        bins=40,
    )


elif section == "Price/m² distribution":
    st.subheader("Price/m² Distribution")

    plot_histogram_by_city(
        filtered,
        column="price_per_m2",
        title="Price per m² Distribution by City",
        xlabel="Price per m² R$",
        bins=40,
    )


elif section == "Price/m² x Area":
    st.subheader("Price/m² x Area")

    plot_scatter(
        filtered,
        x_col="area_num",
        y_col="price_per_m2",
        title="Price per m² x Area by City",
        xlabel="Area m²",
        ylabel="Price per m² R$",
    )


elif section == "Price/m² x Bedrooms":
    st.subheader("Price/m² x Bedrooms")

    plot_median_bar_by_city(
        filtered,
        category_col="bedrooms_clean",
        value_col="price_per_m2",
        title="Median Price per m² by Bedrooms and City",
        xlabel="Bedrooms",
        ylabel="Median price per m² R$",
    )

    plot_scatter(
        filtered,
        x_col="bedrooms_clean",
        y_col="price_per_m2",
        title="Price per m² x Bedrooms by City",
        xlabel="Bedrooms",
        ylabel="Price per m² R$",
    )


elif section == "Price/m² x Bathrooms":
    st.subheader("Price/m² x Bathrooms")

    plot_median_bar_by_city(
        filtered,
        category_col="bathrooms_clean",
        value_col="price_per_m2",
        title="Median Price per m² by Bathrooms and City",
        xlabel="Bathrooms",
        ylabel="Median price per m² R$",
    )

    plot_scatter(
        filtered,
        x_col="bathrooms_clean",
        y_col="price_per_m2",
        title="Price per m² x Bathrooms by City",
        xlabel="Bathrooms",
        ylabel="Price per m² R$",
    )


elif section == "Price/m² x Parking":
    st.subheader("Price/m² x Parking")

    plot_median_bar_by_city(
        filtered,
        category_col="parking_clean",
        value_col="price_per_m2",
        title="Median Price per m² by Parking Spaces and City",
        xlabel="Parking spaces",
        ylabel="Median price per m² R$",
    )

    plot_scatter(
        filtered,
        x_col="parking_clean",
        y_col="price_per_m2",
        title="Price per m² x Parking Spaces by City",
        xlabel="Parking spaces",
        ylabel="Price per m² R$",
    )


elif section == "Median price over time":
    st.subheader("Median Price Over Time")

    time_df = filtered.copy()
    time_df = time_df.dropna(subset=["scrape_date", "price_num", "price_per_m2", "city"])

    if time_df.empty:
        st.info("No time-series data available. Run the updated scraper first.")
    else:
        median_price_time = (
            time_df
            .groupby(["scrape_date", "city"])
            .agg(
                median_price=("price_num", "median"),
                median_price_m2=("price_per_m2", "median"),
                listings=("price_num", "count"),
            )
            .reset_index()
            .sort_values(["scrape_date", "city"])
        )

        plot_time_series(
            median_price_time,
            y_col="median_price",
            title="Median Property Price Over Time by City",
            ylabel="Median price R$",
        )

        st.subheader("Median Price/m² Over Time")

        plot_time_series(
            median_price_time,
            y_col="median_price_m2",
            title="Median Price per m² Over Time by City",
            ylabel="Median R$/m²",
        )

        st.dataframe(
            median_price_time,
            use_container_width=True,
        )


elif section == "City comparison":
    st.subheader("City Comparison")

    city_metric = st.selectbox(
        "Metric to compare",
        options=[
            "median_price",
            "median_price_m2",
            "median_area",
            "listings",
        ],
        format_func=lambda x: {
            "median_price": "Median price",
            "median_price_m2": "Median R$/m²",
            "median_area": "Median area",
            "listings": "Number of listings",
        }[x],
    )

    comparison = city_summary.sort_values(city_metric, ascending=False)

    plot_city_bar(
        comparison,
        x_col="city",
        y_col=city_metric,
        title="City Comparison",
        xlabel="City",
        ylabel=city_metric.replace("_", " ").title(),
    )

    st.dataframe(
        comparison,
        use_container_width=True,
    )


elif section == "Data table":
    st.subheader("Cleaned data")

    display_cols = [
        "scrape_date",
        "scrape_datetime",
        "city",
        "state",
        "page_number",
        "price",
        "area",
        "bedrooms",
        "bathrooms",
        "parking",
        "neighborhood_city",
        "street",
        "title",
        "price_num",
        "area_num",
        "bedrooms_clean",
        "bathrooms_clean",
        "parking_clean",
        "price_per_m2",
    ]

    display_cols = [col for col in display_cols if col in filtered.columns]

    table_display = (
        filtered
        .sort_values(["city", "price_per_m2"], ascending=[True, False])
        [display_cols]
    )

    st.dataframe(
        table_display,
        use_container_width=True,
    )

    csv_data = filtered.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download filtered cleaned data",
        data=csv_data,
        file_name="vivareal_filtered_cleaned.csv",
        mime="text/csv",
    )
