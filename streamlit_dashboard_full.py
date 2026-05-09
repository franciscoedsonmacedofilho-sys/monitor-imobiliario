#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May  8 11:42:02 2026

@author: franciscomacedo
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
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

st.title("VivaReal Real Estate Dashboard")

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

    return df


df = load_data()

if df.empty:
    st.error("No valid data found after cleaning. Check your CSV file.")
    st.stop()

# --------------------------------------------------
# Sidebar filters
# --------------------------------------------------
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

min_price = int(df_city["price_num"].min())
max_price = int(df_city["price_num"].max())

price_range = st.sidebar.slider(
    "Price range R$",
    min_value=min_price,
    max_value=max_price,
    value=(min_price, max_price),
    step=10000,
)

min_area = int(df_city["area_num"].min())
max_area = int(df_city["area_num"].max())

area_range = st.sidebar.slider(
    "Area range m²",
    min_value=min_area,
    max_value=max_area,
    value=(min_area, max_area),
    step=5,
)

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
# Metrics
# --------------------------------------------------
metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)

metric_col1.metric("Listings", f"{len(filtered):,}")
metric_col2.metric("Cities", f"{filtered['city'].nunique():,}")
metric_col3.metric("Median price", f"R$ {filtered['price_num'].median():,.0f}")
metric_col4.metric("Median area", f"{filtered['area_num'].median():,.0f} m²")
metric_col5.metric("Median R$/m²", f"R$ {filtered['price_per_m2'].median():,.0f}")

st.divider()

# --------------------------------------------------
# City summary table
# --------------------------------------------------
st.subheader("City summary")

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

st.dataframe(
    city_summary,
    use_container_width=True,
)

st.divider()

# --------------------------------------------------
# Plot helpers
# --------------------------------------------------
def format_currency_axis(ax, axis="x"):
    if axis == "x":
        ax.ticklabel_format(style="plain", axis="x")
    else:
        ax.ticklabel_format(style="plain", axis="y")


def plot_histogram(data, column, title, xlabel, bins=40):
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.hist(data[column].dropna(), bins=bins)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Number of listings")
    format_currency_axis(ax, "x")
    st.pyplot(fig)


def plot_histogram_by_city(data, column, title, xlabel, bins=40):
    fig, ax = plt.subplots(figsize=(12, 6))

    for city in sorted(data["city"].dropna().unique()):
        city_data = data[data["city"] == city][column].dropna()
        if not city_data.empty:
            ax.hist(city_data, bins=bins, alpha=0.5, label=city)

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Number of listings")
    ax.legend()
    format_currency_axis(ax, "x")
    st.pyplot(fig)


def plot_scatter(data, x_col, y_col, title, xlabel, ylabel):
    clean_data = data.dropna(subset=[x_col, y_col])

    if clean_data.empty:
        st.info("No data available for this chart.")
        return

    fig, ax = plt.subplots(figsize=(12, 6))

    for city in sorted(clean_data["city"].dropna().unique()):
        city_data = clean_data[clean_data["city"] == city]
        ax.scatter(
            city_data[x_col],
            city_data[y_col],
            alpha=0.6,
            label=city,
        )

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend()
    format_currency_axis(ax, "y")
    st.pyplot(fig)


def plot_median_bar(data, group_col, value_col, title, xlabel, ylabel):
    grouped = (
        data
        .dropna(subset=[group_col, value_col])
        .groupby(group_col)[value_col]
        .median()
        .sort_index()
    )

    if grouped.empty:
        st.info("No data available for this chart.")
        return

    fig, ax = plt.subplots(figsize=(12, 6))
    grouped.plot(kind="bar", ax=ax)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    format_currency_axis(ax, "y")
    st.pyplot(fig)


def plot_median_bar_by_city(data, category_col, value_col, title, xlabel, ylabel):
    clean_data = data.dropna(subset=[category_col, value_col, "city"])

    if clean_data.empty:
        st.info("No data available for this chart.")
        return

    grouped = (
        clean_data
        .groupby(["city", category_col])[value_col]
        .median()
        .reset_index()
    )

    pivot = grouped.pivot(
        index=category_col,
        columns="city",
        values=value_col,
    ).sort_index()

    if pivot.empty:
        st.info("No data available for this chart.")
        return

    fig, ax = plt.subplots(figsize=(12, 6))
    pivot.plot(kind="bar", ax=ax)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    format_currency_axis(ax, "y")
    st.pyplot(fig)


# --------------------------------------------------
# Tabs
# --------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
    [
        "i) Price distribution",
        "ii) Price/m² distribution",
        "iii) Price/m² x Area",
        "iv) Price/m² x Bedrooms",
        "v) Price/m² x Bathrooms",
        "vi) Price/m² x Parking",
        "vii) Median price over time",
        "viii) City comparison",
    ]
)

with tab1:
    st.subheader("i) Price Distribution")

    plot_histogram_by_city(
        filtered,
        column="price_num",
        title="Price Distribution by City",
        xlabel="Price R$",
        bins=40,
    )

with tab2:
    st.subheader("ii) Price/m² Distribution")

    plot_histogram_by_city(
        filtered,
        column="price_per_m2",
        title="Price per m² Distribution by City",
        xlabel="Price per m² R$",
        bins=40,
    )

with tab3:
    st.subheader("iii) Price/m² x Area")

    plot_scatter(
        filtered,
        x_col="area_num",
        y_col="price_per_m2",
        title="Price per m² x Area by City",
        xlabel="Area m²",
        ylabel="Price per m² R$",
    )

with tab4:
    st.subheader("iv) Price/m² x Bedrooms")

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

with tab5:
    st.subheader("v) Price/m² x Bathrooms")

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

with tab6:
    st.subheader("vi) Price/m² x Parking")

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

with tab7:
    st.subheader("vii) Median Price Over Time")

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

        fig, ax = plt.subplots(figsize=(12, 6))

        for city in sorted(median_price_time["city"].dropna().unique()):
            city_data = median_price_time[median_price_time["city"] == city]

            ax.plot(
                city_data["scrape_date"],
                city_data["median_price"],
                marker="o",
                label=city,
            )

        ax.set_title("Median Property Price Over Time by City")
        ax.set_xlabel("Scrape date")
        ax.set_ylabel("Median price R$")
        ax.ticklabel_format(style="plain", axis="y")
        ax.legend()
        plt.xticks(rotation=45)
        st.pyplot(fig)

        st.subheader("Median Price/m² Over Time")

        fig, ax = plt.subplots(figsize=(12, 6))

        for city in sorted(median_price_time["city"].dropna().unique()):
            city_data = median_price_time[median_price_time["city"] == city]

            ax.plot(
                city_data["scrape_date"],
                city_data["median_price_m2"],
                marker="o",
                label=city,
            )

        ax.set_title("Median Price per m² Over Time by City")
        ax.set_xlabel("Scrape date")
        ax.set_ylabel("Median R$/m²")
        ax.ticklabel_format(style="plain", axis="y")
        ax.legend()
        plt.xticks(rotation=45)
        st.pyplot(fig)

        st.dataframe(
            median_price_time,
            use_container_width=True,
        )

with tab8:
    st.subheader("viii) City Comparison")

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

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(comparison["city"], comparison[city_metric])
    ax.set_title("City Comparison")
    ax.set_xlabel("City")
    ax.set_ylabel(city_metric.replace("_", " ").title())

    if city_metric != "listings":
        format_currency_axis(ax, "y")

    st.pyplot(fig)

    st.dataframe(
        comparison,
        use_container_width=True,
    )

# --------------------------------------------------
# Optional data view/download
# --------------------------------------------------
st.divider()

with st.expander("View cleaned data"):
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
