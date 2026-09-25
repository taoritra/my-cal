from datetime import date, datetime
from icalendar import Calendar
import pandas as pd
import requests
import streamlit as st
import zoneinfo  # Utile per gestire i fusi orari corretti

# Configurazione della pagina
st.set_page_config(
    page_title="Dashboard Calendario iCloud", page_icon="📊", layout="wide"
)

st.title("📊 Dashboard Calendario iCloud")
st.write("Panoramica rapida e gestione intelligente dei tuoi impegni.")

# Recupero sicuro del link iCloud dai Secrets
try:
  URL_CALENDARIO = st.secrets["URL_ICLOUD"]
except Exception:
  st.error(
      "❌ Attenzione: il link iCloud non è configurato nei Secrets di"
      " Streamlit."
  )
  st.stop()


# Funzione per ottenere la data odierna esatta in Italia (Fuso orario di Roma)
def get_oggi_italia():
  try:
    roma_tz = zoneinfo.ZoneInfo("Europe/Rome")
    return datetime.now(roma_tz).date()
  except Exception:
    return date.today()


# Funzione di supporto per formattare la data in italiano
def formatta_data_italiano(dt_val):
  if isinstance(dt_val, datetime):
    d = dt_val.date()
    ora_str = dt_val.strftime("alle %H:%M")
  else:
    d = dt_val
    ora_str = ""

  if isinstance(d, date):
    giorni = [
        "Lunedì",
        "Martedì",
        "Mercoledì",
        "Giovedì",
        "Venerdì",
        "Sabato",
        "Domenica",
    ]
    mesi = [
        "",
        "gennaio",
        "febbraio",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    ]
    nome_giorno = giorni[d.weekday()]
    nome_mese = mesi[d.month]
    data_formattata = f"{nome_giorno} {d.day} {nome_mese} {d.year}"
    return f"{data_formattata} {ora_str}".strip()
  return "Non definita"


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
          else:
            data_obj = dt_val

          data_str_ita = formatta_data_italiano(dt_val)
        else:
          data_obj = None
          data_str_ita = "Data non definita"

        eventi.append({
            "Titolo": titolo,
            "DataInizio": data_obj,
            "Inizio": data_str_ita,
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
  oggi = get_oggi_italia()

  # Filtri basati sulla data italiana corretta
  eventi_oggi = df[
      df["DataInizio"].apply(lambda x: x == oggi if pd.notna(x) else False)
  ]
  eventi_futuri = df[
      df["DataInizio"].apply(lambda x: x >= oggi if pd.notna(x) else False)
  ]

  # --- SEZIONE 1: KPI STATISTICHE ---
  col_m1, col_m2, col_m3 = st.columns(3)
  with col_m1:
    st.metric("📅 Eventi Totali", len(df))
  with col_m2:
    st.metric("🔔 Eventi di Oggi", len(eventi_oggi))
  with col_m3:
    st.metric("🚀 Eventi Futuri", len(eventi_futuri))

  st.divider()

  # --- SEZIONE 2: ANTEPRIMA EVENTI DI OGGI ---
  if not eventi_oggi.empty:
    st.subheader("🔔 Impegni di Oggi in Dettaglio")
    for _, row in eventi_oggi.iterrows():
      luogo_txt = f"📍 **Luogo:** {row['Luogo']}" if row["Luogo"] else ""
      desc_txt = f"📝 **Note:** {row['Descrizione']}" if row["Descrizione"] else ""

      with st.container(border=True):
        st.markdown(f"### 📌 {row['Titolo']}")
        st.write(f"🕒 **Quando:** {row['Inizio']}")
        if luogo_txt:
          st.write(luogo_txt)
        if desc_txt:
          st.write(desc_txt)
    st.divider()

  # --- SEZIONE 3: ANTEPRIMA PROSSIMI APPUNTAMENTI ---
  st.subheader("⚡ I prossimi appuntamenti in arrivo")
  prossimi_futuri = df[
      df["DataInizio"].apply(lambda x: x > oggi if pd.notna(x) else False)
  ].head(3)

  if not prossimi_futuri.empty:
    cols_prev = st.columns(len(prossimi_futuri))
    for idx, (_, row) in enumerate(prossimi_futuri.iterrows()):
      with cols_prev[idx]:
        luogo_txt = f"📍 {row['Luogo']}" if row["Luogo"] else "📍 Nessun luogo"
        st.info(f"**{row['Titolo']}**\n\n🕒 {row['Inizio']}\n\n{luogo_txt}")
  else:
    st.write("Nessun altro evento futuro oltre a oggi.")

  st.divider()

  # --- SEZIONE 4: FILTRI AVANZATI ---
  st.subheader("🔍 Cerca e Filtra")
  c1, c2, c3 = st.columns(3)

  with c1:
    ricerca = st.text_input("Cerca parola chiave:")
  with c2:
    periodo = st.selectbox(
        "Filtra periodo:", ["Solo Futuri", "Tutti", "Solo Passati"]
    )
  with c3:
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
    df_f = df_f[
        df_f["DataInizio"].apply(lambda x: x >= oggi if pd.notna(x) else False)
    ]
  elif periodo == "Solo Passati":
    df_f = df_f[
        df_f["DataInizio"].apply(lambda x: x < oggi if pd.notna(x) else False)
    ]

  if isinstance(intervallo_date, tuple) and len(intervallo_date) == 2:
    data_inizio_scelta, data_fine_scelta = intervallo_date
    df_f = df_f[
        df_f["DataInizio"].apply(
            lambda x: (data_inizio_scelta <= x <= data_fine_scelta)
            if pd.notna(x)
            else False
        )
    ]

  st.divider()

  # --- SEZIONE 5: TABELLA DATI E DOWNLOAD ---
  st.subheader(f"📋 Elenco Eventi ({len(df_f)} risultati)")

  st.dataframe(
      df_f[["Titolo", "Inizio", "Luogo", "Descrizione"]],
      use_container_width=True,
  )

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
