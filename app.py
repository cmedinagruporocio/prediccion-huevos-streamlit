import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA --- #
st.set_page_config(page_title="Predicción Huevos", layout="wide")
st.title("📈 Predicción de Porcentaje de Huevos por Granja y Lote")

st.markdown("""
Esta aplicación permite visualizar la curva **real** (según datos subidos manualmente), 
la **curva proyectada** (generada por modelo de ML adaptativo) y una curva **estándar** promedio.
""")

# --- 1. CARGA DEL ARCHIVO REAL --- #
st.header("📥 Paso 1: Subir archivo real desde SharePoint")

archivo_real = st.file_uploader("Sube el archivo `Libro Verde Reproductoras.xlsx`", type=["xlsx"], key="archivo_real")

if archivo_real is None:
    st.warning("⚠️ Esperando que subas el archivo real desde SharePoint...")
    st.stop()

# --- 2. LEER ARCHIVO REAL --- #
df_reales = pd.read_excel(archivo_real)
df_reales['Estado'] = df_reales['Estado'].astype(str).str.strip().str.capitalize()
df_reales = df_reales[df_reales['Estado'] == 'Abierto']
df_reales = df_reales[['GRANJA', 'LOTE', 'SEMPROD', 'Porcentaje_HuevosTotales', 'Porcentaje_HuevoTotal_Estandar']]

# --- 3. CARGA DEL ARCHIVO DE PREDICCIONES --- #
st.header("📄 Paso 2: Visualización de curvas reales, proyectadas y estándar")

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

# --- 6. CURVA ESTÁNDAR PROMEDIO GLOBAL --- #
semanas_1_45 = pd.DataFrame({'SEMPROD': range(1, 46)})

df_estandar = df_reales.groupby('SEMPROD')['Porcentaje_HuevoTotal_Estandar'].mean().reset_index()
df_estandar = semanas_1_45.merge(df_estandar, on='SEMPROD', how='left')

df_estandar['Valor'] = df_estandar['Porcentaje_HuevoTotal_Estandar']
df_estandar.drop(columns=['Porcentaje_HuevoTotal_Estandar'], inplace=True)
df_estandar['Tipo'] = 'Estándar'

# Rellenar valores faltantes si los hay
df_estandar['Valor'] = df_estandar['Valor'].interpolate().fillna(method='bfill')

# --- 7. COMBINAR Y GRAFICAR --- #
df_plot = pd.concat([reales, pred, df_estandar], ignore_index=True)

fig = px.line(df_plot, x='SEMPROD', y='Valor', color='Tipo', markers=True,
              title=f"📊 Granja: {granja_sel} | Lote: {lote_sel}",
              labels={'SEMPROD': 'Semana Productiva', 'Valor': 'Porcentaje Huevos'})

fig.update_layout(xaxis=dict(dtick=1))

st.plotly_chart(fig, use_container_width=True)
