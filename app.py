from datetime import date, datetime
from icalendar import Calendar
import pandas as pd
import requests
import streamlit as st
import zoneinfo

# Configurazione della pagina
st.set_page_config(page_title="La mia agenda", page_icon="📅", layout="wide")

# Stile CSS con griglia forzata a 2 colonne reali e testi ottimizzati
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');

    /* Applicazione globale del font Montserrat */
    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif !important;
    }

    /* Gestione degli spazi della pagina */
    .block-container {
        padding-top: 2.5rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }

    /* Titolo principale responsivo */
    h1.custom-title {
        color: #1b5e20 !important;
        font-size: 1.8rem !important;
        font-weight: 900 !important;
        margin-top: 0px !important;
        padding-top: 0px !important;
        margin-bottom: 0px !important;
        letter-spacing: -0.5px;
    }

    @media (max-width: 640px) {
        h1.custom-title {
            font-size: 1.4rem !important;
        }
    }

    /* RIGA DELLA GRIGLIA: Forza sempre 2 colonne affiancate al 50% ciascuna */
    .row-card-2col {
        display: flex;
        flex-direction: row;
        gap: 10px;
        margin-bottom: 10px;
        width: 100%;
    }

    .col-card-item {
        flex: 1 1 50%;
        max-width: 50%;
        box-sizing: border-box;
    }

    /* Card eventi con altezza flessibile e ottimizzata */
    .event-card {
        border-radius: 10px;
        padding: 10px;
        min-height: 155px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-sizing: border-box;
        border: 1px solid rgba(0,0,0,0.06);
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        overflow: hidden;
    }
    .event-completato {
        opacity: 0.5;
        text-decoration: line-through;
    }

    /* Testi all'interno della card ridimensionati per essere ben leggibili */
    .card-title {
        font-size: 0.8rem !important;
        font-weight: 700 !important;
        display: block;
        line-height: 1.2;
        max-height: 2.4em;
        overflow: hidden;
        color: #2c3e50;
        margin-bottom: 3px;
    }
    .card-info {
        font-size: 0.68rem !important;
        color: #555;
        margin-bottom: 2px;
    }
    .card-luogo {
        font-size: 0.65rem !important;
        color: #666;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Badge con colori vivaci */
    .badge-casa {
        background-color: #d1e7dd;
        color: #0f5132;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.6rem;
        font-weight: 700;
    }
    .badge-lavoro {
        background-color: #cfe2ff;
        color: #084298;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.6rem;
        font-weight: 700;
    }
    .badge-priorita {
        background-color: #f8d7da;
        color: #842029;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.6rem;
        font-weight: 700;
    }

    /* Compattezza e pulizia per i checkbox Streamlit */
    [data-testid="stCheckbox"] {
        margin-top: -4px !important;
        margin-bottom: 0px !important;
    }
    [data-testid="stCheckbox"] label {
        font-size: 0.75rem !important;
    }
    
    [data-testid="stVerticalBlock"] {
        gap: 0.1rem !important;
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

# --- FUNZIONE PER RENDERIZZARE LA GRIGLIA A 2 COLONNE REALI ---
def renderizza_griglia_card(df_eventi, chiave_prefisso):
    colori_pastello = [
        "#fdf2e9", "#e8f8f5", "#ebf5fb", "#f4ecf7", "#fef9e7", "#f2f4f4"
    ]

    lista_eventi = df_eventi.to_dict('records')

    for i in range(0, len(lista_eventi), 2):
        coppia = [lista_eventi[i]]
        if i + 1 < len(lista_eventi):
            coppia.append(lista_eventi[i+1])

        # 1. Renderizziamo la riga HTML con le 2 card affiancate
        riga_html = '<div class="row-card-2col">'
        for offset, item in enumerate(coppia):
            global_idx = i + offset
            uid = item["UID"]
            is_completato = uid in st.session_state.completati
            colore_sfondo = colori_pastello[global_idx % len(colori_pastello)]

            badge_cat = '<span class="badge-lavoro">Lavoro</span>' if item["Categoria"] == "Lavoro" else ('<span class="badge-casa">Casa</span>' if item["Categoria"] == "Casa" else "")
            badge_pri = '<span class="badge-priorita">⚠️ Alta</span>' if item["Priorità"] == "Alta" else ""
            classe_card = "event-card event-completato" if is_completato else "event-card"
            luogo_str = f"📍 {item['Luogo']}" if item["Luogo"] else ""

            riga_html += (
                f'<div class="col-card-item">'
                f'<div class="{classe_card}" style="background-color: {colore_sfondo};">'
                f'<div>'
                f'<span class="card-title">{item["Titolo"]}</span>'
                f'<div class="card-info">🕒 {item["Inizio"]}</div>'
                f'<div class="card-luogo">{luogo_str}</div>'
                f'</div>'
                f'<div style="margin-top: 4px;">{badge_cat} {badge_pri}</div>'
                f'</div>'
                f'</div>'
            )
        riga_html += '</div>'
        st.markdown(riga_html, unsafe_allow_html=True)

        # 2. Sotto la riga grafica, posizioniamo i due checkbox in modo perfettamente sincronizzato
        cols = st.columns(2)
        for offset, item in enumerate(coppia):
            with cols[offset]:
                uid = item["UID"]
                is_comp = uid in st.session_state.completati
                idx = i + offset
                nuovo_stato = st.checkbox("Fatto", value=is_comp, key=f"chk_{chiave_prefisso}_{idx}_{uid}")
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
    st.markdown('<hr style="margin: 0.3rem 0; border: none; border-top: 1px solid rgba(0,0,0,0.1);">', unsafe_allow_html=True)

    # 2. IMPEGNI DI OGGI
    if not eventi_oggi.empty:
        st.subheader("🔔 Impegni di Oggi")
        renderizza_griglia_card(eventi_oggi, "oggi")
        st.markdown('<hr style="margin: 0.3rem 0; border: none; border-top: 1px solid rgba(0,0,0,0.1);">', unsafe_allow_html=True)

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

    st.markdown('<hr style="margin: 0.3rem 0; border: none; border-top: 1px solid rgba(0,0,0,0.1);">', unsafe_allow_html=True)

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
