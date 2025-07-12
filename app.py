# --- LIBRERÍAS --- #
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_squared_error
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.user_credential import UserCredential
import io

# --- CONFIGURACIÓN PÁGINA --- #
st.set_page_config(page_title="Predicción Huevos", layout="wide")
st.title("📈 Predicción de Porcentaje de Huevos por Granja y Lote")

st.markdown("""
Esta aplicación permite visualizar la curva **real**, la **curva proyectada**, la **banda de incertidumbre (90%)**, el **promedio del estándar** histórico por semana, el **saldo de hembras**, los **huevos acumulados reales** y los **huevos proyectados**.
""")

# --- CREDENCIALES Y DESCARGA --- #
st.header("🔐 Paso 1: Conectar a SharePoint automáticamente")

if 'archivo_excel' not in st.session_state:
   with st.expander("🔒 Conexión automática a SharePoint", expanded=True):
    st.caption("🔐 Las credenciales se toman de forma segura desde `st.secrets`.")
    usuario = st.secrets["SHAREPOINT_USER"]
    contrasena = st.secrets["SHAREPOINT_PASS"]
    descargar = st.button("📥 Descargar archivo automáticamente")
    if descargar:
        try:
            site_url = "https://gruporocio.sharepoint.com/sites/IDesarrollo"
            ruta_archivo = "/sites/IDesarrollo/Documentos compartidos/Libro Verde/Reproductoras/Libro Verde Reproductoras.xlsx"
            ctx = ClientContext(site_url).with_credentials(UserCredential(usuario, contrasena))
            file_obj = io.BytesIO()
            ctx.web.get_file_by_server_relative_url(ruta_archivo).download(file_obj).execute_query()
            file_obj.seek(0)
            st.session_state['archivo_excel'] = file_obj
            st.success("✅ Archivo descargado correctamente desde SharePoint.")
        except Exception as e:
            st.error(f"❌ Error al conectar o descargar: {e}")
            st.stop()

if 'archivo_excel' not in st.session_state:
    st.warning("⚠️ Aún no se ha cargado el archivo desde SharePoint.")
    st.stop()

archivo_excel = st.session_state['archivo_excel']
df = pd.read_excel(archivo_excel)

# --- LIMPIEZA --- #
df['Estado'] = df['Estado'].astype(str).str.strip().str.capitalize()
df = df.dropna(subset=['Estado', 'Porcentaje_HuevosTotales', 'GRANJA', 'LOTE', 'SEMPROD'])
df['SEMPROD'] = df['SEMPROD'].astype(int)

# --- PROMEDIO ESTÁNDAR --- #
df_std = df[['SEMPROD', 'Porcentaje_HuevoTotal_Estandar']].dropna()
df_std['SEMPROD'] = df_std['SEMPROD'].astype(int)
promedio_estandar = (
    df_std.groupby('SEMPROD', as_index=False)
    .agg({'Porcentaje_HuevoTotal_Estandar': 'mean'})
    .rename(columns={'Porcentaje_HuevoTotal_Estandar': 'Estandar'})
)
semanas_1_45 = pd.DataFrame({'SEMPROD': range(1, 46)})
promedio_estandar = semanas_1_45.merge(promedio_estandar, on='SEMPROD', how='left')

# --- ENTRENAMIENTO CON LOTES CERRADOS --- #
df_cerrados = df[df['Estado'] == 'Cerrado'].copy()
X_train = df_cerrados[['SEMPROD']]
y_train = df_cerrados['Porcentaje_HuevosTotales']
modelo_general = RandomForestRegressor(n_estimators=100, random_state=42)
modelo_general.fit(X_train, y_train)

# --- PREDICCIÓN PARA LOTES ABIERTOS --- #
df_abiertos = df[df['Estado'] == 'Abierto'].copy()
df_pred_final = []
for (granja, lote), grupo in df_abiertos.groupby(['GRANJA', 'LOTE']):
    grupo = grupo.sort_values('SEMPROD').copy()
    if grupo['SEMPROD'].max() < 10:
        continue
    X_observado = grupo[['SEMPROD']]
    y_real = grupo['Porcentaje_HuevosTotales']
    y_modelo = modelo_general.predict(X_observado)
    bias = (y_real - y_modelo).mean()

    # Segmento 3: caída
    idx_pico = grupo['Porcentaje_HuevosTotales'].idxmax()
    semana_pico = grupo.loc[idx_pico, 'SEMPROD']
    corte_2 = semana_pico + 2
    seg3 = grupo[grupo['SEMPROD'] > corte_2]
    if len(seg3) < 2:
        continue
    modelo_3 = LinearRegression().fit(seg3[['SEMPROD']], seg3['Porcentaje_HuevosTotales'])

    r2 = r2_score(seg3['Porcentaje_HuevosTotales'], modelo_3.predict(seg3[['SEMPROD']]))
    rmse = mean_squared_error(seg3['Porcentaje_HuevosTotales'], modelo_3.predict(seg3[['SEMPROD']]), squared=False)

    semana_max = grupo['SEMPROD'].max()
    semanas_futuras = np.arange(semana_max + 1, 46).reshape(-1, 1)
    pred_ml = modelo_general.predict(semanas_futuras) + bias
    pred_regresion = modelo_3.predict(semanas_futuras)
    final_pred = 0.4 * pred_ml + 0.6 * pred_regresion

    desviacion = np.std(grupo.tail(5)['Porcentaje_HuevosTotales'])
    escalado = np.linspace(1.5, 2.5, len(semanas_futuras))
    P5 = np.clip(final_pred - desviacion * escalado, 0, final_pred)
    P95 = np.clip(final_pred + desviacion * escalado, final_pred, None)

    df_temp = pd.DataFrame({
        'GRANJA': granja,
        'LOTE': lote,
        'SEMPROD': semanas_futuras.flatten(),
        'Prediccion_Porcentaje_HuevosTotales': final_pred,
        'P5': P5,
        'P95': P95,
        'R2_Caida': r2,
        'RMSE_Caida': rmse
    })
    df_pred_final.append(df_temp)

if not df_pred_final:
    st.warning("⚠️ No se generaron predicciones. Verifica si hay datos suficientes.")
    st.stop()

df_pred = pd.concat(df_pred_final, ignore_index=True)

# --- VISUALIZACIÓN --- #
st.header("📊 Paso 2: Visualización")
df_abiertos = df_abiertos[['GRANJA', 'LOTE', 'SEMPROD', 'Porcentaje_HuevosTotales', 'Saldo_Hembras', 'HuevosTotales_Acumulado']]
granjas = sorted(df_pred['GRANJA'].unique())
granja_sel = st.selectbox("Selecciona una Granja", granjas)
lotes = df_pred[df_pred['GRANJA'] == granja_sel]['LOTE'].unique()
lote_sel = st.selectbox("Selecciona un Lote (o '-- TODOS --')", ["-- TODOS --"] + sorted(lotes.tolist()))

# --- PROCESAMIENTO Y GRÁFICO --- #
if lote_sel != "-- TODOS --":
    reales = df_abiertos[(df_abiertos['GRANJA'] == granja_sel) & (df_abiertos['LOTE'] == lote_sel)].copy()
    pred = df_pred[(df_pred['GRANJA'] == granja_sel) & (df_pred['LOTE'] == lote_sel)].copy()
    titulo = f"{granja_sel} | {lote_sel}"
    r2_val = pred['R2_Caida'].iloc[0]
    rmse_val = pred['RMSE_Caida'].iloc[0]
    sub = f"R²: {r2_val:.3f} | RMSE: {rmse_val:.2f}"
else:
    reales = df_abiertos[df_abiertos['GRANJA'] == granja_sel].copy()
    lotes_validos = reales.groupby(['GRANJA', 'LOTE']).filter(lambda x: len(x) >= 10)
    reales = lotes_validos.groupby('SEMPROD', as_index=False).agg({
        'Porcentaje_HuevosTotales': 'mean',
        'Saldo_Hembras': 'sum',
        'HuevosTotales_Acumulado': 'sum'
    })
    pred = df_pred[df_pred['GRANJA'] == granja_sel]
    pred = pred[pred['LOTE'].isin(lotes_validos['LOTE'].unique())]
    pred = pred.groupby('SEMPROD', as_index=False).agg({
        'Prediccion_Porcentaje_HuevosTotales': 'mean',
        'P5': 'mean',
        'P95': 'mean'
    })
    titulo = f"{granja_sel} (Promedio de lotes con ≥10 semanas)"
    sub = ""

# --- Regresión saldo hembras --- #
regresion = None
if 'Saldo_Hembras' in reales.columns and len(reales) >= 5:
    modelo = LinearRegression().fit(reales[['SEMPROD']], reales['Saldo_Hembras'])
    semanas_pred = np.arange(1, 46).reshape(-1, 1)
    saldo_pred = modelo.predict(semanas_pred)
    regresion = pd.DataFrame({'SEMPROD': semanas_pred.flatten(), 'Saldo_Hembras_Pred': saldo_pred})

# --- Huevos proyectados --- #
huevos_proj = []
if regresion is not None and not pred.empty:
    saldo_pred = regresion.set_index('SEMPROD')['Saldo_Hembras_Pred']
    prev_total = reales['HuevosTotales_Acumulado'].dropna().max()
    for idx, row in pred.iterrows():
        semana = row['SEMPROD']
        porcentaje = row['Prediccion_Porcentaje_HuevosTotales'] / 100
        saldo = saldo_pred.get(semana, np.nan)
        incremento = porcentaje * saldo * 7 if not np.isnan(saldo) else 0
        prev_total = prev_total + incremento if not np.isnan(prev_total) else incremento
        huevos_proj.append(prev_total)
    pred['Huevos_Proyectado'] = huevos_proj

# --- GRÁFICO FINAL --- #
fig = go.Figure()

fig.add_trace(go.Scatter(x=reales['SEMPROD'], y=reales['Porcentaje_HuevosTotales'],
    mode='lines+markers+text', name='Real', line=dict(color='blue'),
    text=[f"{v:.1f}%" for v in reales['Porcentaje_HuevosTotales']], textposition="top center"))

fig.add_trace(go.Scatter(x=pred['SEMPROD'], y=pred['Prediccion_Porcentaje_HuevosTotales'],
    mode='lines+markers+text', name='Predicción', line=dict(color='orange'),
    text=[f"{v:.1f}%" for v in pred['Prediccion_Porcentaje_HuevosTotales']], textposition="top center"))

fig.add_trace(go.Scatter(x=pd.concat([pred['SEMPROD'], pred['SEMPROD'][::-1]]),
    y=pd.concat([pred['P95'], pred['P5'][::-1]]), fill='toself', fillcolor='rgba(255,165,0,0.2)',
    line=dict(color='rgba(255,255,255,0)'), name='Incertidumbre (90%)', yaxis='y1'))

fig.add_trace(go.Scatter(x=promedio_estandar['SEMPROD'], y=promedio_estandar['Estandar'],
    mode='lines', name='Estándar', line=dict(color='black')))

fig.add_trace(go.Scatter(x=reales['SEMPROD'], y=reales['Saldo_Hembras'],
    mode='lines+markers', name='Saldo Hembras', line=dict(color='purple'), yaxis='y2'))

if regresion is not None:
    fig.add_trace(go.Scatter(x=regresion['SEMPROD'], y=regresion['Saldo_Hembras_Pred'],
        mode='lines', name='Tendencia Saldo Hembras', line=dict(color='red', dash='dash'), yaxis='y2'))

fig.add_trace(go.Scatter(x=reales['SEMPROD'], y=reales['HuevosTotales_Acumulado'],
    mode='lines+markers+text', name='Huevos Acumulados (Reales)',
    line=dict(color='green', width=2), textposition="bottom center", yaxis='y3'))

if 'Huevos_Proyectado' in pred.columns:
    fig.add_trace(go.Scatter(x=pred['SEMPROD'], y=pred['Huevos_Proyectado'],
        mode='lines+markers+text', name='Huevos Proyectados',
        line=dict(color='darkgreen', width=2, dash='dot'), yaxis='y3'))

fig.update_layout(
    title=dict(text=f"{titulo}<br><sub>{sub}</sub>", x=0.01, xanchor='left'),
    xaxis_title="Semana Productiva",
    yaxis=dict(title="Porcentaje de Huevos", tickformat=".1f"),
    yaxis2=dict(title="Saldo Hembras", overlaying='y', side='right', showgrid=False),
    yaxis3=dict(overlaying='y', side='right', visible=False),
    xaxis=dict(tickmode='linear', dtick=1),
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)
