import streamlit as st
import pandas as pd
import plotly.express as px
from office365.runtime.auth.user_credential import UserCredential
from office365.sharepoint.client_context import ClientContext
import io

# --- CONFIGURACIÓN DE SHAREPOINT --- #
site_url = "https://gruporocio.sharepoint.com/sites/IDesarrollo"
ruta_archivo_abiertos = "/sites/IDesarrollo/Documentos compartidos/Libro Verde/Reproductoras/Libro Verde Reproductoras.xlsx"
usuario = "cmedina@gruporocio.com"
contrasena = "3412.abcD*"  # ⚠️ Reemplaza esto localmente por tu contraseña

# --- DESCARGAR ARCHIVO DE ABIERTOS DESDE SHAREPOINT --- #
@st.cache_data(show_spinner=False)
def cargar_datos_abiertos():
    ctx = ClientContext(site_url).with_credentials(UserCredential(usuario, contrasena))
    file_obj = io.BytesIO()
    ctx.web.get_file_by_server_relative_url(ruta_archivo_abiertos).download(file_obj).execute_query()
    file_obj.seek(0)
    df = pd.read_excel(file_obj)
    df = df[df['Estado'].str.strip().str.capitalize() == 'Abierto']
    df = df[['GRANJA', 'LOTE', 'SEMPROD', 'Porcentaje_HuevosTotales']]
    return df

# --- CARGAR PREDICCIONES DESDE LOCAL --- #
@st.cache_data(show_spinner=False)
def cargar_predicciones():
    return pd.read_excel("D:/$CMEDINA/Descargas/predicciones_huevos.xlsx")

# --- TÍTULO APP --- #
st.title("📈 Predicción de Porcentaje de Huevos")
st.markdown("Visualización por **Granja - Lote** de la curva real y la curva proyectada hasta la semana 45.")

# --- CARGAR DATOS --- #
with st.spinner("Cargando datos desde SharePoint..."):
    df_reales = cargar_datos_abiertos()

with st.spinner("Cargando predicciones..."):
    df_pred = cargar_predicciones()

# --- COMBOBOX DE GRANJA - LOTE --- #
granjas_lotes = df_pred[['GRANJA', 'LOTE']].drop_duplicates()
granjas_lotes['id'] = granjas_lotes['GRANJA'] + ' - ' + granjas_lotes['LOTE']
opcion = st.selectbox("Selecciona Granja - Lote", granjas_lotes['id'].sort_values())

# --- FILTRO SELECCIONADO --- #
granja_sel, lote_sel = opcion.split(" - ")

# --- DATOS REALES Y PREDICCIONES --- #
reales = df_reales[(df_reales['GRANJA'] == granja_sel) & (df_reales['LOTE'] == lote_sel)].copy()
pred = df_pred[(df_pred['GRANJA'] == granja_sel) & (df_pred['LOTE'] == lote_sel)].copy()

# --- FORMATEO PARA GRÁFICO --- #
reales = reales[['SEMPROD', 'Porcentaje_HuevosTotales']]
reales['Tipo'] = 'Real'
reales.rename(columns={'Porcentaje_HuevosTotales': 'Valor'}, inplace=True)

pred = pred[['SEMPROD', 'Prediccion_Porcentaje_HuevosTotales']]
pred['Tipo'] = 'Predicción'
pred.rename(columns={'Prediccion_Porcentaje_HuevosTotales': 'Valor'}, inplace=True)

df_plot = pd.concat([reales, pred])

# --- GRÁFICO --- #
fig = px.line(df_plot, x='SEMPROD', y='Valor', color='Tipo', markers=True,
              title=f'Granja: {granja_sel} - Lote: {lote_sel}',
              labels={'Valor': 'Porcentaje de Huevos', 'SEMPROD': 'Semana Productiva'})

st.plotly_chart(fig, use_container_width=True)
