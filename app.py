import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta, date
from io import BytesIO

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
    st.experimental_rerun()  # Force rerun pour mettre à jour l'UI après chaque action


def parse_ts(ts):
    return datetime.fromisoformat(ts) if ts else None


def format_td(td):
    hours = td.seconds // 3600 + td.days * 24
    minutes = (td.seconds % 3600) // 60
    return f"{hours}h {minutes}min"


def estimate_finish(start, worked, target):
    remaining = timedelta(hours=target) - worked
    return (start + remaining) if remaining > timedelta(0) else datetime.now()

# ---------- CHARGEMENT & MIGRATION ----------
journal = load_journal()
# Migration des anciennes clés
for day, rec in journal.items():
    if "debut" in rec:
        rec.setdefault("start", rec.pop("debut"))
    if "reprise" in rec:
        rec.setdefault("resume", rec.pop("reprise"))
    if "fin" in rec:
        rec.setdefault("end", rec.pop("fin"))
    if "overtime" in rec:
        rec.setdefault("overtime_manual", rec.pop("overtime"))
    for k in ["start", "pause", "resume", "end"]:
        rec.setdefault(k, None)
    rec.setdefault("overtime_manual", 0.0)
# Initialisation du jour
today = date.today().isoformat()
if today not in journal:
    journal[today] = {"start": None, "pause": None, "resume": None, "end": None, "overtime_manual": 0.0}
record = journal[today]

# ---------- SIDEBAR ----------
st.sidebar.title("📋 Paramètres")
target = st.sidebar.number_input("Objectif (h)", value=DEFAULT_TARGET, step=0.25)
alert_thresh = st.sidebar.number_input("Alerte (h)", value=DEFAULT_ALERT, step=0.25)
max_thresh = st.sidebar.number_input("Plafond (h)", value=DEFAULT_MAX, step=0.25)

# ---------- INTERFACE PRINCIPALE ----------
st.set_page_config(page_title="Badgeuse Mobile", layout="wide")
st.title("🕒 Tracker de Temps de Travail")

# Calcul des temps
start_ts = parse_ts(record.get("start"))
pause_ts = parse_ts(record.get("pause"))
resume_ts = parse_ts(record.get("resume"))
end_ts = parse_ts(record.get("end")) or datetime.now()
worked = timedelta(0)
if start_ts:
    if pause_ts and resume_ts:
        worked = (pause_ts - start_ts) + (end_ts - resume_ts)
    else:
        worked = end_ts - start_ts

delta_hours = worked.total_seconds()/3600 - target
manual_ot = record.get("overtime_manual", 0.0)

# Affichage métriques
c1, c2, c3, c4 = st.columns(4)
c1.metric("Temps travaillé", format_td(worked), delta=f"{delta_hours:+.2f}h")
c2.metric("Temps restants", format_td((timedelta(hours=target) - worked) if worked < timedelta(hours=target) else timedelta(0)))
c3.metric("Overtime manuel", f"{manual_ot:.2f}h")
est_finish = estimate_finish(resume_ts or start_ts or datetime.now(), worked, target).strftime('%H:%M') if start_ts else "--"
c4.metric("Est. fin (8h)", est_finish)

# ---------- ACTIONS ----------
st.subheader("📌 Actions")
b1, b2, b3, b4 = st.columns(4)
actions = {
    "start": not record.get("start"),
    "pause": record.get("start") and not record.get("pause"),
    "resume": record.get("pause") and not record.get("resume"),
    "end": record.get("start") and not record.get("end")
}
if b1.button("🟢 Démarrer", disabled=not actions["start"]):
    record["start"] = datetime.now().isoformat()
    save_journal(journal)
if b2.button("🍽 Pause", disabled=not actions["pause"]):
    record["pause"] = datetime.now().isoformat()
    save_journal(journal)
if b3.button("✅ Reprendre", disabled=not actions["resume"]):
    record["resume"] = datetime.now().isoformat()
    save_journal(journal)
if b4.button("🔴 Fin", disabled=not actions["end"]):
    record["end"] = datetime.now().isoformat()
    save_journal(journal)

# Alerte & progression
if start_ts and worked.total_seconds() >= alert_thresh * 3600:
    st.error(f"⚠️ Tu as dépassé {alert_thresh}h !")
progress_val = min(worked.total_seconds()/(max_thresh*3600), 1.0)
st.progress(progress_val)
st.write(f"Repères : {target}h | {alert_thresh}h | {max_thresh}h")

# ---------- AJUSTEMENT OVERTIME ----------
st.subheader("🔧 Ajuster Overtime Manuel")
ot_input = st.number_input("Overtime manuel (h)", value=manual_ot, step=0.25)
if ot_input != record.get("overtime_manual", 0.0):
    record["overtime_manual"] = ot_input
    save_journal(journal)

# ---------- HISTORIQUE & EXPORT ----------
st.subheader(f"📅 Historique ({DAYS_HISTORY} jours)")
rows = []
for d, rec in sorted(journal.items(), reverse=True)[:DAYS_HISTORY]:
    s = parse_ts(rec.get("start"))
    p = parse_ts(rec.get("pause"))
    r = parse_ts(rec.get("resume"))
    e = parse_ts(rec.get("end")) or datetime.now()
    if s:
        wt = ((p - s) + (e - r)) if p and r else (e - s)
        delta = round(wt.total_seconds()/3600 - target, 2)
        rows.append({
            "Date": d,
            "Start": s.strftime('%H:%M'),
            "Pause": p.strftime('%H:%M') if p else "",
            "Resume": r.strftime('%H:%M') if r else "",
            "End": e.strftime('%H:%M'),
            "Worked (h)": round(wt.total_seconds()/3600, 2),
            "Delta vs tgt": delta,
            "Manual OT": rec.get("overtime_manual", 0.0)
        })
if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df)
    # Export CSV
    csv = df.to_csv(index=False).encode()
    st.download_button("📥 Télécharger CSV", csv, "heures_travail.csv", "text/csv")
    # Export Excel - nécessite openpyxl dans requirements.txt
    try:
        buf = BytesIO()
        df.to_excel(buf, index=False, sheet_name="Journal")
        buf.seek(0)
        xlsx = buf.getvalue()
        st.download_button("📥 Télécharger Excel", xlsx, "heures_travail.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except ModuleNotFoundError:
        st.warning("Pour exporter en Excel, ajoutez 'openpyxl' à votre requirements.txt.")

# ---------- STYLES MOBILE ----------
st.markdown(
    "<style>button{width:100%; margin-bottom:8px;} .stProgress>div>div>div{height:24px;}</style>",
    unsafe_allow_html=True
)
