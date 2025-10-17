# app.py
import sqlite3
from io import BytesIO
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

# ---------- Config ----------
TZ = ZoneInfo("Europe/Zurich")
DB_PATH = "stamps.db"
DAILY_TARGET = timedelta(hours=8)

st.set_page_config(page_title="Badge 8h", page_icon="⏱️", layout="centered")

# ---------- Storage ----------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stamps(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,        -- YYYY-MM-DD (local)
            ts_utc TEXT NOT NULL,     -- ISO in UTC
            ts_local TEXT NOT NULL,   -- ISO local
            source TEXT DEFAULT 'btn',
            note TEXT
        )
    """)
    return conn

def now_local():
    return datetime.now(TZ)

def iso_local(dt):  # pretty ISO without microseconds
    return dt.replace(microsecond=0).isoformat()

def add_stamp(note=None, source="btn"):
    t_local = now_local()
    t_utc = t_local.astimezone(ZoneInfo("UTC"))
    day = t_local.date().isoformat()
    with get_conn() as c:
        c.execute(
            "INSERT INTO stamps(day, ts_utc, ts_local, source, note) VALUES(?,?,?,?,?)",
            (day, t_utc.isoformat(), iso_local(t_local), source, note),
        )

def get_stamps_for_day(day_iso: str) -> pd.DataFrame:
    with get_conn() as c:
        df = pd.read_sql_query(
            "SELECT id, day, ts_local, source, note FROM stamps WHERE day=? ORDER BY ts_local ASC",
            c, params=(day_iso,)
        )
    if not df.empty:
        df["ts_local"] = pd.to_datetime(df["ts_local"])
    return df

def delete_last_stamp(day_iso: str):
    with get_conn() as c:
        cur = c.execute("SELECT id FROM stamps WHERE day=? ORDER BY ts_local DESC LIMIT 1", (day_iso,))
        row = cur.fetchone()
        if row:
            c.execute("DELETE FROM stamps WHERE id=?", (row[0],))

# ---------- Time math ----------
def pairwise_intervals(timestamps: list[datetime]) -> list[tuple[datetime, datetime]]:
    """Pair stamps [in, out, in, out, ...]; if odd count, last interval is [last_in, now]."""
    intervals = []
    n = len(timestamps)
    for i in range(0, n, 2):
        start = timestamps[i]
        if i + 1 < n:
            end = timestamps[i+1]
        else:
            end = now_local()
        if end > start:
            intervals.append((start, end))
    return intervals

def worked_duration_today(stamps: list[datetime]) -> timedelta:
    return sum((end - start for start, end in pairwise_intervals(stamps)), timedelta())

def eta_after_third_stamp(stamps: list[datetime]) -> datetime | None:
    """After 3 stamps: ETA = stamp3 + (8h - (stamp2 - stamp1))"""
    if len(stamps) < 3:
        return None
    t1, t2, t3 = stamps[0], stamps[1], stamps[2]
    morning = max(timedelta(), t2 - t1)
    remaining = DAILY_TARGET - morning
    if remaining <= timedelta():
        # 8h already covered by morning (edge case)
        return t3
    return t3 + remaining

def fmt_td(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    return f"{sign}{h:02d}h{m:02d}"

# ---------- Monthly summary & export ----------
def monthly_summary(year: int, month: int) -> pd.DataFrame:
    start = date(year, month, 1)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)  # next month
    with get_conn() as c:
        df = pd.read_sql_query(
            "SELECT day, ts_local FROM stamps WHERE day >= ? AND day < ? ORDER BY day, ts_local",
            c, params=(start.isoformat(), end.isoformat())
        )
    if df.empty:
        return pd.DataFrame(columns=["Day", "Stamp 1", "Stamp 2", "Stamp 3", "Stamp 4", "Worked", "Delta_vs_8h"])
    df["ts_local"] = pd.to_datetime(df["ts_local"])
    out_rows = []
    for d, grp in df.groupby("day"):
        times = list(grp["ts_local"])
        worked = worked_duration_today(times)
        delta = worked - DAILY_TARGET
        row = {"Day": d,
               "Worked": fmt_td(worked),
               "Delta_vs_8h": fmt_td(delta)}
        # put first 4 stamps in columns
        for i in range(4):
            row[f"Stamp {i+1}"] = times[i].strftime("%H:%M:%S") if i < len(times) else ""
        out_rows.append(row)
    res = pd.DataFrame(out_rows).sort_values("Day")
    return res[["Day", "Stamp 1", "Stamp 2", "Stamp 3", "Stamp 4", "Worked", "Delta_vs_8h"]]

def export_month_excel(year: int, month: int) -> bytes:
    summary = monthly_summary(year, month)
    with get_conn() as c:
        raw = pd.read_sql_query(
            "SELECT day, ts_local, source, IFNULL(note,'') AS note FROM stamps WHERE substr(day,1,7)=? ORDER BY day, ts_local",
            c, params=(f"{year:04d}-{month:02d}",)
        )
    raw["ts_local"] = pd.to_datetime(raw["ts_local"])
    raw["Time"] = raw["ts_local"].dt.strftime("%Y-%m-%d %H:%M:%S")
    raw = raw.drop(columns=["ts_local"]).rename(columns={"day": "Day", "source": "Source", "note": "Note"})

    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        summary.to_excel(writer, index=False, sheet_name="Summary")
        raw.to_excel(writer, index=False, sheet_name="Raw")
    bio.seek(0)
    return bio.read()

# ---------- UI ----------
st.title("⏱️ Badge 8h")

colA, colB = st.columns([2, 1])
with colA:
    st.subheader("Badger aujourd'hui")
with colB:
    st.caption("Europe/Zurich")

today_iso = now_local().date().isoformat()

# Action buttons
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🟢 Badger maintenant", use_container_width=True):
        add_stamp()
        st.rerun()
with c2:
    note = st.text_input("Note (optionnel)", value="", placeholder="ex: arrivée tardive, meeting, ...")
    if st.button("➕ Ajouter manuellement (HH:MM)", use_container_width=True):
        st.warning("Saisis l'heure au format HH:MM dans le champ ci-dessous.")
with c3:
    if st.button("↩️ Supprimer dernier stamp", use_container_width=True):
        delete_last_stamp(today_iso)
        st.rerun()

manual_time = st.text_input("Heure manuelle (HH:MM)", label_visibility="collapsed", placeholder="HH:MM")
if manual_time:
    try:
        hh, mm = map(int, manual_time.strip().split(":"))
        t = now_local().replace(hour=hh, minute=mm, second=0, microsecond=0)
        # empêcher futur
        if t > now_local():
            st.error("Heure future non autorisée.")
        else:
            with get_conn() as c:
                c.execute(
                    "INSERT INTO stamps(day, ts_utc, ts_local, source, note) VALUES(?,?,?,?,?)",
                    (t.date().isoformat(),
                     t.astimezone(ZoneInfo("UTC")).isoformat(),
                     iso_local(t),
                     "manual",
                     note if note else None),
                )
            st.success(f"Ajouté: {t.strftime('%H:%M')}")
            st.rerun()
    except Exception:
        pass  # on attend une HH:MM valide

# Today panel
st.divider()
st.subheader("🗓️ Aujourd'hui")

df_today = get_stamps_for_day(today_iso)
times_today = list(df_today["ts_local"]) if not df_today.empty else []

if df_today.empty:
    st.info("Aucun stamp pour l’instant. Clique sur **Badger maintenant**.")
else:
    st.dataframe(
        df_today[["ts_local", "source", "note"]].rename(columns={"ts_local": "Horodatage", "source": "Source", "note": "Note"}),
        use_container_width=True, hide_index=True
    )

    worked = worked_duration_today(times_today)
    st.metric("Temps travaillé (cumul)", fmt_td(worked))
    progress = min(1.0, worked / DAILY_TARGET if DAILY_TARGET.total_seconds() else 0.0)
    st.progress(progress)

    if len(times_today) >= 3:
        eta = eta_after_third_stamp(times_today)
        if eta:
            st.metric("Heure prévue d’atteinte des 8h (après 3ᵉ stamp)", eta.strftime("%H:%M"))

    # Détail des intervalles
    with st.expander("Détails des intervalles"):
        rows = []
        for i, (start, end) in enumerate(pairwise_intervals(times_today), start=1):
            rows.append({
                "Intervalle": f"{i}",
                "Début": start.strftime("%H:%M:%S"),
                "Fin": end.strftime("%H:%M:%S"),
                "Durée": fmt_td(end - start)
            })
        st.table(pd.DataFrame(rows))

# Monthly export
st.divider()
st.subheader("📤 Export mensuel Excel")

colm1, colm2, colm3 = st.columns(3)
with colm1:
    year = st.number_input("Année", min_value=2000, max_value=2100, value=now_local().year, step=1)
with colm2:
    month = st.number_input("Mois", min_value=1, max_value=12, value=now_local().month, step=1)
with colm3:
    st.write("")  # spacer
    if st.button("Générer Excel"):
        data = export_month_excel(int(year), int(month))
        fname = f"badge_{int(year):04d}-{int(month):02d}.xlsx"
        st.download_button("⬇️ Télécharger", data=data, file_name=fname, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.caption("Conseil : tu peux dépasser 4 stamps, l’appli calcule par paires (1-2, 3-4, …). Le dernier non appairé est considéré « en cours » jusqu’à maintenant.")
