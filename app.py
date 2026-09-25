from datetime import date, datetime
from icalendar import Calendar
import pandas as pd
import requests
import streamlit as st
import zoneinfo

# Configurazione della pagina
st.set_page_config(page_title="La mia agenda", page_icon="📅", layout="wide")

# Stile CSS per griglia fissa a 2 colonne reali, card uniformi e colori pastello/vivaci
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');

    /* Applicazione globale del font Montserrat */
    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif !important;
    }

    /* Gestione degli spazi */
    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    /* Titolo principale responsivo */
    h1.custom-title {
        color: #1b5e20 !important;
        font-size: 2.2rem !important;
        font-weight: 900 !important;
        margin-top: 0px !important;
        padding-top: 0px !important;
        margin-bottom: 0px !important;
        letter-spacing: -0.5px;
        white-space: nowrap;
    }

    @media (max-width: 640px) {
        h1.custom-title {
            font-size: 1.7rem !important;
        }
    }

    /* Card eventi con altezza fissa identica e flexbox */
    .event-card {
        border-radius: 10px;
        padding: 12px;
        height: 150px; 
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-sizing: border-box;
        border: 1px solid rgba(0,0,0,0.06);
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        margin-bottom: 10px;
        overflow: hidden;
    }
    .event-completato {
        opacity: 0.5;
        text-decoration: line-through;
    }

    /* Badge con colori più vivaci */
    .badge-casa {
        background-color: #d1e7dd;
        color: #0f5132;
        padding: 2px 6px;
        border-radius: 6px;
        font-size: 0.65rem;
        font-weight: 700;
    }
    .badge-lavoro {
        background-color: #cfe2ff;
        color: #084298;
        padding: 2px 6px;
        border-radius: 6px;
        font-size: 0.65rem;
        font-weight: 700;
    }
    .badge-priorita {
        background-color: #f8d7da;
        color: #842029;
        padding: 2px 6px;
        border-radius: 6px;
        font-size: 0.65rem;
        font-weight: 700;
    }
    
    /* Riduce lo spazio verticale nei blocchi Streamlit */
    [data-testid="stVerticalBlock"] {
        gap: 0.2rem !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Intestazione
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
                uid = f"{titolo}_{str(data_obj)}"

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

# --- FUNZIONE PER RENDERIZZARE LA GRIGLIA A 2 COLONNE CON CHECKBOX INTEGRATE ---
def renderizza_griglia_card(df_eventi, chiave_prefisso):
    # Palette colori pastello morbidi per lo sfondo delle card
    colori_pastello = [
        "#fdf2e9", "#e8f8f5", "#ebf5fb", "#f4ecf7", "#fef9e7", "#f2f4f4"
    ]

    # Iteriamo a coppie per sfruttare perfettamente le colonne di Streamlit (2 colonne affiancate)
    for i in range(0, len(df_eventi), 2):
        col1, col2 = st.columns(2)
        coppia = [df_eventi.iloc[i], df_eventi.iloc[i+1]] if i+1 < len(df_eventi) else [df_eventi.iloc[i]]
        
        for col_idx, row in enumerate(coppia):
            col_corrente = col1 if col_idx == 0 else col2
            global_idx = i + col_idx
            uid = row["UID"]
            is_completato = uid in st.session_state.completati
            colore_sfondo = colori_pastello[global_idx % len(colori_pastello)]

            badge_cat = '<span class="badge-lavoro">Lavoro</span>' if row["Categoria"] == "Lavoro" else ('<span class="badge-casa">Casa</span>' if row["Categoria"] == "Casa" else "")
            badge_pri = '<span class="badge-priorita">⚠️ Alta</span>' if row["Priorità"] == "Alta" else ""
            classe_card = "event-card event-completato" if is_completato else "event-card"
            luogo_str = f"📍 {row['Luogo']}" if row["Luogo"] else ""

            with col_corrente:
                # Contenitore visivo della card in HTML
                card_html = (
                    f'<div class="{classe_card}" style="background-color: {colore_sfondo};">'
                    f'<div>'
                    f'<strong style="font-size: 0.82rem; display: block; line-height: 1.15; max-height: 2.3em; overflow: hidden; color: #2c3e50;">{row["Titolo"]}</strong>'
                    f'<div style="font-size: 0.68rem; margin-top: 3px; color: #555;">🕒 {row["Inizio"]}</div>'
                    f'<div style="font-size: 0.68rem; color: #666; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{luogo_str}</div>'
                    f'</div>'
                    f'<div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">'
                    f'<div>{badge_cat} {badge_pri}</div>'
                    f'</div>'
                    f'</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)
                
                # Checkbox nativa posizionata subito sotto all'interno della stessa colonna della griglia
                nuovo_stato = st.checkbox("Fatto", value=is_completato, key=f"chk_{chiave_prefisso}_{global_idx}_{uid}")
                if nuovo_stato and uid not in st.session_state.completati:
                    st.session_state.completati.add(uid)
                    st.rerun()
                elif not nuovo_stato and uid in st.session_state.completati:
                    st.session_state.completati.remove(uid)
                    st.rerun()

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
    st.markdown('<hr style="margin: 0.4rem 0; border: none; border-top: 1px solid rgba(0,0,0,0.1);">', unsafe_allow_html=True)

    # 2. IMPEGNI DI OGGI
    if not eventi_oggi.empty:
        st.subheader("🔔 Impegni di Oggi")
        renderizza_griglia_card(eventi_oggi, "oggi")
        st.markdown('<hr style="margin: 0.4rem 0; border: none; border-top: 1px solid rgba(0,0,0,0.1);">', unsafe_allow_html=True)

    # 3. GRIGLIA EVENTI PER MESE
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
            renderizza_griglia_card(eventi_mese, "mese")
        else:
            st.info("Nessun evento in programma per il mese selezionato.")
    else:
        st.info("Nessuna data valida trovata nel calendario.")

    st.markdown('<hr style="margin: 0.4rem 0; border: none; border-top: 1px solid rgba(0,0,0,0.1);">', unsafe_allow_html=True)

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
        
        if isinstance(intervallo_date, tuple) and len(intervallo_date) == 2:
            df_f = df_f[df_f["DataInizio"].apply(lambda x: (intervallo_date[0] <= x <= intervallo_date[1]) if pd.notna(x) else False)]

        df_f["Completato"] = df_f["UID"].apply(lambda x: "✅" if x in st.session_state.completati else "❌")
        
        st.dataframe(df_f[["Titolo", "Inizio", "Categoria", "Priorità", "Completato", "Luogo"]], use_container_width=True)

else:
    st.warning("Nessun evento trovato o errore di connessione.")
