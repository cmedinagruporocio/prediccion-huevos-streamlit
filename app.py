import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA --- #
st.set_page_config(page_title="Predicción Huevos", layout="wide")
st.title("📈 Predicción de Porcentaje de Huevos por Granja y Lote")

st.markdown("""
Esta aplicación permite visualizar la curva **real** (según datos subidos manualmente), la **curva proyectada**
(generada mediante un modelo de machine learning) y la curva **estándar promedio** por SEMPROD.
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

# Asegurar columnas necesarias
columnas_necesarias = ['GRANJA', 'LOTE', 'SEMPROD', 'Porcentaje_HuevosTotales', 'Porcentaje_HuevoTotal_Estandar']
if not all(col in df_reales.columns for col in columnas_necesarias):
    st.error("❌ El archivo real no contiene todas las columnas necesarias.")
    st.stop()

# --- 3. CARGA DE PREDICCIONES --- #
st.header("📄 Paso 2: Visualización de curvas reales, proyectadas y estándar")
try:
    df_pred = pd.read_excel("predicciones_huevos.xlsx")
except FileNotFoundError:
    st.error("❌ No se encontró el archivo `predicciones_huevos.xlsx` en el repositorio.")
    st.stop()

# --- 4. SELECCIÓN DE GRANJA Y LOTE --- #
granjas_lotes = df_pred[['GRANJA', 'LOTE']].drop_duplicates()
granjas_lotes['ID'] = granjas_lotes['GRANJA'] + " - " + granjas_lotes['LOTE']
opcion = st.selectbox("Selecciona una Granja + Lote", granjas_lotes['ID'].sort_values())
granja_sel, lote_sel = opcion.split(" - ")

# --- 5. FILTRAR DATOS --- #
reales = df_reales[(df_reales['GRANJA'] == granja_sel) & (df_reales['LOTE'] == lote_sel)].copy()
pred = df_pred[(df_pred['GRANJA'] == granja_sel) & (df_pred['LOTE'] == lote_sel)].copy()

# --- 6. CALCULAR PROMEDIO ESTÁNDAR POR SEMPROD --- #
df_estandar_promedio = df_reales.groupby('SEMPROD')['Porcentaje_HuevoTotal_Estandar'].mean().reset_index()
df_estandar_promedio['Tipo'] = 'Estándar'
df_estandar_promedio = df_estandar_promedio.rename(columns={'Porcentaje_HuevoTotal_Estandar': 'Valor'})

# --- 7. FORMATEAR CURVAS PARA PLOT --- #
reales_plot = reales[['SEMPROD', 'Porcentaje_HuevosTotales']].rename(columns={'Porcentaje_HuevosTotales': 'Valor'})
reales_plot['Tipo'] = 'Real'

pred_plot = pred[['SEMPROD', 'Prediccion_Porcentaje_HuevosTotales']].rename(columns={'Prediccion_Porcentaje_HuevosTotales': 'Valor'})
pred_plot['Tipo'] = 'Predicción'

# --- 8. CONCATENAR Y GRAFICAR --- #
df_plot = pd.concat([reales_plot, pred_plot, df_estandar_promedio], ignore_index=True)
df_plot = df_plot[df_plot['SEMPROD'] <= 45]  # Mostrar solo hasta semana 45

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
