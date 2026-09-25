from datetime import date, datetime
from icalendar import Calendar
import pandas as pd
import requests
import streamlit as st
import zoneinfo

# Configurazione della pagina
st.set_page_config(page_title="La mia agenda", page_icon="📅", layout="wide")

# Stile CSS per compattare gli spazi tra le card
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');

    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif !important;
    }

    .block-container {
        padding-top: 1.0rem !important;
        padding-bottom: 1.0rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    /* Riduciamo lo spazio verticale generale tra gli elementi di Streamlit */
    div.stVerticalBlock > div {
        gap: 0.2rem !important;
    }

    /* Titolo principale */
    h1.custom-title {
        color: #1b5e20 !important;
        font-size: 1.5rem !important;
        font-weight: 900 !important;
        margin-top: 0px !important;
        margin-bottom: 0px !important;
        letter-spacing: -0.5px;
    }

    /* Stile checkbox ravvicinata e compatta */
    [data-testid="stCheckbox"] {
        padding: 2px 8px 4px 8px !important;
        border-bottom-left-radius: 8px;
        border-bottom-right-radius: 8px;
        margin-top: -6px !important;
        margin-bottom: 6px !important; /* Riduce lo spazio vuoto sotto ogni card */
        border-left: 1px solid rgba(0,0,0,0.08);
        border-right: 1px solid rgba(0,0,0,0.08);
        border-bottom: 1px solid rgba(0,0,0,0.08);
    }
    
    [data-testid="stCheckbox"] label {
        font-size: 0.7rem !important;
        font-weight: 700 !important;
        color: #2c3e50 !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Intestazione visibile
st.markdown('<h1 class="custom-title">La mia agenda</h1>', unsafe_allow_html=True)
st.caption("Sincronizzato in tempo reale (Fuso orario: Roma)")

# Recupero link iCloud sicuro
if "URL_ICLOUD" in st.secrets:
    URL_CALENDARIO = st.secrets["URL_ICLOUD"]
else:
    st.error("❌ Attenzione: il link iCloud non è configurato nei Secrets di Streamlit (`URL_ICLOUD`).")
    st.stop()

# Funzioni di utilità
def get_oggi_italia():
    try:
        roma_tz = zoneinfo.ZoneInfo("Europe/Rome")
        return datetime.now(roma_tz).date()
    except Exception:
        return date.today()

def formatta_data_italiano(dt_val):
    if isinstance(dt_val, datetime):
        d = dt_val.date()
        ora_str = dt_val.strftime("alle %H:%M")
    else:
        d = dt_val
        ora_str = ""
    
    if isinstance(d, date):
        giorni = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
        mesi = ["", "gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
        nome_giorno = giorni[d.weekday()]
        nome_mese = mesi[d.month]
        return f"{nome_giorno} {d.day} {nome_mese} {d.year} {ora_str}".strip()
    return "Non definita"

def analizza_dettagli_evento(titolo, descrizione, categoria_ical):
    testo_globale = f"{titolo} {descrizione} {categoria_ical}".lower()
    if any(k in testo_globale for k in ["lavoro", "ufficio", "meeting", "call", "client", "riunione", "lavorare"]):
        categoria = "Lavoro"
    elif any(k in testo_globale for k in ["casa", "famiglia", "spesa", "medico", "commissione", "relax"]):
        categoria = "Casa"
    else:
        categoria = "Generale"

    if any(k in testo_globale for k in ["priorità alta", "[alta]", "urgente", "!"]):
        priorita = "Alta"
    else:
        priorita = "Normale"
    return categoria, priorita

@st.cache_data(ttl=600)
def carica_eventi(url):
    try:
        risposta = requests.get(url)
        risposta.raise_for_status()
        cal = Calendar.from_ical(risposta.content)

        eventi = []
        for componente in cal.walk():
            if componente.name == "VEVENT":
                titolo = str(componente.get("summary", "Senza titolo"))
                luogo = str(componente.get("location", ""))
                descrizione = str(componente.get("description", ""))
                
                cat_raw = componente.get("categories", "")
                cat_str = cat_raw.to_ical().decode("utf-8") if hasattr(cat_raw, "to_ical") else str(cat_raw)
                
                inizio = componente.get("dtstart")
                if inizio:
                    dt_val = inizio.dt
                    data_obj = dt_val.date() if isinstance(dt_val, datetime) else dt_val
                    data_str_ita = formatta_data_italiano(dt_val)
                else:
                    data_obj = None
                    data_str_ita = "Data non definita"

                categoria, priorita = analizza_dettagli_evento(titolo, descrizione, cat_str)
                native_uid = str(componente.get("uid", ""))
                uid = native_uid if native_uid else f"{titolo}_{str(data_obj)}_{str(inizio)}"

                eventi.append({
                    "UID": uid, "Titolo": titolo, "DataInizio": data_obj,
                    "Inizio": data_str_ita, "Luogo": luogo, "Descrizione": descrizione,
                    "Categoria": categoria, "Priorità": priorita
                })

        df = pd.DataFrame(eventi)
        if not df.empty:
            df = df.sort_values(by="DataInizio", na_position="last").reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"❌ Errore durante il caricamento: {e}")
        return pd.DataFrame()

# --- RENDERIZZAZIONE SINGOLA CARD COMPATTA ---
def renderizza_singola_card(item, idx, chiave_prefisso, colore_sfondo):
    uid = item["UID"]
    
    if "completati" not in st.session_state:
        st.session_state.completati = set()
        
    is_completato = uid in st.session_state.completati
    stile_opacita = "opacity: 0.4; text-decoration: line-through;" if is_completato else ""

    badge_cat = '<span style="background-color: #cfe2ff; color: #084298; padding: 1px 5px; border-radius: 3px; font-size: 0.65rem; font-weight: 700;">Lavoro</span>' if item["Categoria"] == "Lavoro" else ('<span style="background-color: #d1e7dd; color: #0f5132; padding: 1px 5px; border-radius: 3px; font-size: 0.65rem; font-weight: 700;">Casa</span>' if item["Categoria"] == "Casa" else "")
    badge_pri = '<span style="background-color: #f8d7da; color: #842029; padding: 1px 5px; border-radius: 3px; font-size: 0.65rem; font-weight: 700; margin-left: 4px;">⚠️ Alta</span>' if item["Priorità"] == "Alta" else ""
    luogo_str = f"📍 {item['Luogo']}" if item["Luogo"] else ""

    # Parte superiore della card (più compatta)
    st.markdown(
        f"""
        <div style="background-color: {colore_sfondo}; border-top-left-radius: 8px; border-top-right-radius: 8px; padding: 8px 10px; border-left: 1px solid rgba(0,0,0,0.08); border-right: 1px solid rgba(0,0,0,0.08); border-top: 1px solid rgba(0,0,0,0.08); {stile_opacita}">
            <div style="font-size: 0.9rem; font-weight: 800; color: #2c3e50; line-height: 1.2; margin-bottom: 2px;">{item["Titolo"]}</div>
            <div style="font-size: 0.7rem; font-weight: 600; color: #444; margin-bottom: 2px;">🕒 {item["Inizio"]}</div>
            <div style="font-size: 0.65rem; color: #666; margin-bottom: 4px;">{luogo_str}</div>
            <div>{badge_cat} {badge_pri}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Checkbox agganciata con lo stesso sfondo
    st.markdown(f'<div style="background-color: {colore_sfondo};">', unsafe_allow_html=True)
    nuovo_stato = st.checkbox("Completato", value=is_completato, key=f"chk_{chiave_prefisso}_{idx}_{abs(hash(uid))}")
    st.markdown('</div>', unsafe_allow_html=True)

    if nuovo_stato and uid not in st.session_state.completati:
        st.session_state.completati.add(uid)
        st.rerun()
    elif not nuovo_stato and uid in st.session_state.completati:
        st.session_state.completati.remove(uid)
        st.rerun()

def renderizza_lista_card(df_eventi, chiave_prefisso):
    colori_pastello = ["#fdf2e9", "#e8f8f5", "#ebf5fb", "#f4ecf7", "#fef9e7", "#f2f4f4"]
    lista_eventi = df_eventi.to_dict('records')

    for i, item in enumerate(lista_eventi):
        renderizza_singola_card(item, i, chiave_prefisso, colori_pastello[i % len(colori_pastello)])

# --- CARICAMENTO DATI ---
with st.spinner("Sincronizzazione in corso..."):
    df = carica_eventi(URL_CALENDARIO)

if not df.empty:
    oggi = get_oggi_italia()
    if "completati" not in st.session_state:
        st.session_state.completati = set()

    eventi_oggi = df[df["DataInizio"].apply(lambda x: x == oggi if pd.notna(x) else False)]
    eventi_futuri = df[df["DataInizio"].apply(lambda x: x >= oggi if pd.notna(x) else False)]

    # 1. SOMMARIO COMPATTO
    st.markdown(f"📌 **Oggi:** `{len(eventi_oggi)}` &nbsp;|&nbsp; 🚀 **Futuri:** `{len(eventi_futuri)}` &nbsp;|&nbsp; 📅 **Totali:** `{len(df)}`")
    st.markdown('<hr style="margin: 0.2rem 0; border: none; border-top: 1px solid rgba(0,0,0,0.1);">', unsafe_allow_html=True)

    # 2. IMPEGNI DI OGGI
    if not eventi_oggi.empty:
        st.subheader("🔔 Impegni di Oggi")
        renderizza_lista_card(eventi_oggi, "oggi")
        st.markdown('<hr style="margin: 0.2rem 0; border: none; border-top: 1px solid rgba(0,0,0,0.1);">', unsafe_allow_html=True)

    # 3. EVENTI PER MESE
    st.subheader("🗓️ Appuntamenti per Mese")
    df_con_date = df.dropna(subset=["DataInizio"]).copy()
    
    if not df_con_date.empty:
        df_con_date["MeseAnno"] = df_con_date["DataInizio"].apply(lambda x: x.strftime("%Y-%m"))
        mesi_disponibili = sorted(df_con_date["MeseAnno"].unique())
        mese_corrente_str = oggi.strftime("%Y-%m")
        default_index = mesi_disponibili.index(mese_corrente_str) if mese_corrente_str in mesi_disponibili else 0

        col_filtro_m, _ = st.columns([2, 2])
        with col_filtro_m:
            mese_scelto = st.selectbox("Seleziona Mese:", mesi_disponibili, index=default_index,
                                       format_func=lambda x: datetime.strptime(x, "%Y-%m").strftime("%B %Y").capitalize())

        anno_s, mese_s = map(int, mese_scelto.split("-"))
        eventi_mese = df[df["DataInizio"].apply(lambda x: (x.year == anno_s and x.month == mese_s if pd.notna(x) else False))].sort_values(by="DataInizio", ascending=True)

        if not eventi_mese.empty:
            renderizza_lista_card(eventi_mese, "mese")
        else:
            st.info("Nessun evento in programma per il mese selezionato.")
    else:
        st.info("Nessuna data valida trovata nel calendario.")

    st.markdown('<hr style="margin: 0.2rem 0; border: none; border-top: 1px solid rgba(0,0,0,0.1);">', unsafe_allow_html=True)

    # 4. RICERCA E FILTRI
    with st.expander("🔍 Altri filtri e ricerca avanzata"):
        c1, c2, c3 = st.columns(3)
        with c1:
            ricerca = st.text_input("Cerca parola:")
        with c2:
            filtro_categoria = st.selectbox("Categoria:", ["Tutte", "Casa", "Lavoro", "Generale"])
        with c3:
            periodo = st.selectbox("Periodo:", ["Solo Futuri", "Tutti", "Solo Passati"])

        min_date = df["DataInizio"].min() if not pd.isna(df["DataInizio"].min()) else oggi
        max_date = df["DataInizio"].max() if not pd.isna(df["DataInizio"].max()) else oggi

        intervallo_date = st.date_input("Intervallo:", value=(min_date, max_date))

        df_f = df.copy()
        if ricerca:
            df_f = df_f[df_f["Titolo"].str.contains(ricerca, case=False, na=False)]
        if filtro_categoria != "Tutte":
            df_f = df_f[df_f["Categoria"] == filtro_categoria]
        if periodo == "Solo Futuri":
            df_f = df_f[df_f["DataInizio"].apply(lambda x: x >= oggi if pd.notna(x) else False)]
        elif periodo == "Solo Passati":
            df_f = df_f[df_f["DataInizio"].apply(lambda x: x < oggi if pd.notna(x) else False)]
        
        if isinstance(intervallo_date, tuple) and len(intervallo_date) ==2:
            df_f = df_f[df_f["DataInizio"].apply(lambda x: (intervallo_date[0] <= x <= intervallo_date[1]) if pd.notna(x) else False)]

        df_f["Completato"] = df_f["UID"].apply(lambda x: "✅" if x in st.session_state.completati else "❌")
        
        st.dataframe(df_f[["Titolo", "Inizio", "Categoria", "Priorità", "Completato", "Luogo"]], use_container_width=True)

else:
    st.warning("Nessun evento trovato o errore di connessione.")
