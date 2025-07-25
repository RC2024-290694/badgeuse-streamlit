import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta, date, time

# ---------- CONFIGURATION ----------
JOURNAL_FILE = "heures_travail.json"
DEFAULT_TARGET = 8.0             # heures normales
DEFAULT_ALERT = 8.5              # seuil d'alerte
DEFAULT_MAX = 9.0                # plafond
DAYS_HISTORY = 14                # jours à afficher en historique

# ---------- UTILITAIRES ----------

def load_journal():
    if os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE, "r") as f:
            return json.load(f)
    return {}


def save_journal(journal):
    with open(JOURNAL_FILE, "w") as f:
        json.dump(journal, f, indent=2)


def parse_ts(ts):
    return datetime.fromisoformat(ts) if ts else None


def format_td(td):
    h = td.seconds // 3600 + td.days * 24
    m = (td.seconds % 3600) // 60
    return f"{h}h {m}min"


def estimate_finish(start: datetime, worked: timedelta, target: float):
    remaining = timedelta(hours=target) - worked
    return start + remaining if remaining > timedelta(0) else datetime.now()

# ---------- CHARGEMENT ----------
journal = load_journal()
today = date.today().isoformat()

if today not in journal:
    journal[today] = {key: None for key in ["start","pause","resume","end"]}
    journal[today]["overtime_manual"] = 0.0

record = journal[today]

# ---------- SIDEBAR ----------
st.sidebar.title("📋 Paramètres")
target = st.sidebar.number_input("Objectif (h)", value=DEFAULT_TARGET, step=0.25)
alert_thresh = st.sidebar.number_input("Alerte (h)", value=DEFAULT_ALERT, step=0.25)
max_thresh = st.sidebar.number_input("Plafond (h)", value=DEFAULT_MAX, step=0.25)

# ---------- INTERFACE PRINCIPALE ----------
st.set_page_config(page_title="Badgeuse Mobile", layout="wide")
st.title("🕒 Tracker de Temps de Travail")

# Affichage des metrics
col1, col2, col3, col4 = st.columns(4)

# Calcul des temps
start_ts = parse_ts(record["start"])
pause_ts = parse_ts(record["pause"])
resume_ts = parse_ts(record["resume"])
end_ts = parse_ts(record["end"]) or datetime.now()

worked = timedelta(0)
if start_ts:
    if pause_ts and resume_ts:
        worked = (pause_ts - start_ts) + (end_ts - resume_ts)
    else:
        worked = end_ts - start_ts

delta_hours = worked.total_seconds()/3600 - target
manual_ot = record.get("overtime_manual", 0.0)

col1.metric("Temps travaillé",
            format_td(worked),
            delta=f"{delta_hours:+.2f}h")
col2.metric("Temps restants",
            format_td(timedelta(hours=target) - worked if worked < timedelta(hours=target) else timedelta(0)))
col3.metric("Overtime manuel",
            f"{manual_ot:.2f}h")
col4.metric("Est. fin (8h)",
            estimate_finish(resume_ts or start_ts or datetime.now(), worked, target).strftime('%H:%M') if start_ts else "--")

# ---------- BADGES ----------
st.subheader("📌 Actions")
cols = st.columns(4)

# Boutons conditionnels
def btn(label, enabled):
    return cols.pop(0).button(label, disabled=not enabled)

actions = {
    'start':  not record['start'],
    'pause':  record['start'] and not record['pause'],
    'resume': record['pause'] and not record['resume'],
    'end':    record['start'] and not record['end']
}

if btn("🟢 Démarrer la journée", actions['start']):
    record['start'] = datetime.now().isoformat()
    save_journal(journal)

if btn("🍽 Pause déjeuner", actions['pause']):
    record['pause'] = datetime.now().isoformat()
    save_journal(journal)

if btn("✅ Reprendre", actions['resume']):
    record['resume'] = datetime.now().isoformat()
    save_journal(journal)

if btn("🔴 Fin de journée", actions['end']):
    record['end'] = datetime.now().isoformat()
    save_journal(journal)

# Alerte
if worked.total_seconds() >= alert_thresh*3600:
    st.error(f"⚠️ Tu as dépassé {alert_thresh}h de travail !")

# Barre de progression
st.progress(min(worked.total_seconds()/(max_thresh*3600),1.0))
st.write(f"Repères : {target}h | {alert_thresh}h | {max_thresh}h")

# ---------- AJUSTEMENT ----------
st.subheader("🔧 Ajuster Overtime Manuellement")
over_input = st.number_input("Overtime manuelle (h)", value=manual_ot, step=0.25)
record['overtime_manual'] = over_input
save_journal(journal)

# ---------- HISTORIQUE & TÉLÉCHARGEMENT ----------
st.subheader("📅 Historique ({DAYS_HISTORY} jours)")
rows = []
time_formats = []

for d, rec in sorted(journal.items(), reverse=True)[:DAYS_HISTORY]:
    s = parse_ts(rec['start'])
    p = parse_ts(rec['pause'])
    r = parse_ts(rec['resume'])
    e = parse_ts(rec['end']) or datetime.now()
    if s:
        wt = (p - s if p and s else timedelta(0)) + (e - r if r and e else timedelta(0)) if p and r else (e - s)
        delta = round(wt.total_seconds()/3600 - target,2)
        rows.append({
            'Date': d,
            'Start': s.strftime('%H:%M') if s else '',
            'Pause': p.strftime('%H:%M') if p else '',
            'Resume': r.strftime('%H:%M') if r else '',
            'End': e.strftime('%H:%M') if e else '',
            'Worked (h)': round(wt.total_seconds()/3600,2),
            'Delta vs target': delta,
            'Manual OT': rec.get('overtime_manual',0.0)
        })

if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df)
    # Export CSV & Excel
    csv = df.to_csv(index=False).encode()
    st.download_button("Télécharger CSV", csv, "heures_travail.csv", "text/csv")

    # Excel
    def to_excel(df):
        from io import BytesIO
        with BytesIO() as buf:
            writer = pd.ExcelWriter(buf, engine='xlsxwriter')
            df.to_excel(writer, index=False, sheet_name='Journal')
            writer.save()
            return buf.getvalue()
    xlsx_data = to_excel(df)
    st.download_button("Télécharger Excel", xlsx_data, "heures_travail.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------- Thème mobile-friendly ----------
st.markdown("<style>button {width: 100%; margin-bottom: 10px;} .stProgress > div > div > div {height: 20px;}</style>", unsafe_allow_html=True)
