import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA --- #
st.set_page_config(page_title="Predicción Huevos", layout="wide")
st.title("📈 Predicción de Porcentaje de Huevos por Granja y Lote")

st.markdown("""
Esta aplicación permite visualizar la curva **real** (según datos subidos manualmente) y la **curva proyectada**
(generada previamente mediante un modelo de machine learning).
""")

# --- 1. CARGA MANUAL DEL ARCHIVO REAL (DESDE TU PC) --- #
st.header("📥 Paso 1: Subir archivo real desde SharePoint")

archivo_real = st.file_uploader("Sube el archivo `Libro Verde Reproductoras.xlsx`", type=["xlsx"], key="archivo_real")

if archivo_real is None:
    st.warning("⚠️ Esperando que subas el archivo real desde SharePoint...")
    st.stop()

# --- 2. LEER ARCHIVO REAL --- #
df_reales = pd.read_excel(archivo_real)
df_reales = df_reales[df_reales['Estado'].str.strip().str.capitalize() == 'Abierto']
df_reales = df_reales[['GRANJA', 'LOTE', 'SEMPROD', 'Porcentaje_HuevosTotales']]

# --- 3. CARGA DEL ARCHIVO DE PREDICCIONES (desde el repositorio GitHub) --- #
st.header("📄 Paso 2: Visualización de curvas reales y proyectadas")

try:
    df_pred = pd.read_excel("predicciones_huevos.xlsx")
except FileNotFoundError:
    st.error("❌ No se encontró el archivo `predicciones_huevos.xlsx` en el repositorio.")
    st.stop()

# --- 4. SELECCIÓN DE GRANJA + LOTE --- #
granjas_lotes = df_pred[['GRANJA', 'LOTE']].drop_duplicates()
granjas_lotes['ID'] = granjas_lotes['GRANJA'] + " - " + granjas_lotes['LOTE']

opcion = st.selectbox("Selecciona una Granja + Lote", granjas_lotes['ID'].sort_values())
granja_sel, lote_sel = opcion.split(" - ")

# --- 5. FILTRAR DATOS --- #
reales = df_reales[(df_reales['GRANJA'] == granja_sel) & (df_reales['LOTE'] == lote_sel)].copy()
pred = df_pred[(df_pred['GRANJA'] == granja_sel) & (df_pred['LOTE'] == lote_sel)].copy()

reales = reales[['SEMPROD', 'Porcentaje_HuevosTotales']].rename(columns={'Porcentaje_HuevosTotales': 'Valor'})
reales['Tipo'] = 'Real'

pred = pred[['SEMPROD', 'Prediccion_Porcentaje_HuevosTotales']].rename(columns={'Prediccion_Porcentaje_HuevosTotales': 'Valor'})
pred['Tipo'] = 'Predicción'

df_plot = pd.concat([reales, pred])

# --- 6. GRÁFICO --- #
fig = px.line(df_plot, x='SEMPROD', y='Valor', color='Tipo', markers=True,
              title=f"📊 Granja: {granja_sel} | Lote: {lote_sel}",
              labels={'SEMPROD': 'Semana Productiva', 'Valor': 'Porcentaje Huevos'})

st.plotly_chart(fig, use_container_width=True)
