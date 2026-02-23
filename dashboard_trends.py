import streamlit as st
import pandas as pd
import altair as alt
import os

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Appie Trends Dashboard",
    page_icon="🍰",
    layout="wide"
)

# --- CONSTANTS ---
CSV_FILE = "laatste_kans_trends.csv"

# --- DATA LOADING ---
@st.cache_data(ttl="10m")
def load_data():
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(CSV_FILE)
        
        # Convert timestamp
        if 'fetch_timestamp' in df.columns:
            df['fetch_timestamp'] = pd.to_datetime(df['fetch_timestamp'])
        
        # Ensure numeric columns
        cols = ['priceWas', 'priceNow', 'markdownPercentage', 'stock']
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

df = load_data()

# --- TITLE & SIDEBAR ---
st.title("🍰 Appie 'Laatste Kans' Trends")
st.markdown("Inzichten uit de verzamelde `laatste_kans_trends.csv` data.")

if df.empty:
    st.warning("Nog geen data beschikbaar. Draai `ah_sniper.py` om data te verzamelen.")
    st.stop()

# Sidebar Filters
st.sidebar.header("Filters")

# Date Filter
if 'fetch_timestamp' in df.columns and not df['fetch_timestamp'].isnull().all():
    min_date = df['fetch_timestamp'].min().date()
    max_date = df['fetch_timestamp'].max().date()
    
    if min_date == max_date:
        st.sidebar.info(f"Data beschikbaar voor: {min_date}")
        date_range = (min_date, max_date)
    else:
        date_range = st.sidebar.date_input("Datum Bereik", [min_date, max_date])
else:
    st.sidebar.warning("Geen datum informatie beschikbaar.")
    date_range = None

# Category Filter
if 'categoryTitle' in df.columns:
    categories = sorted(df['categoryTitle'].dropna().unique())
    selected_categories = st.sidebar.multiselect("Selecteer Categorieën", categories, default=categories[:5])
else:
    categories = []
    selected_categories = []

# Filter Data
if date_range and len(date_range) == 2:
    start_date = pd.Timestamp(date_range[0])
    end_date = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1, seconds=-1) # End of day
    
    mask = (df['fetch_timestamp'] >= start_date) & (df['fetch_timestamp'] <= end_date)
    if 'categoryTitle' in df.columns:
        mask &= (df['categoryTitle'].isin(selected_categories if selected_categories else categories))
    
    df_filtered = df[mask]
else:
    df_filtered = df

# --- KPIS ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Totaal Items Gespot", len(df_filtered))
with col2:
    if 'markdownPercentage' in df_filtered.columns:
        avg_discount = df_filtered['markdownPercentage'].mean()
        st.metric("Gemiddelde Korting", f"{avg_discount:.1f}%")
with col3:
    if 'stock' in df_filtered.columns:
        total_stock = df_filtered['stock'].sum()
        st.metric("Totale Voorraad (Gesommeerd)", int(total_stock) if pd.notnull(total_stock) else 0)
with col4:
    if 'fetch_timestamp' in df.columns:
        latest_update = df['fetch_timestamp'].max()
        st.metric("Laatste Update", latest_update.strftime("%d-%m %H:%M"))

# --- VISUALS ---

# 1. Price Comparison Scatter
st.subheader("💰 Prijs Analyse: Was vs. Nu")
if not df_filtered.empty:
    chart_scatter = alt.Chart(df_filtered).mark_circle(size=60).encode(
        x=alt.X('priceWas', title='Oude Prijs (€)'),
        y=alt.Y('priceNow', title='Nieuwe Prijs (€)'),
        color='categoryTitle',
        tooltip=['title', 'priceWas', 'priceNow', 'markdownPercentage', 'stock', 'fetch_timestamp']
    ).interactive()
    st.altair_chart(chart_scatter, use_container_width=True)

# 2. Category Distribution
st.subheader("📊 Aantal Items per Categorie")
if not df_filtered.empty:
    chart_bar = alt.Chart(df_filtered).mark_bar().encode(
        x=alt.X('categoryTitle', sort='-y', title='Categorie'),
        y=alt.Y('count()', title='Aantal Items'),
        color='categoryTitle'
    )
    st.altair_chart(chart_bar, use_container_width=True)

# 3. Discount Distribution
st.subheader("🏷️ Kortingsverdeling")
if not df_filtered.empty:
    chart_hist = alt.Chart(df_filtered).mark_bar().encode(
        x=alt.X('markdownPercentage', bin=True, title='Kortingspercentage'),
        y=alt.Y('count()', title='Aantal')
    )
    st.altair_chart(chart_hist, use_container_width=True)

# 4. Timeline
st.subheader("📅 Items over Tijd")
if not df_filtered.empty and 'fetch_timestamp' in df_filtered.columns:
    # Group by hour to see trend
    df_time = df_filtered.copy()
    df_time['hour'] = df_time['fetch_timestamp'].dt.floor('h')
    chart_line = alt.Chart(df_time).mark_line(point=True).encode(
        x=alt.X('hour', title='Tijd'),
        y=alt.Y('count()', title='Aantal Items Gevonden'),
        tooltip=['hour', 'count()']
    ).interactive()
    st.altair_chart(chart_line, use_container_width=True)

# --- RAW DATA ---
st.subheader("🔍 Ruwe Data")
if 'fetch_timestamp' in df_filtered.columns:
    st.dataframe(df_filtered.sort_values('fetch_timestamp', ascending=False))
else:
    st.dataframe(df_filtered)
