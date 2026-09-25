from datetime import date, datetime
from icalendar import Calendar
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Il mio Calendario iCloud", page_icon="📅", layout="centered"
)

st.title("📅 Il mio Calendario iCloud Personale")
st.write("Gestisci, cerca e filtra tutti i tuoi eventi in tempo reale.")

# Recuperiamo il link in modo sicuro dai Secrets di Streamlit
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
        titolo = str(componente.get("summary"))
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

        eventi.append(
            {"Titolo": titolo, "DataInizio": data_obj, "Inizio": data_str}
        )

    df = pd.DataFrame(eventi)
    if not df.empty:
      df = df.sort_values(by="DataInizio", na_position="last").reset_index(
          drop=True
      )
    return df
  except Exception as e:
    st.error(f"❌ Errore durante il caricamento: {e}")
    return pd.DataFrame()


# Caricamento dati
with st.spinner("Sincronizzazione con iCloud in corso..."):
  df = carica_eventi(URL_CALENDARIO)

if not df.empty:
  # Sezione Notifiche per Oggi
  oggi = date.today()
  eventi_oggi = df[df["DataInizio"] == oggi]

  if not eventi_oggi.empty:
    st.success(f"🔔 **ATTENZIONE: Hai {len(eventi_oggi)} eventi oggi!**")
    for _, row in eventi_oggi.iterrows():
      st.markdown(f"- **{row['Titolo']}** ({row['Inizio']})")

  st.divider()

  # Filtri interattivi
  col1, col2 = st.columns(2)
  with col1:
    ricerca = st.text_input("🔍 Cerca parola chiave:")
  with col2:
    periodo = st.selectbox(
        "📅 Filtra periodo:", ["Tutti", "Solo Futuri", "Solo Passati"]
    )

  df_f = df.copy()

  # Applicazione filtri
  if ricerca:
    df_f = df_f[df_f["Titolo"].str.contains(ricerca, case=False, na=False)]

  if periodo == "Solo Futuri":
    df_f = df_f[df_f["DataInizio"] >= oggi]
  elif periodo == "Solo Passati":
    df_f = df_f[df_f["DataInizio"] < oggi]

  st.write(f"Trovati **{len(df_f)}** eventi in base ai filtri:")
  st.dataframe(df_f[["Titolo", "Inizio"]], use_container_width=True)

else:
  st.warning("Nessun evento trovato. Controlla la connessione al calendario.")
