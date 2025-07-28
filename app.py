import streamlit as st
import pandas as pd

st.title("Physico-Chemical DB & Converters")

# --- Upload option ---
st.sidebar.header("Database Configuration")
upload = st.sidebar.file_uploader("Upload a CSV file with physico-chemical data", type=["csv"])

if upload:
    try:
        df = pd.read_csv(upload)
        df.set_index('Compound', inplace=True)
    except Exception as e:
        st.sidebar.error(f"Erreur en lisant le fichier: {e}")
        st.stop()
else:
    # --- Default sample database (35+ composés) ---
    data = {
        "Compound": [
            "Olive Oil", "Sunflower Oil", "Coconut Oil", "Corn Oil", "Canola Oil", "Palm Oil",
            "Hexane", "Toluene", "Ethanol", "Methanol", "Acetone", "Chloroform", "Dichloromethane (DCM)", "Isopropanol", "DMF", "DMSO", "Water",
            "β-Carotene", "Lycopene", "Lutein", "Zeaxanthin", "Astaxanthin", "Cryptoxanthin", "Phytoene", "Phytofluene",
            "Vitamin A (Retinol)", "Vitamin C (Ascorbic Acid)", "Vitamin D3 (Cholecalciferol)", "Vitamin E (α-Tocopherol)", "Vitamin K1 (Phylloquinone)",
            "Vitamin B1 (Thiamine)", "Vitamin B2 (Riboflavin)", "Vitamin B3 (Niacin)", "Vitamin B6 (Pyridoxine)", "Vitamin B12 (Cobalamin)"
        ],
        "Type": ["Oil"]*6 + ["Solvent"]*8 + ["Carotenoid"]*6 + ["Vitamin"]*7,
        "Density (g/mL)": [
            0.91, 0.92, 0.924, 0.92, 0.91, 0.88,
            0.66, 0.87, 0.789, 0.791, 0.784, 1.48, 1.33, 0.786, 0.944, 1.10, 1.00,
            1.01, 1.06, 1.02, 1.02, 1.07, 1.03, 0.96, 0.95,
            0.96, 1.65, 1.02, 0.95, 1.00, 1.03, 1.33, 1.38, 1.11, 1.34
        ],
        "Refractive Index": [
            1.467, 1.472, 1.448, 1.467, 1.468, 1.449,
            1.375, 1.496, 1.361, 1.328, 1.359, 1.445, 1.424, 1.377, 1.430, 1.479, 1.333,
            1.52, 1.54, 1.47, 1.47, 1.54, 1.50, 1.49, 1.48,
            1.51, 1.56, 1.53, 1.50, 1.55, 1.58, 1.61, 1.62, 1.50, 1.61
        ],
        "MW (g/mol)": [
            None, None, None, None, None, None,
            86.18, 92.14, 46.07, 32.04, 58.08, 119.38, 84.93, 60.10, 73.09, 78.13, 18.02,
            536.87, 536.85, 568.87, 568.87, 596.84, 552.87, 536.88, 536.88,
            286.45, 176.12, 384.64, 430.71, 450.71, 265.35, 376.37, 123.11, 169.18, 1355.37
        ]
    }
    df = pd.DataFrame(data).set_index('Compound')

# --- Display database ---
st.subheader("Database Preview")
st.dataframe(df)

# --- Conversion functions ---
def wt_percent_to_ppm(wt):
    return wt * 10000

def mL_to_g(vol, dens):
    return vol * dens

def g_to_mL(mass, dens):
    return mass / dens if dens else None

# --- UI for converters ---
st.subheader("Converters")
conv = st.selectbox('Select conversion:', ['%wt → ppm', 'mL → g', 'g → mL'])
compound = st.selectbox('Choose a compound for density reference:', df.index)
dens = df.loc[compound, 'Density (g/mL)'] if 'Density (g/mL)' in df.columns else None

if conv == '%wt → ppm':
    wt = st.number_input('Enter % weight (wt%):', min_value=0.0)
    st.write(f"{wt}% wt = {wt_percent_to_ppm(wt):,.1f} ppm")
elif conv == 'mL → g':
    vol = st.number_input('Enter volume (mL):', min_value=0.0)
    st.write(f"{vol} mL × {dens} g/mL = {mL_to_g(vol, dens):,.3f} g")
else:
    mass = st.number_input('Enter mass (g):', min_value=0.0)
    st.write(f"{mass} g ÷ {dens} g/mL = {g_to_mL(mass, dens):,.3f} mL")

st.markdown("---")
st.markdown(
    "**+** Téléverse ton propre CSV pour une base de données illimitée, ou modifie le fichier local `physico_params.csv`."
)
