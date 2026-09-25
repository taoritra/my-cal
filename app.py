from datetime import date, datetime
from icalendar import Calendar
import pandas as pd
import requests
import streamlit as st
import zoneinfo

# Configurazione della pagina
st.set_page_config(
    page_title="Dashboard Calendario iCloud", page_icon="📊", layout="wide"
)

# Stile CSS personalizzato per dare sfumature colorate alle card della griglia
st.markdown(
    """
    <style>
    /* Stile per le card colorate della griglia */
    .event-card {
        padding: 12px;
        border-radius: 10px;
        margin-bottom: 10px;
        border-left: 5px solid rgba(0,0,0,0.1);
    }
    </style>
""",
    unsafe_allow_html=True,
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

  # --- SEZIONE 1: SOMMARIO COMPATTO ---
  st.markdown(
      f"📌 **Oggi:** `{len(eventi_oggi)} eventi` &nbsp;|&nbsp; 🚀 **Futuri:**"
      f" `{len(eventi_futuri)}` &nbsp;|&nbsp; 📅 **Totali:** `{len(df)}`"
  )

  st.markdown("---")

  # --- SEZIONE 2: IMPEGNI DI OGGI ---
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

  # --- SEZIONE 3: GRIGLIA EVENTI DEL MESE IN CORSO (Con colori a rotazione) ---
  st.subheader(f"📅 Appuntamenti del Mese ({oggi.strftime('%B %Y')})")

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
    num_colonne = 3
    colonne = st.columns(num_colonne)

    # Lista di colori pastello alternati per le card
    colori_sfondo = [
        "rgba(255, 223, 186, 0.3)",  # Arancio tenue
        "rgba(186, 225, 255, 0.3)",  # Azzurro tenue
        "rgba(218, 255, 186, 0.3)",  # Verde tenue
        "rgba(255, 186, 203, 0.3)",  # Rosa tenue
        "rgba(230, 218, 255, 0.3)",  # Viola tenue
        "rgba(255, 255, 186, 0.3)",  # Giallo tenue
    ]

    for idx, (_, row) in enumerate(eventi_mese.iterrows()):
      col_corrente = colonne[idx % num_colonne]
      colore_corrente = colori_sfondo[idx % len(colori_sfondo)]

      with col_corrente:
        luogo_str = f"📍 {row['Luogo']}" if row["Luogo"] else ""
        # Creiamo una card HTML personalizzata con il colore di sfondo ciclico
        st.markdown(
            f"""
                <div class="event-card" style="background-color: {colore_corrente};">
                    <strong>{row['Titolo']}</strong><br>
                    <small>🕒 {row['Inizio']}</small><br>
                    <small>{luogo_str}</small>
                </div>
                """,
            unsafe_allow_html=True,
        )
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
          df_f["DataInzIndex"].apply(lambda x: x < oggi if pd.notna(x) else False)
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
