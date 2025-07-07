import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA --- #
st.set_page_config(page_title="Predicción Huevos", layout="wide")
st.title("📈 Predicción de Porcentaje de Huevos por Granja y Lote")

st.markdown("""
Esta aplicación permite visualizar la curva **real**, la **curva proyectada**, la **banda de incertidumbre (P5–P95)**, y el **promedio del estándar** histórico por semana.
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

# --- 3. PROMEDIO DEL ESTÁNDAR POR SEMPROD --- #
df_std = df[['SEMPROD', 'Porcentaje_HuevoTotal_Estandar']].dropna()
df_std['SEMPROD'] = df_std['SEMPROD'].astype(int)

promedio_estandar = (
    df_std.groupby('SEMPROD', as_index=False)
    .agg({'Porcentaje_HuevoTotal_Estandar': 'mean'})
    .rename(columns={'Porcentaje_HuevoTotal_Estandar': 'Estandar'})
)

semanas_1_45 = pd.DataFrame({'SEMPROD': range(1, 46)})
promedio_estandar = semanas_1_45.merge(promedio_estandar, on='SEMPROD', how='left')

# --- 4. FILTRAR LOTES ABIERTOS --- #
df_abiertos = df[df['Estado'] == 'Abierto']
df_abiertos = df_abiertos[['GRANJA', 'LOTE', 'SEMPROD', 'Porcentaje_HuevosTotales']]

# --- 5. CARGAR PREDICCIONES --- #
st.header("📄 Paso 2: Visualización de curvas reales y proyectadas")
try:
    df_pred = pd.read_excel("predicciones_huevos.xlsx")
except FileNotFoundError:
    st.error("❌ No se encontró el archivo `predicciones_huevos.xlsx`.")
    st.stop()

# --- 6. FILTROS: GRANAJA + LOTE --- #
granjas = sorted(df_pred['GRANJA'].unique())
granja_sel = st.selectbox("Selecciona una Granja", granjas)

lotes_disponibles = df_pred[df_pred['GRANJA'] == granja_sel]['LOTE'].unique()
lote_sel = st.selectbox("Selecciona un Lote (o '-- TODOS --')", ["-- TODOS --"] + sorted(lotes_disponibles.tolist()))

# --- 7. FILTRADO DE DATOS --- #
if lote_sel != "-- TODOS --":
    reales = df_abiertos[(df_abiertos['GRANJA'] == granja_sel) & (df_abiertos['LOTE'] == lote_sel)].copy()
    pred = df_pred[(df_pred['GRANJA'] == granja_sel) & (df_pred['LOTE'] == lote_sel)].copy()
    titulo = f"Granja: {granja_sel} | Lote: {lote_sel}"
else:
    st.info(f"Mostrando el promedio general de todos los lotes de la granja **{granja_sel}**.")
    reales = df_abiertos[df_abiertos['GRANJA'] == granja_sel].copy()
    pred = df_pred[df_pred['GRANJA'] == granja_sel].copy()
    reales = reales.groupby('SEMPROD', as_index=False).agg({'Porcentaje_HuevosTotales': 'mean'})
    pred = pred.groupby('SEMPROD', as_index=False).agg({
        'Prediccion_Porcentaje_HuevosTotales': 'mean',
        'P5': 'mean',
        'P95': 'mean'
    })
    titulo = f"Granja: {granja_sel} (Promedio de todos los lotes)"

# --- 8. GRAFICAR --- #
fig = go.Figure()

# Datos reales
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

# Banda de incertidumbre con tooltip personalizado dinámico
x_vals = pd.concat([pred['SEMPROD'], pred['SEMPROD'][::-1]])
y_vals = pd.concat([pred['P95'], pred['P5'][::-1]])

tooltip_text = [
    f"Incertidumbre ({p5:.1f}–{p95:.1f})" for p5, p95 in zip(pred['P5'], pred['P95'])
]
tooltip_text = tooltip_text + tooltip_text[::-1]  # duplicado invertido para cerrar el polígono

fig.add_trace(go.Scatter(
    x=x_vals,
    y=y_vals,
    fill='toself',
    fillcolor='rgba(255,165,0,0.2)',
    line=dict(color='rgba(255,255,255,0)'),
    mode='lines',
    hoverinfo="text",
    text=tooltip_text,
    showlegend=True,
    name='Incertidumbre (P5–P95)'
))


# Línea del estándar (negra continua sin markers, con tooltip personalizado)
fig.add_trace(go.Scatter(
    x=promedio_estandar['SEMPROD'],
    y=promedio_estandar['Estandar'],
    mode='lines',
    name='Estándar',
    line=dict(color='black'),
    hovertemplate='Estándar: %{y:.1f}<extra></extra>'
))

fig.update_layout(
    title=f"📊 {titulo}",
    xaxis_title="Semana Productiva",
    yaxis_title="Porcentaje de Huevos",
    xaxis=dict(tickmode='linear', dtick=1),
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)
