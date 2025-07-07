import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA --- #
st.set_page_config(page_title="Predicción Huevos", layout="wide")
st.title("📈 Predicción de Porcentaje de Huevos por Granja y Lote")

st.markdown("""
Esta aplicación permite visualizar la curva **real**, la curva **proyectada** mediante modelo híbrido, y el 
**estándar promedio semanal** calculado globalmente por semana productiva.
""")

# --- 1. CARGA DEL ARCHIVO REAL --- #
st.header("📥 Paso 1: Subir archivo real desde SharePoint")

archivo_real = st.file_uploader("Sube el archivo `Libro Verde Reproductoras.xlsx`", type=["xlsx"], key="archivo_real")

if archivo_real is None:
    st.warning("⚠️ Esperando que subas el archivo real desde SharePoint...")
    st.stop()

# --- 2. LEER ARCHIVO REAL COMPLETO --- #
df_total = pd.read_excel(archivo_real)
df_total['Estado'] = df_total['Estado'].astype(str).str.strip().str.capitalize()
df_total = df_total.dropna(subset=['GRANJA', 'LOTE', 'SEMPROD', 'Porcentaje_HuevosTotales', 'Porcentaje_HuevoTotal_Estandar'])

# --- 3. CALCULAR PROMEDIO DE ESTÁNDAR POR SEMPROD --- #
df_estandar_promedio = (
    df_total
    .groupby('SEMPROD')['Porcentaje_HuevoTotal_Estandar']
    .mean()
    .reset_index()
    .rename(columns={'Porcentaje_HuevoTotal_Estandar': 'Valor'})
)
df_estandar_promedio['Tipo'] = 'Estándar Promedio'

# --- 4. FILTRAR ABIERTOS Y REDUCIR COLUMNAS --- #
df_reales = df_total[df_total['Estado'] == 'Abierto']
df_reales = df_reales[['GRANJA', 'LOTE', 'SEMPROD', 'Porcentaje_HuevosTotales']]

# --- 5. CARGA DEL ARCHIVO DE PREDICCIONES --- #
st.header("📄 Paso 2: Visualización de curvas")

try:
    df_pred = pd.read_excel("predicciones_huevos.xlsx")
except FileNotFoundError:
    st.error("❌ No se encontró el archivo `predicciones_huevos.xlsx`.")
    st.stop()

# --- 6. SELECCIÓN DE GRANJA + LOTE --- #
granjas_lotes = df_pred[['GRANJA', 'LOTE']].drop_duplicates()
granjas_lotes['ID'] = granjas_lotes['GRANJA'] + " - " + granjas_lotes['LOTE']

opcion = st.selectbox("Selecciona una Granja + Lote", granjas_lotes['ID'].sort_values())
granja_sel, lote_sel = opcion.split(" - ")

# --- 7. FILTRAR DATOS --- #
reales = df_reales[(df_reales['GRANJA'] == granja_sel) & (df_reales['LOTE'] == lote_sel)].copy()
pred = df_pred[(df_pred['GRANJA'] == granja_sel) & (df_pred['LOTE'] == lote_sel)].copy()

# Curva real
reales_plot = reales[['SEMPROD', 'Porcentaje_HuevosTotales']].rename(columns={'Porcentaje_HuevosTotales': 'Valor'})
reales_plot['Tipo'] = 'Real'

# Curva predicción
pred_plot = pred[['SEMPROD', 'Prediccion_Porcentaje_HuevosTotales']].rename(columns={'Prediccion_Porcentaje_HuevosTotales': 'Valor'})
pred_plot['Tipo'] = 'Predicción'

# --- 8. CONCATENAR Y GRAFICAR --- #
df_plot = pd.concat([reales_plot, pred_plot, df_estandar_promedio], ignore_index=True)

fig = px.line(
    df_plot,
    x='SEMPROD',
    y='Valor',
    color='Tipo',
    markers=True,
    title=f"📊 Granja: {granja_sel} | Lote: {lote_sel}",
    labels={'SEMPROD': 'Semana Productiva', 'Valor': 'Porcentaje Huevos'}
)

st.plotly_chart(fig, use_container_width=True)
