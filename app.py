import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta, date
from io import BytesIO

# ---------- CONFIGURATION ----------
JOURNAL_FILE = 'heures_travail.json'
TARGET = 8.0       # heures normales
ALERT = 8.5        # seuil d'alerte
MAX_HOURS = 9.0    # plafond
HISTORY_DAYS = 14  # jours dans l'historique

# ---------- UTILITAIRES ----------

def load_journal():
    if os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_journal(journal):
    with open(JOURNAL_FILE, 'w') as f:
        json.dump(journal, f, indent=2)


def parse_ts(ts):
    return datetime.fromisoformat(ts) if ts else None


def fmt_td(td):
    hours = td.seconds // 3600 + td.days * 24
    minutes = (td.seconds % 3600) // 60
    return f"{hours}h {minutes}min"


def estimate_end(start, worked):
    remaining = timedelta(hours=TARGET) - worked
    end_time = start + remaining if remaining > timedelta(0) else datetime.now()
    return end_time.strftime('%H:%M')

# ---------- CHARGEMENT JOURNAL ----------
journal = load_journal()
today = date.today().isoformat()
if today not in journal:
    journal[today] = {'start': None, 'pause': None, 'resume': None, 'end': None, 'overtime_manual': 0.0}
    save_journal(journal)
record = journal[today]

# ---------- SIDEBAR PARAMS ----------
st.sidebar.title('⚙️ Paramètres')
target = st.sidebar.number_input('Objectif (h)', value=TARGET, step=0.25)
alert_thresh = st.sidebar.number_input('Alerte (h)', value=ALERT, step=0.25)
max_thresh = st.sidebar.number_input('Plafond (h)', value=MAX_HOURS, step=0.25)

# ---------- CALCUL TEMPS ----------
start_ts = parse_ts(record.get('start'))
pause_ts = parse_ts(record.get('pause'))
resume_ts = parse_ts(record.get('resume'))
end_ts = parse_ts(record.get('end')) or datetime.now()
worked = timedelta(0)
if start_ts:
    if pause_ts and resume_ts:
        worked = (pause_ts - start_ts) + (end_ts - resume_ts)
    else:
        worked = end_ts - start_ts

delta = worked.total_seconds()/3600 - target
manual_ot = record.get('overtime_manual', 0.0)

# ---------- AFFICHAGE METRICS ----------
st.set_page_config(page_title='Badgeuse Mobile', layout='wide')
st.title('🕒 Tracker de Temps')
c1, c2, c3, c4 = st.columns(4)
c1.metric('Temps travaillé', fmt_td(worked), delta=f"{delta:+.2f}h")
c2.metric('Temps restants', fmt_td((timedelta(hours=target) - worked) if worked < timedelta(hours=target) else timedelta(0)))
c3.metric('Overtime manuel', f"{manual_ot:.2f}h")
end_est = estimate_end(resume_ts or start_ts, worked) if start_ts else '--'
c4.metric('Est. fin (8h)', end_est)

# ---------- ACTIONS AVEC CALLBACKS ----------
st.subheader('📌 Actions')
col1, col2, col3, col4 = st.columns(4)

def make_callback(key):
    def cb():
        record[key] = datetime.now().isoformat()
        save_journal(journal)
    return cb

col1.button('🟢 Démarrer', on_click=make_callback('start'), disabled=record['start'] is not None)
col2.button('🍽️ Pause', on_click=make_callback('pause'), disabled=record['start'] is None or record['pause'] is not None)
col3.button('✅ Reprendre', on_click=make_callback('resume'), disabled=record['pause'] is None or record['resume'] is not None)
col4.button('🔴 Fin', on_click=make_callback('end'), disabled=record['start'] is None or record['end'] is not None)

# Alerte et barre de progression
if start_ts and worked.total_seconds() >= alert_thresh*3600:
    st.error(f"⚠️ Tu as dépassé {alert_thresh}h de travail !")
progress = min(worked.total_seconds()/(max_thresh*3600), 1.0)
st.progress(progress)
st.write(f"Repères : {target}h | {alert_thresh}h | {max_thresh}h")

# ---------- AJUSTEMENT OVERTIME ----------
st.subheader('🔧 Ajuster Overtime Manuel')
ot = st.number_input('Overtime manuel (h)', value=manual_ot, step=0.25)
if ot != record['overtime_manual']:
    record['overtime_manual'] = ot
    save_journal(journal)

# ---------- HISTORIQUE & EXPORT ----------
st.subheader(f'📅 Historique ({HISTORY_DAYS} jours)')
rows = []
for d, rec in sorted(journal.items(), reverse=True)[:HISTORY_DAYS]:
    s = parse_ts(rec.get('start'))
    e = parse_ts(rec.get('end')) or datetime.now()
    if s:
        if rec.get('pause') and rec.get('resume'):
            p = parse_ts(rec['pause'])
            r = parse_ts(rec['resume'])
            w = (p - s) + (e - r)
        else:
            w = e - s
        rows.append({
            'Date': d,
            'Start': s.strftime('%H:%M'),
            'Pause': parse_ts(rec.get('pause')).strftime('%H:%M') if rec.get('pause') else '',
            'Resume': parse_ts(rec.get('resume')).strftime('%H:%M') if rec.get('resume') else '',
            'End': e.strftime('%H:%M'),
            'Worked (h)': round(w.total_seconds()/3600,2),
            'Delta vs tgt': round(w.total_seconds()/3600 - target, 2),
            'Manual OT': rec.get('overtime_manual', 0.0)
        })
if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df)
    # Export CSV
    csv = df.to_csv(index=False).encode()
    st.download_button('📥 Télécharger CSV', csv, 'heures_travail.csv', 'text/csv')
    # Export Excel si openpyxl dispo
    try:
        buf = BytesIO()
        df.to_excel(buf, index=False, sheet_name='Journal')
        buf.seek(0)
        st.download_button('📥 Télécharger Excel', buf.getvalue(), 'heures_travail.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except ModuleNotFoundError:
        st.info("Ajoute 'openpyxl' à ton requirements.txt pour l'export Excel.")

# ---------- STYLES MOBILE ----------
st.markdown("<style>button{width:100%;margin:5px 0;} .stProgress>div>div>div{height:24px;}</style>", unsafe_allow_html=True)
