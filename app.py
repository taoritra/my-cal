from datetime import date, datetime
from icalendar import Calendar
import pandas as pd
import requests
import streamlit as st
import zoneinfo

# Configurazione della pagina (layout wide sfrutta al meglio la griglia)
st.set_page_config(
    page_title="Dashboard Calendario iCloud", page_icon="📊", layout="wide"
)

st.title("📊 Dashboard Calendario")
st.write("I tuoi impegni a portata di mano.")

# Recupero sicuro del link iCloud dai Secrets
try:
  URL_CALENDARIO = st.secrets["URL_ICLOUD"]
except Exception:
  st.error(
      "❌ Attenzione: il link iCloud non è configurato nei Secrets di"
      " Streamlit."
  )
  st.stop()


# Funzione per ottenere la data odierna esatta in Italia
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
    giorni = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    mesi = [
        "",
        "gen",
        "feb",
        "mar",
        "apr",
        "mag",
        "giu",
        "lug",
        "ago",
        "set",
        "ott",
        "nov",
        "dic",
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
with st.spinner("Sincronizzazione..."):
  df = carica_eventi(URL_CALENDARIO)

if not df.empty:
  oggi = get_oggi_italia()

  eventi_oggi = df[
      df["DataInizio"].apply(lambda x: x == oggi if pd.notna(x) else False)
  ]
  eventi_futuri = df[
      df["DataInizio"].apply(lambda x: x >= oggi if pd.notna(x) else False)
  ]

  # --- SEZIONE 1: KPI COMPATTI (Ottimizzati per mobile) ---
  col_m1, col_m2, col_m3 = st.columns(3)
  with col_m1:
    st.metric("Totali", len(df))
  with col_m2:
    st.metric("Oggi", len(eventi_oggi))
  with col_m3:
    st.metric("Futuri", len(eventi_futuri))

  st.markdown("---")

  # --- SEZIONE 2: IMPEGNI DI OGGI (Subito in cima!) ---
  if not eventi_oggi.empty:
    st.subheader("🔔 Impegni di Oggi")
    for _, row in eventi_oggi.iterrows():
      luogo_txt = f"📍 {row['Luogo']}" if row["Luogo"] else ""
      desc_txt = f"📝 {row['Descrizione']}" if row["Descrizione"] else ""

      with st.container(border=True):
        st.markdown(f"**📌 {row['Titolo']}**")
        st.caption(f"🕒 {row['Inizio']}")
        if luogo_txt:
          st.caption(luogo_txt)
        if desc_txt:
          st.caption(desc_txt)
    st.markdown("---")

  # --- SEZIONE 3: GRIGLIA EVENTI DEL MESE IN CORSO ---
  st.subheader(f"📅 Appuntamenti del Mese ({oggi.strftime('%B %Y')})")

  # Filtriamo gli eventi che appartengono allo stesso mese e anno odierni (e che sono futuri o di oggi)
  eventi_mese = eventi_futuri[
      eventi_futuri["DataInizio"].apply(
          lambda x: (
              x.year == oggi.year and x.month == oggi.month
              if pd.notna(x)
              else False
          )
      )
  ]

  if not eventi_mese.empty:
    # Creiamo una griglia a 3 colonne per desktop che diventa a colonna singola automatica su mobile
    num_colonne = 3
    colonne = st.columns(num_colonne)

    for idx, (_, row) in enumerate(eventi_mese.iterrows()):
      col_corrente = colonne[idx % num_colonne]
      with col_corrente:
        # Usiamo un contenitore con bordo per ogni "card" della griglia
        with st.container(border=True):
          st.markdown(f"**{row['Titolo']}**")
          st.caption(f"🕒 {row['Inizio']}")
          if row["Luogo"]:
            st.caption(f"📍 {row['Luogo']}")
  else:
    st.info("Nessun altro evento in programma per questo mese.")

  st.markdown("---")

  # --- SEZIONE 4: RICERCA E FILTRI AVANZATI ---
  with st.expander("🔍 Altri filtri e ricerca avanzata"):
    c1, c2 = st.columns(2)
    with c1:
      ricerca = st.text_input("Cerca parola chiave:")
    with c2:
      periodo = st.selectbox(
          "Periodo:", ["Solo Futuri", "Tutti", "Solo Passati"]
      )

    min_date = df["DataInizio"].min()
    max_date = df["DataInizio"].max()
    if pd.isna(min_date):
      min_date = oggi
    if pd.isna(max_date):
      max_date = oggi

    intervallo_date = st.date_input(
        "Intervallo personalizzato:",
        value=(
            min_date if isinstance(min_date, date) else oggi,
            max_date if isinstance(max_date, date) else oggi,
        ),
    )

    df_f = df.copy()

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

    st.subheader(f"Risultati ({len(df_f)})")
    st.dataframe(
        df_f[["Titolo", "Inizio", "Luogo", "Descrizione"]],
        use_container_width=True,
    )

    csv_data = df_f[
        ["Titolo", "Inizio", "Luogo", "Descrizione"]
    ].to_csv(index=False)
    st.download_button(
        label="📥 Scarica CSV",
        data=csv_data,
        file_name="miei_eventi_calendario.csv",
        mime="text/csv",
    )

else:
  st.warning("Nessun evento trovato o errore di connessione al calendario.")
