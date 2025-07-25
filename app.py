import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta

# Constantes
JOURNAL_FILE = "heures_travail.json"
HEURES_CIBLE = 8
HEURES_ALERTE = 8.5
HEURES_MAX = 9.0

# Fonctions de base
def charger_journal():
    if os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE, "r") as f:
            return json.load(f)
    return {}

def sauvegarder_journal(journal):
    with open(JOURNAL_FILE, "w") as f:
        json.dump(journal, f, indent=2)

def format_timedelta(td):
    heures, reste = divmod(td.total_seconds(), 3600)
    minutes = reste // 60
    return f"{int(heures)}h {int(minutes)}min"

def estimer_fin(reprise, deja_fait):
    reste = timedelta(hours=HEURES_CIBLE) - deja_fait
    return reprise + reste

# Chargement
date_du_jour = datetime.now().date().isoformat()
journal = charger_journal()

if date_du_jour not in journal:
    journal[date_du_jour] = {
        "debut": None,
        "pause": None,
        "reprise": None,
        "fin": None,
        "overtime": 0.0
    }

data = journal[date_du_jour]

# UI principale
st.set_page_config("Badgeuse")
st.title("🕒 Tracker de Travail")

# Badges visibles en permanence
st.subheader("📌 Badges")
col1, col2 = st.columns(2)

if col1.button("🟢 Démarrer la journée"):
    data["debut"] = datetime.now().isoformat()
    sauvegarder_journal(journal)

if col2.button("🍽 Pause déjeuner"):
    data["pause"] = datetime.now().isoformat()
    sauvegarder_journal(journal)

if col1.button("✅ Reprendre"):
    data["reprise"] = datetime.now().isoformat()
    sauvegarder_journal(journal)

if col2.button("🔴 Fin de journée"):
    data["fin"] = datetime.now().isoformat()
    sauvegarder_journal(journal)

# Récupération des temps
fmt = lambda x: datetime.fromisoformat(x) if x else None
debut = fmt(data["debut"])
pause = fmt(data["pause"])
reprise = fmt(data["reprise"])
fin = fmt(data["fin"]) if data["fin"] else datetime.now()

temps_total = timedelta()
if debut:
    if pause and reprise:
        matin = pause - debut
        aprem = fin - reprise
        temps_total = matin + aprem
    else:
        temps_total = fin - debut

    st.success(f"Temps travaillé : {format_timedelta(temps_total)}")

    if reprise:
        est_fin = estimer_fin(reprise, temps_total)
        st.info(f"Heure estimée de fin (8h) : {est_fin.strftime('%H:%M')}")

    st.markdown(f"**🔔 Heures de référence :** 8h | 8h30 | 9h")

    # Overtime
    overtime = (temps_total.total_seconds() / 3600) - HEURES_CIBLE
    if overtime > 0:
        data["overtime"] = round(overtime, 2)
        st.warning(f"🕑 Overtime actuel : {data['overtime']}h")

    if temps_total.total_seconds() >= HEURES_ALERTE * 3600:
        st.error("⚠️ Tu as dépassé 8h30 de travail !")

# Overtime manuel
st.subheader("🔧 Ajuster Overtime")
nouveau_ot = st.number_input("Corriger l'overtime (heures)", value=data.get("overtime", 0.0), step=0.25)
data["overtime"] = nouveau_ot
sauvegarder_journal(journal)

# Historique
st.subheader("📅 Historique")
records = []

for jour, d in journal.items():
    deb = fmt(d["debut"])
    f = fmt(d["fin"]) if d["fin"] else datetime.now()
    if deb:
        if d["pause"] and d["reprise"]:
            p = fmt(d["pause"])
            r = fmt(d["reprise"])
            matin = p - deb
            aprem = f - r
            total = matin + aprem
        else:
            total = f - deb

        h_total = total.total_seconds() / 3600
        delta = round(h_total - HEURES_CIBLE, 2)

        records.append({
            "Date": jour,
            "Heure début": deb.strftime('%H:%M') if deb else '',
            "Heure fin": f.strftime('%H:%M') if f else '',
            "Heures travaillées": round(h_total, 2),
            "Delta vs 8h": delta,
            "Overtime": d.get("overtime", 0.0)
        })

# Affichage tableau + export
if records:
    df = pd.DataFrame(records)
    st.dataframe(df)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Télécharger CSV", data=csv, file_name="heures_travail.csv", mime="text/csv")
