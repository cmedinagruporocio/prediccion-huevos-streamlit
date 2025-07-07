import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA --- #
st.set_page_config(page_title="Predicción Huevos", layout="wide")
st.title("📈 Predicción de Porcentaje de Huevos por Granja y Lote")

st.markdown("""
Esta aplicación permite visualizar:
- La curva **real** (datos registrados manualmente).
- La curva **proyectada** (modelo híbrido).
- El rango de **incertidumbre** (P5 a P95).
- La curva **estándar promedio** por semana productiva (SEMPROD).
""")

# --- 1. SUBIR ARCHIVO REAL --- #
st.header("📥 Paso 1: Subir archivo real desde SharePoint")

archivo_real = st.file_uploader("Sube el archivo `Libro Verde Reproductoras.xlsx`", type=["xlsx"])

if archivo_real is None:
    st.warning("⚠️ Esperando que subas el archivo real desde SharePoint...")
    st.stop()

# --- 2. LEER DATOS --- #
df_reales = pd.read_excel(archivo_real)
df_reales['Estado'] = df_reales['Estado'].astype(str).str.strip().str.capitalize()
df_reales = df_reales[df_reales['Estado'] == 'Abierto']

# --- 3. LEER PREDICCIONES --- #
try:
    df_pred = pd.read_excel("predicciones_huevos.xlsx")
except FileNotFoundError:
    st.error("❌ No se encontró el archivo `predicciones_huevos.xlsx`.")
    st.stop()

# --- 4. PROMEDIO ESTÁNDAR POR SEMANA --- #
df_estandar = df_reales[['SEMPROD', 'Porcentaje_HuevoTotal_Estandar']].dropna()
promedio_estandar = df_estandar.groupby('SEMPROD')['Porcentaje_HuevoTotal_Estandar'].mean().reset_index()
promedio_estandar = promedio_estandar[promedio_estandar['SEMPROD'] <= 45]

# --- 5. SELECCIÓN DE GRANJA + LOTE --- #
st.header("📄 Paso 2: Visualización de curvas")

granjas_lotes = df_pred[['GRANJA', 'LOTE']].drop_duplicates()
granjas_lotes['ID'] = granjas_lotes['GRANJA'] + " - " + granjas_lotes['LOTE']
opcion = st.selectbox("Selecciona una Granja + Lote", granjas_lotes['ID'].sort_values())
granja_sel, lote_sel = opcion.split(" - ")

# --- 6. FILTRAR DATOS --- #
reales = df_reales[(df_reales['GRANJA'] == granja_sel) & (df_reales['LOTE'] == lote_sel)]
pred = df_pred[(df_pred['GRANJA'] == granja_sel) & (df_pred['LOTE'] == lote_sel)]

# --- 7. GRÁFICO --- #
fig = go.Figure()

# Curva real
fig.add_trace(go.Scatter(
    x=reales['SEMPROD'], y=reales['Porcentaje_HuevosTotales'],
    mode='lines+markers', name='Real', line=dict(color='blue')
))

# Curva predicción
fig.add_trace(go.Scatter(
    x=pred['SEMPROD'], y=pred['Prediccion_Porcentaje_HuevosTotales'],
    mode='lines+markers', name='Predicción', line=dict(color='orange')
))

# Área de incertidumbre
fig.add_trace(go.Scatter(
    x=pred['SEMPROD'], y=pred['P95'],
    mode='lines', name='P95', line=dict(width=0), showlegend=False
))
fig.add_trace(go.Scatter(
    x=pred['SEMPROD'], y=pred['P5'],
    mode='lines', name='P5', line=dict(width=0), fill='tonexty',
    fillcolor='rgba(255,165,0,0.2)', showlegend=True, name='Incertidumbre'
))

# Curva estándar promedio
fig.add_trace(go.Scatter(
    x=promedio_estandar['SEMPROD'], y=promedio_estandar['Porcentaje_HuevoTotal_Estandar'],
    mode='lines+markers', name='Estándar promedio', line=dict(color='green', dash='dash')
))

fig.update_layout(
    title=f"📊 Granja: {granja_sel} | Lote: {lote_sel}",
    xaxis_title="Semana Productiva (SEMPROD)",
    yaxis_title="Porcentaje de Huevos",
    legend_title="Tipo de curva",
    template="plotly_white"
)

st.plotly_chart(fig, use_container_width=True)
