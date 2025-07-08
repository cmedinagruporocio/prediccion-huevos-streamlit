import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
import numpy as np

# --- CONFIGURACIÓN DE PÁGINA --- #
st.set_page_config(page_title="Predicción Huevos", layout="wide")
st.title("\U0001F4C8 Predicción de Porcentaje de Huevos por Granja y Lote")

st.markdown("""
Esta aplicación permite visualizar la curva **real**, la **curva proyectada**, la **banda de incertidumbre (90%)**, el **promedio del estándar** histórico por semana, el **saldo de hembras** (eje secundario), los **huevos acumulados reales** y los **huevos proyectados**.
""")

# --- 1. CARGA MANUAL DEL ARCHIVO REAL --- #
st.header("\U0001F4C5 Paso 1: Subir archivo real desde SharePoint")
archivo_real = st.file_uploader("Sube el archivo Libro Verde Reproductoras.xlsx", type=["xlsx"])

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
df_abiertos = df_abiertos[['GRANJA', 'LOTE', 'SEMPROD', 'Porcentaje_HuevosTotales', 'Saldo_Hembras', 'HuevosTotales_Acumulado']]

# --- 5. CARGAR PREDICCIONES --- #
st.header("\U0001F4C4 Paso 2: Visualización de curvas reales y proyectadas")
try:
    df_pred = pd.read_excel("predicciones_huevos.xlsx")
except FileNotFoundError:
    st.error("❌ No se encontró el archivo predicciones_huevos.xlsx.")
    st.stop()

# --- 6. FILTROS: GRANJA + LOTE --- #
granjas = sorted(df_pred['GRANJA'].unique())
granja_sel = st.selectbox("Selecciona una Granja", granjas)

lotes_disponibles = df_pred[df_pred['GRANJA'] == granja_sel]['LOTE'].unique()
lote_sel = st.selectbox("Selecciona un Lote (o '-- TODOS --')", ["-- TODOS --"] + sorted(lotes_disponibles.tolist()))

# --- 7. FILTRADO DE DATOS --- #
if lote_sel != "-- TODOS --":
    reales = df_abiertos[(df_abiertos['GRANJA'] == granja_sel) & (df_abiertos['LOTE'] == lote_sel)].copy()
    pred = df_pred[(df_pred['GRANJA'] == granja_sel) & (df_pred['LOTE'] == lote_sel)].copy()
    titulo = f"Granja: {granja_sel} | Lote: {lote_sel}"

    # --- 7.1 Mostrar métricas de regresión si hay datos --- #
    if not pred.empty and 'R2_Caida' in pred.columns and 'RMSE_Caida' in pred.columns:
        r2_val = pred['R2_Caida'].iloc[0]
        rmse_val = pred['RMSE_Caida'].iloc[0]
        col1, col2 = st.columns(2)
        col1.metric("\U0001F50E R² de Caída", f"{r2_val:.3f}")
        col2.metric("\U0001F4C9 RMSE de Caída", f"{rmse_val:.3f}")

else:
    st.info(f"Mostrando el promedio general de todos los lotes de la granja **{granja_sel}**.")
    reales = df_abiertos[df_abiertos['GRANJA'] == granja_sel].copy()
    pred = df_pred[df_pred['GRANJA'] == granja_sel].copy()
    reales = reales.groupby('SEMPROD', as_index=False).agg({
        'Porcentaje_HuevosTotales': 'mean',
        'Saldo_Hembras': 'sum',
        'HuevosTotales_Acumulado': 'sum'
    })
    pred = pred.groupby('SEMPROD', as_index=False).agg({
        'Prediccion_Porcentaje_HuevosTotales': 'mean',
        'P5': 'mean',
        'P95': 'mean'
    })
    titulo = f"Granja: {granja_sel} (Promedio de todos los lotes)"

# --- 8. REGRESIÓN LINEAL DE SALDO HEMBRAS --- #
regresion = None
if 'Saldo_Hembras' in reales.columns and len(reales) >= 5:
    df_temp = reales.dropna(subset=['Saldo_Hembras'])
    X_reg = df_temp[['SEMPROD']]
    y_reg = df_temp['Saldo_Hembras']
    if len(X_reg) >= 5:
        modelo = LinearRegression().fit(X_reg, y_reg)
        semanas_pred = np.arange(1, 46).reshape(-1, 1)
        saldo_pred = modelo.predict(semanas_pred)
        regresion = pd.DataFrame({'SEMPROD': semanas_pred.flatten(), 'Saldo_Hembras_Pred': saldo_pred})

# --- 9. CALCULAR HUEVOS PROYECTADOS --- #
huevos_proj = []
if regresion is not None and not pred.empty:
    saldo_pred = regresion.set_index('SEMPROD')['Saldo_Hembras_Pred']
    prev_total = reales['HuevosTotales_Acumulado'].dropna().max()
    for idx, row in pred.iterrows():
        semana = row['SEMPROD']
        porcentaje = row['Prediccion_Porcentaje_HuevosTotales'] / 100
        saldo = saldo_pred.get(semana, np.nan)
        if np.isnan(porcentaje) or np.isnan(saldo):
            huevos_proj.append(np.nan)
            continue
        incremento = porcentaje * saldo * 7
        prev_total = prev_total + incremento if not np.isnan(prev_total) else incremento
        huevos_proj.append(prev_total)
    pred['Huevos_Proyectado'] = huevos_proj

# --- 10. GRAFICAR --- #
fig = go.Figure()

# Curva real
fig.add_trace(go.Scatter(
    x=reales['SEMPROD'], y=reales['Porcentaje_HuevosTotales'],
    mode='lines+markers', name='Real',
    line=dict(color='blue'), yaxis='y1'
))

# Curva predicha
fig.add_trace(go.Scatter(
    x=pred['SEMPROD'], y=pred['Prediccion_Porcentaje_HuevosTotales'],
    mode='lines+markers', name='Predicción',
    line=dict(color='orange'), yaxis='y1'
))

# Banda de incertidumbre
fig.add_trace(go.Scatter(
    x=pd.concat([pred['SEMPROD'], pred['SEMPROD'][::-1]]),
    y=pd.concat([pred['P95'], pred['P5'][::-1]]),
    fill='toself', fillcolor='rgba(255,165,0,0.2)',
    line=dict(color='rgba(255,255,255,0)'),
    hoverinfo="skip", showlegend=True,
    name='Incertidumbre (90%)', yaxis='y1'
))

# Estándar promedio
fig.add_trace(go.Scatter(
    x=promedio_estandar['SEMPROD'], y=promedio_estandar['Estandar'],
    mode='lines', name='Estándar', line=dict(color='black'), yaxis='y1'
))

# Saldo hembras real
fig.add_trace(go.Scatter(
    x=reales['SEMPROD'], y=reales['Saldo_Hembras'],
    mode='lines+markers', name='Saldo Hembras',
    line=dict(color='purple'), yaxis='y2'
))

# Tendencia de saldo hembras
if regresion is not None:
    fig.add_trace(go.Scatter(
        x=regresion['SEMPROD'], y=regresion['Saldo_Hembras_Pred'],
        mode='lines', name='Tendencia Saldo Hembras',
        line=dict(color='red', dash='dash'), yaxis='y2'
    ))

# Huevos acumulados reales
fig.add_trace(go.Scatter(
    x=reales['SEMPROD'], y=reales['HuevosTotales_Acumulado'],
    mode='lines+markers+text',
    name='Huevos Acumulados (Reales)',
    line=dict(color='green', width=2),
    text=[f"{val:,.0f}" for val in reales['HuevosTotales_Acumulado']],
    textposition="top right",
    hovertemplate='Acumulado Real: %{y:,.0f}<extra></extra>',
    yaxis='y3'
))

# Huevos proyectados
if 'Huevos_Proyectado' in pred.columns:
    fig.add_trace(go.Scatter(
        x=pred['SEMPROD'], y=pred['Huevos_Proyectado'],
        mode='lines+markers+text',
        name='Huevos Proyectados',
        line=dict(color='darkgreen', width=2, dash='dot'),
        text=[f"{val:,.0f}" for val in pred['Huevos_Proyectado']],
        textposition="top right",
        hovertemplate='Proyectado: %{y:,.0f}<extra></extra>',
        yaxis='y3'
    ))

# Layout final
fig.update_layout(
    title=f"\U0001F4CA {titulo}",
    xaxis_title="Semana Productiva",
    yaxis=dict(title="Porcentaje de Huevos", tickformat=".1f"),
    yaxis2=dict(title="Saldo Hembras", overlaying='y', side='right', showgrid=False),
    yaxis3=dict(overlaying='y', side='right', visible=False),
    xaxis=dict(tickmode='linear', dtick=1),
    hovermode="x unified",
    legend=dict(
        x=0.01, y=0.98,
        xanchor='left',
        bgcolor='rgba(255,255,255,0.8)',
        bordercolor='gray',
        borderwidth=1
    )
)

st.plotly_chart(fig, use_container_width=True)
