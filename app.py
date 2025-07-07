import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA --- #
st.set_page_config(page_title="Predicción Huevos", layout="wide")
st.title("📈 Predicción de Porcentaje de Huevos por Granja y Lote")

st.markdown("""
Esta aplicación permite visualizar la curva **real** (según datos subidos manualmente) y la **curva proyectada**
(generada previamente mediante un modelo híbrido de machine learning + regresión local).
También se incluye una **banda de incertidumbre** (percentiles 25 y 75).
""")

# --- 1. CARGA MANUAL DEL ARCHIVO REAL --- #
st.header("📥 Paso 1: Subir archivo real desde SharePoint")
archivo_real = st.file_uploader("Sube el archivo `Libro Verde Reproductoras.xlsx`", type=["xlsx"], key="archivo_real")

if archivo_real is None:
    st.warning("⚠️ Esperando que subas el archivo real desde SharePoint...")
    st.stop()

# --- 2. LEER ARCHIVO REAL --- #
df_reales = pd.read_excel(archivo_real)
df_reales = df_reales[df_reales['Estado'].str.strip().str.capitalize() == 'Abierto']
df_reales = df_reales[['GRANJA', 'LOTE', 'SEMPROD', 'Porcentaje_HuevosTotales']]

# --- 3. CARGA DEL ARCHIVO DE PREDICCIONES --- #
st.header("📄 Paso 2: Visualización de curvas reales y proyectadas")

try:
    df_pred = pd.read_excel("predicciones_huevos.xlsx")
except FileNotFoundError:
    st.error("❌ No se encontró el archivo `predicciones_huevos.xlsx`.")
    st.stop()

# --- 4. SELECCIÓN DE GRANJA + LOTE --- #
granjas_lotes = df_pred[['GRANJA', 'LOTE']].drop_duplicates()
granjas_lotes['ID'] = granjas_lotes['GRANJA'] + " - " + granjas_lotes['LOTE']

opcion = st.selectbox("Selecciona una Granja + Lote", granjas_lotes['ID'].sort_values())
granja_sel, lote_sel = opcion.split(" - ")

# --- 5. FILTRAR DATOS --- #
reales = df_reales[(df_reales['GRANJA'] == granja_sel) & (df_reales['LOTE'] == lote_sel)].copy()
pred = df_pred[(df_pred['GRANJA'] == granja_sel) & (df_pred['LOTE'] == lote_sel)].copy()

# --- 6. GRAFICAR CON BANDA DE INCERTIDUMBRE --- #
fig = go.Figure()

# Curva real
fig.add_trace(go.Scatter(
    x=reales['SEMPROD'],
    y=reales['Porcentaje_HuevosTotales'],
    mode='lines+markers',
    name='Real',
    line=dict(color='blue')
))

# Curva proyectada
fig.add_trace(go.Scatter(
    x=pred['SEMPROD'],
    y=pred['Prediccion_Porcentaje_HuevosTotales'],
    mode='lines+markers',
    name='Predicción',
    line=dict(color='orange')
))

# Banda de incertidumbre
fig.add_trace(go.Scatter(
    x=pred['SEMPROD'],
    y=pred['P95'],
    mode='lines',
    name='P95 (límite superior)',
    line=dict(width=0),
    showlegend=False
))
fig.add_trace(go.Scatter(
    x=pred['SEMPROD'],
    y=pred['P5'],
    mode='lines',
    name='P5 (límite inferior)',
    fill='tonexty',
    fillcolor='rgba(255,165,0,0.2)',
    line=dict(width=0),
    showlegend=True
))

# Layout
fig.update_layout(
    title=f"📊 Granja: {granja_sel} | Lote: {lote_sel}",
    xaxis_title='Semana Productiva (SEMPROD)',
    yaxis_title='Porcentaje Huevos',
    hovermode='x unified'
)

st.plotly_chart(fig, use_container_width=True)
