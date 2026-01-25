import streamlit as st
import pandas as pd
import requests
import uuid
import os

# --- PAGINA CONFIGURATIE ---
st.set_page_config(page_title="Appie Koopjes Sniper", page_icon="🛒", layout="wide")

# --- AH API HELPERS ---
def get_ah_token():
    headers = {"User-Agent": "Appie/9.28", "x-application": "AHWEBSHOP"}
    res = requests.post("https://api.ah.nl/mobile-auth/v1/auth/token/anonymous", 
                         json={"clientId": "appie-ios"}, headers=headers)
    return res.json().get('access_token')

def get_live_bargains(store_id):
    token = get_ah_token()
    headers = {"Authorization": f"Bearer {token}", "x-application": "AHWEBSHOP"}
    query = """
    query GetBargains($storeId: String!) {
      bargainItems(storeId: $storeId) {
        categoryTitle
        product { title brand images { url width } }
        bargainPrice { priceNow priceWas }
        markdown { markdownPercentage }
      }
    }
    """
    res = requests.post("https://api.ah.nl/graphql", 
                         json={'query': query, 'variables': {'storeId': str(store_id)}}, 
                         headers=headers)
    return res.json().get('data', {}).get('bargainItems', [])

# --- UI ONTWERP ---
st.title("🛒 Appie Koopjes Sniper")
st.markdown("Ontdek de beste 'Laatste Kans' deals van jouw Albert Heijn.")

# Sidebar: Store Selector
with st.sidebar:
    st.header("Instellingen")
    # Voor nu een paar bekende, maar je kunt dit uitbreiden
    stores = {"Woenselse Markt (1558)": "1558", "Eindhoven XL (1177)": "1177", "Amsterdam Damrak (1166)": "1166"}
    selected_store_name = st.selectbox("Kies een winkel:", list(stores.keys()))
    STORE_ID = stores[selected_store_name]
    
    st.info("De robot op GitHub verzamelt momenteel alleen data voor de Woenselse Markt.")

# Live Data ophalen
items = get_live_bargains(STORE_ID)

if items:
    df = pd.json_normalize(items)
    
    # 70% SECTIE
    st.subheader("🔥 70% Korting Knallers")
    snipers = df[df['markdown.markdownPercentage'] == 70]
    
    if not snipers.empty:
        # Maak kolommen voor de 'kaarten'
        cols = st.columns(4)
        for i, (idx, row) in enumerate(snipers.iterrows()):
            with cols[i % 4]:
                # Haal het plaatje op (meestal de eerste in de lijst)
                img_url = row['product.images'][0]['url'] if row['product.images'] else ""
                st.image(img_url, use_container_width=True)
                st.write(f"**{row['product.title']}**")
                st.write(f"~~€{row['bargainPrice.priceWas']}~~ → **€{row['bargainPrice.priceNow']}**")
                st.caption(f"Categorie: {row['categoryTitle']}")
    else:
        st.write("Geen 70% deals op dit moment.")

    st.divider()

    # OVERZICHTSTABEL
    st.subheader("📦 Alle huidige aanbiedingen")
    # Opschonen voor de tabel
    display_df = df[['categoryTitle', 'product.title', 'bargainPrice.priceWas', 'bargainPrice.priceNow', 'markdown.markdownPercentage']]
    st.dataframe(display_df, use_container_width=True)

else:
    st.error("Geen data gevonden voor deze winkel. De bak is waarschijnlijk leeg!")

# Historie Sectie (Data Science!)
if os.path.exists("koopjes_historie.csv"):
    st.divider()
    st.subheader("📈 Historische Patronen (Data Science)")
    hist_df = pd.read_csv("koopjes_historie.csv")
    st.line_chart(hist_df.groupby('timestamp').size())
    st.write("Aantal gevonden koopjes over de tijd.")

