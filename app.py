import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA --- #
st.set_page_config(page_title="Predicción Huevos", layout="wide")
st.title("📈 Predicción de Porcentaje de Huevos por Granja y Lote")

st.markdown("""
Esta aplicación permite visualizar la curva **real**, la **curva proyectada** y la **banda de incertidumbre (P5–P95)**, junto con el **promedio del estándar** histórico por semana.
""")

# --- 1. CARGA MANUAL DEL ARCHIVO REAL --- #
st.header("📥 Paso 1: Subir archivo real desde SharePoint")
archivo_real = st.file_uploader("Sube el archivo `Libro Verde Reproductoras.xlsx`", type=["xlsx"])

if archivo_real is None:
    st.warning("⚠️ Esperando que subas el archivo real desde SharePoint...")
    st.stop()

# --- 2. LEER DATOS REALES --- #
df = pd.read_excel(archivo_real)
df['Estado'] = df['Estado'].astype(str).str.strip().str.capitalize()
df = df.dropna(subset=['Estado', 'Porcentaje_HuevosTotales', 'GRANJA', 'LOTE', 'SEMPROD'])
df['SEMPROD'] = df['SEMPROD'].astype(int)

# --- 3. GENERAR ESTÁNDAR PROMEDIO POR SEMANA (SEM PROD 1-45) --- #
df_std = df[['SEMPROD', 'Porcentaje_HuevoTotal_Estandar']].dropna()
df_std['SEMPROD'] = df_std['SEMPROD'].astype(int)

promedio_estandar = (
    df_std.groupby('SEMPROD', as_index=False)
    .agg({'Porcentaje_HuevoTotal_Estandar': 'mean'})
    .rename(columns={'Porcentaje_HuevoTotal_Estandar': 'Estandar'})
)

# Asegurar semanas 1 a 45
semanas_1_45 = pd.DataFrame({'SEMPROD': range(1, 46)})
promedio_estandar = semanas_1_45.merge(promedio_estandar, on='SEMPROD', how='left')

# --- 4. FILTRAR DATOS ABIERTOS --- #
df_abiertos = df[df['Estado'] == 'Abierto']
df_abiertos = df_abiertos[['GRANJA', 'LOTE', 'SEMPROD', 'Porcentaje_HuevosTotales']]

# --- 5. CARGAR PREDICCIONES --- #
st.header("📄 Paso 2: Visualización de curvas reales y proyectadas")
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

# --- 7. FILTRAR DATOS SELECCIONADOS --- #
reales = df_abiertos[(df_abiertos['GRANJA'] == granja_sel) & (df_abiertos['LOTE'] == lote_sel)].copy()
pred = df_pred[(df_pred['GRANJA'] == granja_sel) & (df_pred['LOTE'] == lote_sel)].copy()

# --- 8. GRAFICAR --- #
fig = go.Figure()

# Línea de datos reales
fig.add_trace(go.Scatter(
    x=reales['SEMPROD'], 
    y=reales['Porcentaje_HuevosTotales'],
    mode='lines+markers', 
    name='Real', 
    line=dict(color='blue')
))

# Línea de predicción
fig.add_trace(go.Scatter(
    x=pred['SEMPROD'], 
    y=pred['Prediccion_Porcentaje_HuevosTotales'],
    mode='lines+markers', 
    name='Predicción', 
    line=dict(color='orange')
))

# Banda de incertidumbre (P5–P95) con tooltip personalizado
fig.add_trace(go.Scatter(
    x=pd.concat([pred['SEMPROD'], pred['SEMPROD'][::-1]]),
    y=pd.concat([pred['P95'], pred['P5'][::-1]]),
    fill='toself',
    fillcolor='rgba(255,165,0,0.2)',
    line=dict(color='rgba(255,255,255,0)'),
    name='Incertidumbre (P5–P95)',
    hoverinfo='text',
    showlegend=True,
    text=[
        f"Incertidumbre ({round(p5,1)}–{round(p95,1)})"
        for p5, p95 in zip(pred['P5'], pred['P95'])
    ] + [
        f"Incertidumbre ({round(p5,1)}–{round(p95,1)})"
        for p5, p95 in zip(pred['P5'][::-1], pred['P95'][::-1])
    ]
))

# Línea del estándar promedio (línea negra continua sin markers)
fig.add_trace(go.Scatter(
    x=promedio_estandar['SEMPROD'],
    y=promedio_estandar['Estandar'],
    mode='lines',
    name='Estándar Promedio',
    line=dict(color='black')
))

# Layout
fig.update_layout(
    title=f"📊 Granja: {granja_sel} | Lote: {lote_sel}",
    xaxis_title="Semana Productiva",
    yaxis_title="Porcentaje de Huevos",
    xaxis=dict(tickmode='linear', dtick=1),
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)
