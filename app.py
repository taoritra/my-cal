from datetime import date, datetime
from icalendar import Calendar
import pandas as pd
import requests
import streamlit as st

# Configurazione della pagina
st.set_page_config(
    page_title="Dashboard Calendario iCloud", page_icon="📊", layout="wide"
)

st.title("📊 Dashboard Calendario iCloud")
st.write(
    "Panoramica completa, statistiche in tempo reale e ricerca avanzata dei tuoi"
    " eventi."
)

# Recupero sicuro del link iCloud dai Secrets
try:
  URL_CALENDARIO = st.secrets["URL_ICLOUD"]
except Exception:
  st.error(
      "❌ Attenzione: il link iCloud non è configurato nei Secrets di"
      " Streamlit."
  )
  st.stop()


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
        inizio = componente.get("dtstart")

        if inizio:
          dt_val = inizio.dt
          if isinstance(dt_val, datetime):
            data_obj = dt_val.date()
            data_str = dt_val.strftime("%Y-%m-%d %H:%M")
          else:
            data_obj = dt_val
            data_str = dt_val.strftime("%Y-%m-%d")
        else:
          data_obj = None
          data_str = "Non definita"

        eventi.append({
            "Titolo": titolo,
            "DataInizio": data_obj,
            "Inizio": data_str,
            "Luogo": luogo,
            "Descrizione": descrizione,
        })

    df = pd.DataFrame(eventi)
    if not df.empty:
      df = df.sort_values(by="DataInizio", na_position="last").reset_index(
          drop=True
      )
    return df
  except Exception as e:
    st.error(f"❌ Errore durante il caricamento: {e}")
    return pd.DataFrame()


# Caricamento dati con spinner
with st.spinner("Sincronizzazione della dashboard in corso..."):
  df = carica_eventi(URL_CALENDARIO)

if not df.empty:
  oggi = date.today()

  # --- SEZIONE 1: STATISTICHE / KPI DASHBOARD ---
  eventi_oggi = df[df["DataInizio"] == oggi]
  eventi_futuri = df[df["DataInizio"] >= oggi]

  col_m1, col_m2, col_m3 = st.columns(3)
  with col_m1:
    st.metric("📅 Eventi Totali", len(df))
  with col_m2:
    st.metric("🔔 Eventi di Oggi", len(eventi_oggi))
  with col_m3:
    st.metric("🚀 Eventi Futuri", len(eventi_futuri))

  st.divider()

  # --- SEZIONE 2: FILTRI AVANZATI ---
  st.subheader("🔍 Filtri e Ricerca")
  c1, c2, c3 = st.columns(3)

  with c1:
    ricerca = st.text_input("Cerca parola chiave:")
  with c2:
    periodo = st.selectbox(
        "Filtra periodo:", ["Tutti", "Solo Futuri", "Solo Passati"]
    )
  with c3:
    # Filtro per intervallo di date personalizzato
    min_date = df["DataInizio"].min()
    max_date = df["DataInizio"].max()
    if pd.isna(min_date):
      min_date = oggi
    if pd.isna(max_date):
      max_date = oggi

    intervallo_date = st.date_input(
        "Intervallo date:",
        value=(
            min_date if isinstance(min_date, date) else oggi,
            max_date if isinstance(max_date, date) else oggi,
        ),
    )

  df_f = df.copy()

  # Applicazione filtri
  if ricerca:
    df_f = df_f[df_f["Titolo"].str.contains(ricerca, case=False, na=False)]

  if periodo == "Solo Futuri":
    df_f = df_f[df_f["DataInizio"] >= oggi]
  elif periodo == "Solo Passati":
    df_f = df_f[df_f["DataInizio"] < oggi]

  # Filtro intervallo date se l'utente ha selezionato entrambe le date
  if isinstance(intervallo_date, tuple) and len(intervallo_date) == 2:
    data_inizio_scelta, data_fine_scelta = intervallo_date
    df_f = df_f[
        (df_f["DataInizio"] >= data_inizio_scelta)
        & (df_f["DataInizio"] <= data_fine_scelta)
    ]

  st.divider()

  # --- SEZIONE 3: TABELLA DATI E DOWNLOAD ---
  st.subheader(f"📋 Elenco Eventi ({len(df_f)} risultati)")

  # Mostriamo la tabella con le nuove colonne (Titolo, Inizio, Luogo, Descrizione)
  st.dataframe(
      df_f[["Titolo", "Inizio", "Luogo", "Descrizione"]],
      use_container_width=True,
  )

  # Pulsante per scaricare in CSV
  csv_data = df_f[
      ["Titolo", "Inizio", "Luogo", "Descrizione"]
  ].to_csv(index=False)
  st.download_button(
      label="📥 Scarica eventi filtrati (CSV)",
      data=csv_data,
      file_name="miei_eventi_calendario.csv",
      mime="text/csv",
  )

else:
  st.warning("Nessun evento trovato o errore di connessione al calendario.")
