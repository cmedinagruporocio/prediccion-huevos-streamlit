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
    st.warning("\u26a0\ufe0f Esperando que subas el archivo real desde SharePoint...")
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
    titulo_principal = f"📊 Granja: {granja_sel} | Lote: {lote_sel}"
    if not pred.empty and 'R2_Caida' in pred.columns:
        r2_val = pred['R2_Caida'].iloc[0]
        rmse_val = pred['RMSE_Caida'].iloc[0]
        titulo_secundario = f"R²: {r2_val:.3f} | RMSE: {rmse_val:.2f}"
    else:
        titulo_secundario = ""

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
else:
    st.info(f"Mostrando el total acumulado de proyecciones por lotes de la granja **{granja_sel}**.")

    reales_granja = df_abiertos[df_abiertos['GRANJA'] == granja_sel].copy()
    lotes_validos = reales_granja.groupby(['GRANJA', 'LOTE']).filter(lambda x: len(x) >= 10)
    reales = lotes_validos.groupby('SEMPROD', as_index=False).agg({
        'Porcentaje_HuevosTotales': 'mean',
        'Saldo_Hembras': 'sum',
        'HuevosTotales_Acumulado': 'sum'
    })

    pred_lotes_validos = df_pred[(df_pred['GRANJA'] == granja_sel) & (df_pred['LOTE'].isin(lotes_validos['LOTE'].unique()))].copy()

    # Calcular proyección de huevos totales acumulados sumando por lote
    proy_acum = []
    for semana in range(1, 46):
        semana_lotes = pred_lotes_validos[pred_lotes_validos['SEMPROD'] == semana]
        total = 0
        for _, row in semana_lotes.iterrows():
            porcentaje = row['Prediccion_Porcentaje_HuevosTotales'] / 100
            saldo = row['Saldo_Hembras_Pred'] if 'Saldo_Hembras_Pred' in row else np.nan
            if not np.isnan(porcentaje) and not np.isnan(saldo):
                total += porcentaje * saldo * 7
        proy_acum.append(total if semana == 1 else proy_acum[-1] + total)

    pred = pred_lotes_validos.groupby('SEMPROD', as_index=False).agg({
        'Prediccion_Porcentaje_HuevosTotales': 'mean',
        'P5': 'mean',
        'P95': 'mean'
    })
    pred['Huevos_Proyectado'] = proy_acum

    titulo_principal = f"📊 Granja: {granja_sel} (Suma de proyecciones por lote)"
    titulo_secundario = ""
    regresion = None

# --- continúa con gráfico --- #
