import streamlit as st
import json
import os
from datetime import datetime, timedelta

# -------- CONFIG --------
JOURNAL_FILE = "heures_travail.json"
HEURES_CIBLE = 8
ALERTE_DEPASSEMENT = 8.5

# -------- CHARGEMENT / SAUVEGARDE --------
def charger_journal():
    if os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE, "r") as f:
            return json.load(f)
    return {}

def sauvegarder_journal(journal):
    with open(JOURNAL_FILE, "w") as f:
        json.dump(journal, f, indent=2)

# -------- FORMATAGE TEMPS --------
def format_timedelta(td):
    heures, reste = divmod(td.total_seconds(), 3600)
    minutes = reste // 60
    return f"{int(heures)}h {int(minutes)}min"

def estimer_fin(reprise, deja_fait):
    reste = timedelta(hours=HEURES_CIBLE) - deja_fait
    return reprise + reste

# -------- INTERFACE --------
st.set_page_config("Badgeuse Journalière")
st.title("🕒 Tracker de Travail Quotidien")
st.caption("Objectif : 8h / Alerte à 8h30")

date_du_jour = datetime.now().date().isoformat()
journal = charger_journal()

if date_du_jour not in journal:
    journal[date_du_jour] = {
        "debut": None,
        "pause": None,
        "reprise": None,
        "fin": None
    }

data = journal[date_du_jour]

# --- BADGES ---
col1, col2 = st.columns(2)

if col1.button("🟢 Démarrer la journée"):
    data["debut"] = datetime.now().isoformat()
    sauvegarder_journal(journal)

if col2.button("🍽️ Pause déjeuner"):
    data["pause"] = datetime.now().isoformat()
    sauvegarder_journal(journal)

if col1.button("✅ Reprendre après pause"):
    data["reprise"] = datetime.now().isoformat()
    sauvegarder_journal(journal)

if col2.button("🔴 Fin de journée"):
    data["fin"] = datetime.now().isoformat()
    sauvegarder_journal(journal)

# --- CALCUL TEMPS ---
debut = datetime.fromisoformat(data["debut"]) if data["debut"] else None
pause = datetime.fromisoformat(data["pause"]) if data["pause"] else None
reprise = datetime.fromisoformat(data["reprise"]) if data["reprise"] else None
fin = datetime.fromisoformat(data["fin"]) if data["fin"] else datetime.now()

temps_total = timedelta()

if debut:
    if pause and reprise:
        matin = pause - debut
        apres = fin - reprise
        temps_total = matin + apres
    else:
        temps_total = fin - debut

    st.markdown(f"⏱️ **Temps travaillé :** {format_timedelta(temps_total)}")

    if reprise:
        heure_fin_estimee = estimer_fin(reprise, temps_total)
        st.markdown(f"🧮 **Heure estimée de fin (8h) :** `{heure_fin_estimee.strftime('%H:%M')}`")

    if temps_total.total_seconds() >= ALERTE_DEPASSEMENT * 3600:
        st.error("⚠️ Tu as dépassé les 8h30 de travail !")

else:
    st.info("Clique sur *Démarrer la journée* pour commencer le tracking.")

# --- HISTORIQUE (optionnel) ---
with st.expander("📅 Historique des jours précédents"):
    for jour, d in sorted(journal.items(), reverse=True):
        if d["debut"]:
            deb = datetime.fromisoformat(d["debut"])
            f = datetime.fromisoformat(d["fin"]) if d["fin"] else datetime.now()
            if d["pause"] and d["reprise"]:
                p = datetime.fromisoformat(d["pause"])
                r = datetime.fromisoformat(d["reprise"])
                matin = p - deb
                aprem = f - r
                total = matin + aprem
            else:
                total = f - deb
            st.markdown(f"- **{jour}** : {format_timedelta(total)}")

