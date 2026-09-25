from datetime import date, datetime
from icalendar import Calendar
import pandas as pd
import requests
import streamlit as st
import zoneinfo

# Configurazione della pagina
st.set_page_config(page_title="La mia agenda", page_icon="📅", layout="wide")

# Script JS per forzare lo scroll in cima all'apertura dell'app
st.markdown(
    """
    <script>
        window.scrollTo(0, 0);
    </script>
    """,
    unsafe_allow_html=True,
)

# Stile CSS con importazione del font Montserrat, titolo responsive e layout ultra-compatto per mobile
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');

    /* Applicazione globale del font Montserrat */
    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif !important;
    }

    /* Riduzione spazi generali per dispositivi mobili */
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    /* Titolo principale responsivo (sta su un'unica riga senza icona) */
    h1.custom-title {
        color: #2e7d32 !important;
        font-size: 2.2rem !important;
        font-weight: 900 !important;
        padding-top: 0px;
        margin-top: -10px;
        margin-bottom: 0px;
        letter-spacing: -0.5px;
        white-space: nowrap;
    }

    @media (max-width: 640px) {
        h1.custom-title {
            font-size: 1.7rem !important;
        }
    }

    /* Card quadrate compatte e moderne */
    .event-card {
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 10px;
        border-left: 4px solid rgba(0,0,0,0.15);
        min-height: 125px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .event-completato {
        opacity: 0.55;
        text-decoration: line-through;
    }
    .badge-casa {
        background-color: #e8f5e9;
        color: #2e7d32;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
    }
    .badge-lavoro {
        background-color: #e3f2fd;
        color: #1565c0;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
    }
    .badge-priorita {
        background-color: #ffebee;
        color: #c62828;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
    }
    
    /* Riduce i margini dei widget Streamlit per risparmiare spazio verticale */
    div.stButton > button {
        padding: 0.25rem 0.5rem;
        font-size: 0.85rem;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Intestazione HTML con il titolo pulito senza icona
st.markdown(
    '<h1 class="custom-title">La mia agenda</h1>', unsafe_allow_html=True
)
st.caption("Sincronizzato in tempo reale (Fuso orario: Roma)")

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


# Funzione per estrarre categoria e priorità
def analizza_dettagli_evento(titolo, descrizione, categoria_ical):
  testo_globale = f"{titolo} {descrizione} {categoria_ical}".lower()

  if any(
      k in testo_globale
      for k in [
          "lavoro",
          "ufficio",
          "meeting",
          "call",
          "client",
          "riunione",
          "lavorare",
      ]
  ):
    categoria = "Lavoro"
  elif any(
      k in testo_globale
      for k in ["casa", "famiglia", "spesa", "medico", "commissione", "relax"]
  ):
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
        if hasattr(cat_raw, "to_ical"):
          cat_str = cat_raw.to_ical().decode("utf-8")
        else:
          cat_str = str(cat_raw)

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

        categoria, priorita = analizza_dettagli_evento(
            titolo, descrizione, cat_str
        )
        uid = f"{titolo}_{str(data_obj)}"

        eventi.append({
            "UID": uid,
            "Titolo": titolo,
            "DataInizio": data_obj,
            "Inizio": data_str_ita,
            "Luogo": luogo,
            "Descrizione": descrizione,
            "Categoria": categoria,
            "Priorità": priorita,
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
with st.spinner("Sincronizzazione in corso..."):
  df = carica_eventi(URL_CALENDARIO)

if not df.empty:
  oggi = get_oggi_italia()

  if "completati" not in st.session_state:
    st.session_state.completati = set()

  eventi_oggi = df[
      df["DataInizio"].apply(lambda x: x == oggi if pd.notna(x) else False)
  ]
  eventi_futuri = df[
      df["DataInizio"].apply(lambda x: x >= oggi if pd.notna(x) else False)
  ]

  # --- SEZIONE 1: SOMMARIO COMPATTO ---
  st.markdown(
      f"📌 **Oggi:** `{len(eventi_oggi)}` &nbsp;|&nbsp; 🚀 **Futuri:**"
      f" `{len(eventi_futuri)}` &nbsp;|&nbsp; 📅 **Totali:** `{len(df)}`"
  )

  st.markdown("---")

  # --- SEZIONE 2: IMPEGNI DI OGGI ---
  if not eventi_oggi.empty:
    st.subheader("🔔 Impegni di Oggi")
    for idx, (_, row) in enumerate(eventi_oggi.iterrows()):
      uid = row["UID"]
      is_completato = uid in st.session_state.completati

      luogo_txt = f"📍 {row['Luogo']}" if row["Luogo"] else ""
      desc_txt = f"📝 {row['Descrizione']}" if row["Descrizione"] else ""

      badge_cat = (
          '<span class="badge-lavoro">Lavoro</span>'
          if row["Categoria"] == "Lavoro"
          else (
              '<span class="badge-casa">Casa</span>'
              if row["Categoria"] == "Casa"
              else ""
          )
      )
      badge_pri = (
          '<span class="badge-priorita">⚠️ Priorità Alta</span>'
          if row["Priorità"] == "Alta"
          else ""
      )

      with st.container(border=True):
        col_t, col_c = st.columns([3, 1])
        with col_t:
          stile_testo = (
              'class="event-completato"' if is_completato else ""
          )
          st.markdown(
              f"<div {stile_testo}><strong>{row['Titolo']}</strong></div>",
              unsafe_allow_html=True,
          )
          st.caption(f"🕒 {row['Inizio']}")
          if luogo_txt:
            st.caption(luogo_txt)
          if desc_txt:
            st.caption(desc_txt)
          st.markdown(
              f'<div style="margin-top: 4px;">{badge_cat} {badge_pri}</div>',
              unsafe_allow_html=True,
          )
        with col_c:
          nuovo_stato = st.checkbox(
              "Fatto", value=is_completato, key=f"chk_oggi_{idx}_{uid}"
          )
          if nuovo_stato and uid not in st.session_state.completati:
            st.session_state.completati.add(uid)
            st.rerun()
          elif not nuovo_stato and uid in st.session_state.completati:
            st.session_state.completati.remove(uid)
            st.rerun()
    st.markdown("---")

  # --- SEZIONE 3: GRIGLIA EVENTI PER MESE (2 Colonne con checkbox integrato) ---
  st.subheader("🗓️ Appuntamenti per Mese")

  df_con_date = df.dropna(subset=["DataInizio"]).copy()
  if not df_con_date.empty:
    df_con_date["MeseAnno"] = df_con_date["DataInizio"].apply(
        lambda x: x.strftime("%Y-%m")
    )
    mesi_disponibili = sorted(df_con_date["MeseAnno"].unique())

    mese_corrente_str = oggi.strftime("%Y-%m")
    default_index = (
        mesi_disponibili.index(mese_corrente_str)
        if mese_corrente_str in mesi_disponibili
        else 0
    )

    col_filtro_m, _ = st.columns([2, 2])
    with col_filtro_m:
      mese_scelto = st.selectbox(
          "Seleziona Mese:",
          mesi_disponibili,
          index=default_index,
          format_func=lambda x: datetime.strptime(x, "%Y-%m")
          .strftime("%B %Y")
          .capitalize(),
      )

    anno_s, mese_s = map(int, mese_scelto.split("-"))

    eventi_mese = df[
        df["DataInizio"].apply(
            lambda x: (
                x.year == anno_s and x.month == mese_s
                if pd.notna(x)
                else False
            )
        )
    ].sort_values(by="DataInizio", ascending=True)

    if not eventi_mese.empty:
      num_colonne = 2
      colonne = st.columns(num_colonne)

      colori_sfondo = [
          "rgba(255, 223, 186, 0.35)",
          "rgba(186, 225, 255, 0.35)",
          "rgba(218, 255, 186, 0.35)",
          "rgba(255, 186, 203, 0.35)",
          "rgba(230, 218, 255, 0.35)",
          "rgba(255, 255, 186, 0.35)",
      ]

      for idx, (_, row) in enumerate(eventi_mese.iterrows()):
        col_corrente = colonne[idx % num_colonne]
        colore_corrente = colori_sfondo[idx % len(colori_sfondo)]
        uid = row["UID"]
        is_completato = uid in st.session_state.completati

        badge_cat = (
            '<span class="badge-lavoro">Lavoro</span>'
            if row["Categoria"] == "Lavoro"
            else (
                '<span class="badge-casa">Casa</span>'
                if row["Categoria"] == "Casa"
                else ""
            )
        )
        badge_pri = (
            '<span class="badge-priorita">⚠️ Alta</span>'
            if row["Priorità"] == "Alta"
            else ""
        )

        classe_card = (
            "event-card event-completato" if is_completato else "event-card"
        )
        luogo_str = f"📍 {row['Luogo']}" if row["Luogo"] else ""

        with col_corrente:
          # Container per unire card visiva e checkbox al suo interno in modo pulito
          with st.container(border=True):
            col_testo, col_chk = st.columns([3, 1])
            with col_testo:
              st.markdown(
                  f"""
                      <div class="{classe_card}" style="background-color: {colore_corrente}; border:none; margin-bottom:0; padding:0;">
                          <strong>{row['Titolo']}</strong><br>
                          <small>🕒 {row['Inizio']}</small><br>
                          <small>{luogo_str}</small><br>
                          <div style="margin-top: 4px;">{badge_cat} {badge_pri}</div>
                      </div>
                      """,
                  unsafe_allow_html=True,
              )
            with col_chk:
              nuovo_stato_card = st.checkbox(
                  "Fatto", value=is_completato, key=f"chk_mese_{idx}_{uid}"
              )
              if nuovo_stato_card and uid not in st.session_state.completati:
                st.session_state.completati.add(uid)
                st.rerun()
              elif (
                  not nuovo_stato_card and uid in st.session_state.completati
              ):
                st.session_state.completati.remove(uid)
                st.rerun()
    else:
      st.info("Nessun evento in programma per il mese selezionato.")
  else:
    st.info("Nessuna data valida trovata nel calendario.")

  st.markdown("---")

  # --- SEZIONE 4: RICERCA E FILTRI AVANZATI ---
  with st.expander("🔍 Altri filtri e ricerca avanzata"):
    c1, c2, c3 = st.columns(3)
    with c1:
      ricerca = st.text_input("Cerca parola chiave:")
    with c2:
      filtro_categoria = st.selectbox(
          "Categoria:", ["Tutte", "Casa", "Lavoro", "Generale"]
      )
    with c3:
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

    if filtro_categoria != "Tutte":
      df_f = df_f[df_f["Categoria"] == filtro_categoria]

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

    df_f["Completato"] = df_f["UID"].apply(
        lambda x: "✅ Sì" if x in st.session_state.completati else "❌ No"
    )

    st.subheader(f"Risultati ({len(df_f)})")
    st.dataframe(
        df_f[
            [
                "Titolo",
                "Inizio",
                "Categoria",
                "Priorità",
                "Completato",
                "Luogo",
                "Descrizione",
            ]
        ],
        use_container_width=True,
    )

    csv_data = df_f[
        [
            "Titolo",
            "Inizio",
            "Categoria",
            "Priorità",
            "Completato",
            "Luogo",
            "Descrizione",
        ]
    ].to_csv(index=False)
    st.download_button(
        label="📥 Scarica CSV",
        data=csv_data,
        file_name="miei_eventi_calendario.csv",
        mime="text/csv",
    )

else:
  st.warning("Nessun evento trovato o errore di connessione al calendario.")
