Python 3.14.6 (tags/v3.14.6:c63aec6, Jun 10 2026, 10:26:10) [MSC v.1944 64 bit (AMD64)] on win32
Enter "help" below or click "Help" above for more information.
 ARQUITECTURA COMPLETA DEL PROYECTO

┌─────────────────────────────────────────────────────────────────────┐
│                        USUARIO (Navegador)                          │
│   Pregunta: "¿Cuál fue el gasto total del Territorio Norte?"       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP Request (JSON)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│              INTERFAZ WEB (HTML + CSS + JavaScript)                 │
│  • Chat UI con burbujas de mensajes                                 │
│  • Input de texto + botón enviar                                    │
│  • Fetch API para comunicarse con FastAPI                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ POST /chat  (JSON: {"query": "..."})
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FASTAPI (Backend - Python)                        │
│  • Endpoint /chat recibe la pregunta                                │
│  • Endpoint /health verifica estado                                 │
│  • CORS habilitado para la interfaz web                             │
│  • Invoca al motor de procesamiento                                 │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│              PYTHON + PANDAS (Motor de Procesamiento)                │
│  • Carga CSVs al iniciar (GL.csv + Chart_of_Accounts.csv)           │
│  • Limpieza de datos (NaN, tipos, formatos)                         │
│  • Merge entre DataFrames (GL + Plan de Cuentas)                    │
│  • Búsqueda y filtrado según la consulta                            │
│  • Generación de respuesta en lenguaje natural                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   RESPUESTA DEL CHATBOT (JSON)                      │
│  {"respuesta": "El gasto total del Territorio Norte fue $45,200"}   │
└─────────────────────────────────────────────────────────────────────┘



Estructura del Proyecto

chatbot_financiero/
│
├── data/                          # Carpeta de datos
│   ├── GL.csv                     # Libro Mayor (exportado desde Kaggle)
│   └── Chart_of_Accounts.csv      # Plan de Cuentas (exportado desde Kaggle)
│
├── backend/
│   ├── main.py                    # FastAPI + Lógica principal
│   ├── data_processor.py          # Carga, limpieza y merge de CSVs
│   └── chatbot_engine.py          # Motor de procesamiento de consultas
│
├── frontend/
│   ├── index.html                 # Interfaz web
│   ├── style.css                  # Estilos
│   └── script.js                  # Lógica de comunicación con API
│
├── requirements.txt               # Dependencias
└── README.md

DATAFRAME

import pandas as pd
import os

class DataProcessor:
    """
    Clase encargada de cargar, limpiar y procesar los datos contables.
    Lee los archivos CSV del dataset General Ledger.
    """

    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.df_gl = None              # DataFrame del Libro Mayor
        self.df_accounts = None        # DataFrame del Plan de Cuentas
        self.df_merged = None          # DataFrame resultante del merge

        # Cargar y procesar al inicializar
        self._load_data()
        self._clean_data()
        self._merge_data()

    def _load_data(self):
        """Lee los archivos CSV desde la carpeta data/"""
        gl_path = os.path.join(self.data_dir, "GL.csv")
        accounts_path = os.path.join(self.data_dir, "Chart_of_Accounts.csv")

        # ============================================
        # DATAFRAME 1: LIBRO MAYOR (GL.csv)
        # ============================================
        # Columnas típicas del dataset General Ledger:
        # Date | Account | Debit | Credit | Description | Territory | Journal_Entry_ID
        self.df_gl = pd.read_csv(gl_path, parse_dates=['Date'])
        print(f"✅ GL.csv cargado: {self.df_gl.shape[0]} filas, {self.df_gl.shape[1]} columnas")

        # ============================================
        # DATAFRAME 2: PLAN DE CUENTAS (Chart_of_Accounts.csv)
        # ============================================
        # Columnas típicas:
        # Account_Code | Account_Name | Account_Type | Normal_Balance
        self.df_accounts = pd.read_csv(accounts_path)
        print(f"✅ Chart_of_Accounts.csv cargado: {self.df_accounts.shape[0]} filas")

    def _clean_data(self):
        """
        Limpieza de datos:
        - Eliminar filas completamente vacías
        - Rellenar NaN en descripciones
        - Convertir tipos de datos numéricos
        - Estandarizar nombres de territorios
        """
        # --- Limpieza del Libro Mayor ---
        # Eliminar filas donde faltan datos críticos
        self.df_gl = self.df_gl.dropna(subset=['Account', 'Date'])

        # Rellenar descripciones vacías
        self.df_gl['Description'] = self.df_gl['Description'].fillna('Sin descripción')

        # Asegurar que Debit y Credit sean numéricos
        self.df_gl['Debit'] = pd.to_numeric(self.df_gl['Debit'], errors='coerce').fillna(0)
        self.df_gl['Credit'] = pd.to_numeric(self.df_gl['Credit'], errors='coerce').fillna(0)

        # Calcular el monto neto de cada transacción
        self.df_gl['Amount'] = self.df_gl['Debit'] - self.df_gl['Credit']

        # Estandarizar Territory (quitar espacios, capitalizar)
        if 'Territory' in self.df_gl.columns:
            self.df_gl['Territory'] = self.df_gl['Territory'].str.strip().str.title()

        # --- Limpieza del Plan de Cuentas ---
        self.df_accounts = self.df_accounts.dropna(subset=['Account_Code'])
        self.df_accounts['Account_Name'] = self.df_accounts['Account_Name'].str.strip()

        print(f"🧹 Datos limpiados. GL final: {self.df_gl.shape[0]} filas")

    def _merge_data(self):
        """
        Realiza merge entre el Libro Mayor y el Plan de Cuentas
        para enriquecer las transacciones con nombres de cuentas y tipos.
        """
        # Merge: GL (izquierda) + Plan de Cuentas (derecha)
        # La columna de unión es 'Account' en GL y 'Account_Code' en Plan de Cuentas
        self.df_merged = pd.merge(
            self.df_gl,
            self.df_accounts,
            left_on='Account',
            right_on='Account_Code',
            how='left',
            suffixes=('_gl', '_acc')
        )

        # Rellenar cuentas no encontradas en el Plan
        self.df_merged['Account_Name'] = self.df_merged['Account_Name'].fillna('Cuenta Desconocida')
        self.df_merged['Account_Type'] = self.df_merged['Account_Type'].fillna('Otro')

        print(f"🔗 Merge completado. DataFrame final: {self.df_merged.shape[0]} filas, {self.df_merged.shape[1]} columnas")
        print(f"📋 Columnas disponibles: {list(self.df_merged.columns)}")

    def get_dataframe(self):
        """Retorna el DataFrame procesado y listo para consultar."""
        return self.df_merged

    def get_summary(self):
        """Retorna un resumen estadístico de los datos."""
        return {
            "total_transacciones": len(self.df_merged),
            "total_territorios": self.df_merged['Territory'].nunique() if 'Territory' in self.df_merged.columns else 0,
            "total_cuentas": self.df_merged['Account'].nunique(),
            "rango_fechas": {
                "desde": str(self.df_merged['Date'].min().date()),
                "hasta": str(self.df_merged['Date'].max().date())
            },
            "tipos_cuenta": self.df_merged['Account_Type'].value_counts().to_dict()
        }

data/GL.csv

CSV de ejemplo

Libro Mayor

Date,Account,Debit,Credit,Description,Territory,Journal_Entry_ID
2024-01-15,1000,5000.00,0.00,Venta de servicios,North,JE001
2024-01-15,4000,0.00,5000.00,Ingreso por servicios,North,JE001
2024-01-20,6000,1200.00,0.00,Alquiler oficina,South,JE002
2024-01-20,1100,0.00,1200.00,Pago alquiler,South,JE002
2024-02-01,6100,800.00,0.00,Suministros de oficina,East,JE003
2024-02-01,1100,0.00,800.00,Pago suministros,East,JE003
2024-02-10,1000,7500.00,0.00,Venta de productos,West,JE004
2024-02-10,4000,0.00,7500.00,Ingreso por productos,West,JE004
2024-03-05,6200,2000.00,0.00,Salarios empleados,North,JE005
2024-03-05,1100,0.00,2000.00,Pago de salarios,North,JE005

data/Chart_of_Accounts.csv

Plan de Cuentas

Account_Code,Account_Name,Account_Type,Normal_Balance
1000,Cuentas por Cobrar,Activo,Debit
1100,Bancos,Activo,Debit
2000,Cuentas por Pagar,Pasivo,Credit
4000,Ingresos por Servicios,Ingreso,Credit
4100,Ingresos por Productos,Ingreso,Credit
6000,Gastos de Alquiler,Gasto,Debit
6100,Gastos de Suministros,Gasto,Debit
6200,Gastos de Salarios,Gasto,Debit

BACKEND CON FastAPI

Archivo: main.py  Python

import pandas as pd
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ============================================
# 0. SETUP ENVIRONMENT (for Colab execution)
# ============================================
# Uninstall conflicting packages before installing desired versions
!pip uninstall -y pandas numpy pydantic fastapi uvicorn

# Install dependencies with specified versions
!pip install -q fastapi==0.104.1 uvicorn==0.24.0 pandas==2.1.3 pydantic==2.5.0 numpy==1.26.4

# Create data directory
if not os.path.exists('data'):
    os.makedirs('data')

# Create GL.csv
with open('data/GL.csv', 'w') as f:
    f.write("""Date,Account,Debit,Credit,Description,Territory,Journal_Entry_ID
2024-01-15,1000,5000.00,0.00,Venta de servicios,North,JE001
2024-01-15,4000,0.00,5000.00,Ingreso por servicios,North,JE001
2024-01-20,6000,1200.00,0.00,Alquiler oficina,South,JE002
2024-01-20,1100,0.00,1200.00,Pago alquiler,South,JE002
2024-02-01,6100,800.00,0.00,Suministros de oficina,East,JE003
2024-02-01,1100,0.00,800.00,Pago suministros,East,JE003
2024-02-10,1000,7500.00,0.00,Venta de productos,West,JE004
2024-02-10,4000,0.00,7500.00,Ingreso por productos,West,JE004
2024-03-05,6200,2000.00,0.00,Salarios empleados,North,JE005
2024-03-05,1100,0.00,2000.00,Pago de salarios,North,JE005""")

# Create Chart_of_Accounts.csv
with open('data/Chart_of_Accounts.csv', 'w') as f:
    f.write("""Account_Code,Account_Name,Account_Type,Normal_Balance
1000,Cuentas por Cobrar,Activo,Debit
1100,Bancos,Activo,Debit
2000,Cuentas por Pagar,Pasivo,Credit
4000,Ingresos por Servicios,Ingreso,Credit
4100,Ingresos por Productos,Ingreso,Credit
6000,Gastos de Alquiler,Gasto,Debit
6100,Gastos de Suministros,Gasto,Debit
6200,Gastos de Salarios,Gasto,Debit""")

# ============================================
# DataProcessor Class (Embedded)
# ============================================
class DataProcessor:
    """
    Clase encargada de cargar, limpiar y procesar los datos contables.
    Lee los archivos CSV del dataset General Ledger.
    """

    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.df_gl = None              # DataFrame del Libro Mayor
        self.df_accounts = None        # DataFrame del Plan de Cuentas
        self.df_merged = None          # DataFrame resultante del merge

        # Cargar y procesar al inicializar
        self._load_data()
        self._clean_data()
        self._merge_data()

    def _load_data(self):
        """Lee los archivos CSV desde la carpeta data/"""
        gl_path = os.path.join(self.data_dir, "GL.csv")
        accounts_path = os.path.join(self.data_dir, "Chart_of_Accounts.csv")

        # ============================================
        # DATAFRAME 1: LIBRO MAYOR (GL.csv)
        # ============================================
        self.df_gl = pd.read_csv(gl_path, parse_dates=['Date'])
        print(f"✅ GL.csv cargado: {self.df_gl.shape[0]} filas, {self.df_gl.shape[1]} columnas")

        # ============================================
        # DATAFRAME 2: PLAN DE CUENTAS (Chart_of_Accounts.csv)
        # ============================================
        self.df_accounts = pd.read_csv(accounts_path)
        print(f"✅ Chart_of_Accounts.csv cargado: {self.df_accounts.shape[0]} filas")

    def _clean_data(self):
        """
        Limpieza de datos:
        - Eliminar filas completamente vacías
        - Rellenar NaN en descripciones
        - Convertir tipos de datos numéricos
        - Estandarizar nombres de territorios
        """
        # --- Limpieza del Libro Mayor ---
        self.df_gl = self.df_gl.dropna(subset=['Account', 'Date'])
        self.df_gl['Description'] = self.df_gl['Description'].fillna('Sin descripción')
        self.df_gl['Debit'] = pd.to_numeric(self.df_gl['Debit'], errors='coerce').fillna(0)
        self.df_gl['Credit'] = pd.to_numeric(self.df_gl['Credit'], errors='coerce').fillna(0)
        self.df_gl['Amount'] = self.df_gl['Debit'] - self.df_gl['Credit']
        if 'Territory' in self.df_gl.columns:
            self.df_gl['Territory'] = self.df_gl['Territory'].str.strip().str.title()

        # --- Limpieza del Plan de Cuentas ---
        self.df_accounts = self.df_accounts.dropna(subset=['Account_Code'])
        self.df_accounts['Account_Name'] = self.df_accounts['Account_Name'].str.strip()

        print(f"🧹 Datos limpiados. GL final: {self.df_gl.shape[0]} filas")

    def _merge_data(self):
        """
        Realiza merge entre el Libro Mayor y el Plan de Cuentas
        para enriquecer las transacciones con nombres de cuentas y tipos.
        """
        self.df_merged = pd.merge(
            self.df_gl,
            self.df_accounts,
            left_on='Account',
            right_on='Account_Code',
            how='left',
            suffixes=('_gl', '_acc')
        )

        self.df_merged['Account_Name'] = self.df_merged['Account_Name'].fillna('Cuenta Desconocida')
        self.df_merged['Account_Type'] = self.df_merged['Account_Type'].fillna('Otro')

        print(f"🔗 Merge completado. DataFrame final: {self.df_merged.shape[0]} filas, {self.df_merged.shape[1]} columnas")
        print(f"📋 Columnas disponibles: {list(self.df_merged.columns)}")

    def get_dataframe(self):
        """Retorna el DataFrame procesado y listo para consultar."""
        return self.df_merged

    def get_summary(self):
        """Retorna un resumen estadístico de los datos."""
        return {
            "total_transacciones": len(self.df_merged),
            "total_territorios": self.df_merged['Territory'].nunique() if 'Territory' in self.df_merged.columns else 0,
            "total_cuentas": self.df_merged['Account'].nunique(),
            "rango_fechas": {
                "desde": str(self.df_merged['Date'].min().date()),
                "hasta": str(self.df_merged['Date'].max().date())
            },
            "tipos_cuenta": self.df_merged['Account_Type'].value_counts().to_dict()
        }

# ============================================
# ChatbotEngine Class (Embedded)
# ============================================
class ChatbotEngine:
    """
    Motor del chatbot: procesa consultas en lenguaje natural
    y las traduce a operaciones sobre el DataFrame.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def process_query(self, query: str) -> dict:
        """
        Procesa la consulta del usuario y retorna una respuesta.
        En una versión avanzada, aquí iría un LLM.
        Esta versión usa reglas y palabras clave.
        """
        query_lower = query.lower()

        # ============================================
        # PATRÓN 1: Consulta por Territorio
        # ============================================
        if "territorio" in query_lower or "norte" in query_lower or "sur" in query_lower:
            return self._query_by_territory(query_lower)

        # ============================================
        # PATRÓN 2: Consulta por tipo de cuenta (Gastos, Ingresos)
        # ============================================
        elif "gasto" in query_lower or "ingreso" in query_lower:
            return self._query_by_account_type(query_lower)

        # ============================================
        # PATRÓN 3: Consulta por rango de fechas
        # ============================================
        elif "enero" in query_lower or "febrero" in query_lower or "marzo" in query_lower:
            return self._query_by_month(query_lower)

        # ============================================
        # PATRÓN 4: Resumen general
        # ============================================
        elif "resumen" in query_lower or "total" in query_lower:
            return self._query_summary()

        # ============================================
        # DEFAULT: No se entendió la consulta
        # ============================================
        else:
            return {
                "texto": "No entendí tu consulta. Podés preguntarme sobre:\n" +
                         "• Gastos o ingresos por territorio\n" +
                         "• Totales por mes\n" +
                         "• Resumen general de las cuentas",
                "datos": []
            }

    def _query_by_territory(self, query: str) -> dict:
        """Filtra datos por territorio."""
        territorios = {"norte": "North", "sur": "South", "este": "East", "oeste": "West"}

        territorio_encontrado = None
        for key, value in territorios.items():
            if key in query:
                territorio_encontrado = value
                break

        if territorio_encontrado and 'Territory' in self.df.columns:
            datos = self.df[self.df['Territory'] == territorio_encontrado]
            total_gastos = datos[datos['Account_Type'] == 'Gasto']['Amount'].sum()
            total_ingresos = datos[datos['Account_Type'] == 'Ingreso']['Amount'].abs().sum()

            return {
                "texto": f"📊 Para el Territorio {territorio_encontrado}:\n" +
                         f"• Total de Gastos: ${total_gastos:,.2f}\n" +
                         f"• Total de Ingresos: ${total_ingresos:,.2f}\n" +
                         f"• Transacciones registradas: {len(datos)}",
                "datos": datos.head(5).to_dict('records')
            }
        return {"texto": "No encontré datos para ese territorio.", "datos": []}

    def _query_by_account_type(self, query: str) -> dict:
        """Filtra por tipo de cuenta."""
        if "gasto" in query:
            datos = self.df[self.df['Account_Type'] == 'Gasto']
            total = datos['Amount'].sum()
            tipo = "Gastos"
        else:
            datos = self.df[self.df['Account_Type'] == 'Ingreso']
            total = datos['Amount'].abs().sum()
            tipo = "Ingresos"

        return {
            "texto": f"💰 Total de {tipo}: ${total:,.2f}\n" +
                     f"📝 Cantidad de transacciones: {len(datos)}",
            "datos": datos.head(5).to_dict('records')
        }

    def _query_by_month(self, query: str) -> dict:
        """Filtra por mes."""
        meses = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6}

        mes_encontrado = None
        for key, value in meses.items():
            if key in query:
                mes_encontrado = value
                break

        if mes_encontrado:
            datos = self.df[self.df['Date'].dt.month == mes_encontrado]
            total = datos['Amount'].sum()
            return {
                "texto": f"📅 Movimientos del mes {mes_encontrado}:\n" +
                         f"• Total: ${total:,.2f}\n" +
                         f"• Transacciones: {len(datos)}",
                "datos": datos.head(5).to_dict('records')
            }
        return {"texto": "No encontré datos para ese mes.", "datos": []}

    def _query_summary(self) -> dict:
        """Resumen general de los datos."""
        total_transacciones = len(self.df)
        total_movimientos = self.df['Amount'].sum()
        territorios = self.df['Territory'].nunique() if 'Territory' in self.df.columns else 0

        return {
            "texto": f"📋 RESUMEN GENERAL:\n" +
                     f"• Total de transacciones: {total_transacciones}\n" +
                     f"• Monto total movimentado: ${total_movimientos:,.2f}\n" +
                     f"• Territorios registrados: {territorios}\n" +
                     f"• Cuentas únicas: {self.df['Account'].nunique()}",
            "datos": []
        }

# ============================================
# INICIALIZACIÓN DE FASTAPI
# ============================================
app = FastAPI(
    title="Chatbot Financiero - General Ledger",
    description="API para consultar datos contables en lenguaje natural",
    version="1.0.0"
)

# Habilitar CORS para permitir comunicación con la interfaz web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar el dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# CARGA DE DATOS AL INICIAR
# ============================================
print("🚀 Iniciando Chatbot Financiero...")
processor = DataProcessor(data_dir="data")
chatbot = ChatbotEngine(processor.get_dataframe())
print("✅ Sistema listo para recibir consultas\n")

# ============================================
# MODELOS DE DATOS (Pydantic)
# ============================================
class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    pregunta: str
    respuesta: str
    datos_relevantes: list = []

# ============================================
# ENDPOINTS
# ============================================
@app.get("/")
async def root():
    return {"mensaje": "Chatbot Financiero API - General Ledger"}

@app.get("/health")
async def health_check():
    """Verifica que el sistema esté operativo."""
    return {
        "status": "ok",
        "registros_cargados": len(chatbot.df),
        "columnas": list(chatbot.df.columns)
    }

@app.get("/summary")
async def get_summary():
    """Retorna un resumen de los datos cargados."""
    return processor.get_summary()

@app.post("/chat", response_model=QueryResponse)
async def chat(request: QueryRequest):
    """
    Endpoint principal del chatbot.
    Recibe una pregunta en lenguaje natural y devuelve una respuesta.
    """
    try:
        respuesta = chatbot.process_query(request.query)
        return QueryResponse(
            pregunta=request.query,
            respuesta=respuesta["texto"],
            datos_relevantes=respuesta.get("datos", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# EJECUCIÓN DEL SERVIDOR
# ============================================
if __name__ == "__main__":
    # This block is typically for running FastAPI with uvicorn.run().
    # In a Colab environment, you might use a different method to expose the API
    # or just run specific parts of the logic for testing.
    # For simplicity in Colab, we can skip uvicorn.run() if just testing the setup,
    # or use it with a tool like `ngrok` if exposing it.
    # To run FastAPI in Colab, you would usually do something like:
    # from colab_tunnel import run_ngrok
    # run_ngrok(app)
    print("FastAPI app is set up. To run it, you would typically use uvicorn.run(app, host='0.0.0.0', port=8000) "
          "in a script or use a tool like ngrok in Colab.")

Archivo: chatbot_engine.py  PYTHON

import pandas as pd

class ChatbotEngine:
    """
    Motor del chatbot: procesa consultas en lenguaje natural
    y las traduce a operaciones sobre el DataFrame.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def process_query(self, query: str) -> dict:
        """
        Procesa la consulta del usuario y retorna una respuesta.
        En una versión avanzada, aquí iría un LLM.
        Esta versión usa reglas y palabras clave.
        """
        query_lower = query.lower()

        # ============================================
        # PATRÓN 1: Consulta por Territorio
        # ============================================
        if "territorio" in query_lower or "norte" in query_lower or "sur" in query_lower:
            return self._query_by_territory(query_lower)

        # ============================================
        # PATRÓN 2: Consulta por tipo de cuenta (Gastos, Ingresos)
        # ============================================
        elif "gasto" in query_lower or "ingreso" in query_lower:
            return self._query_by_account_type(query_lower)

        # ============================================
        # PATRÓN 3: Consulta por rango de fechas
        # ============================================
        elif "enero" in query_lower or "febrero" in query_lower or "marzo" in query_lower:
            return self._query_by_month(query_lower)

        # ============================================
        # PATRÓN 4: Resumen general
        # ============================================
        elif "resumen" in query_lower or "total" in query_lower:
            return self._query_summary()

        # ============================================
        # DEFAULT: No se entendió la consulta
        # ============================================
        else:
            return {
                "texto": "No entendí tu consulta. Podés preguntarme sobre:\n"
                         "• Gastos o ingresos por territorio\n"
                         "• Totales por mes\n"
                         "• Resumen general de las cuentas",
                "datos": []
            }

    def _query_by_territory(self, query: str) -> dict:
        """Filtra datos por territorio."""
        territorios = {"norte": "North", "sur": "South", "este": "East", "oeste": "West"}

        territorio_encontrado = None
        for key, value in territorios.items():
            if key in query:
                territorio_encontrado = value
                break

        if territorio_encontrado and 'Territory' in self.df.columns:
            datos = self.df[self.df['Territory'] == territorio_encontrado]
            total_gastos = datos[datos['Account_Type'] == 'Gasto']['Amount'].sum()
            total_ingresos = datos[datos['Account_Type'] == 'Ingreso']['Amount'].abs().sum()

            return {
                "texto": f"📊 Para el Territorio {territorio_encontrado}:\n"
                         f"• Total de Gastos: ${total_gastos:,.2f}\n"
                         f"• Total de Ingresos: ${total_ingresos:,.2f}\n"
                         f"• Transacciones registradas: {len(datos)}",
                "datos": datos.head(5).to_dict('records')
            }
        return {"texto": "No encontré datos para ese territorio.", "datos": []}

    def _query_by_account_type(self, query: str) -> dict:
        """Filtra por tipo de cuenta."""
        if "gasto" in query:
            datos = self.df[self.df['Account_Type'] == 'Gasto']
            total = datos['Amount'].sum()
            tipo = "Gastos"
        else:
            datos = self.df[self.df['Account_Type'] == 'Ingreso']
            total = datos['Amount'].abs().sum()
            tipo = "Ingresos"

        return {
            "texto": f"💰 Total de {tipo}: ${total:,.2f}\n"
                     f"📝 Cantidad de transacciones: {len(datos)}",
            "datos": datos.head(5).to_dict('records')
        }

    def _query_by_month(self, query: str) -> dict:
        """Filtra por mes."""
        meses = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6}

        mes_encontrado = None
        for key, value in meses.items():
            if key in query:
                mes_encontrado = value
                break

        if mes_encontrado:
            datos = self.df[self.df['Date'].dt.month == mes_encontrado]
            total = datos['Amount'].sum()
            return {
                "texto": f"📅 Movimientos del mes {mes_encontrado}:\n"
                         f"• Total: ${total:,.2f}\n"
                         f"• Transacciones: {len(datos)}",
                "datos": datos.head(5).to_dict('records')
            }
        return {"texto": "No encontré datos para ese mes.", "datos": []}

    def _query_summary(self) -> dict:
        """Resumen general de los datos."""
        total_transacciones = len(self.df)
        total_movimientos = self.df['Amount'].sum()
        territorios = self.df['Territory'].nunique() if 'Territory' in self.df.columns else 0

        return {
            "texto": f"📋 RESUMEN GENERAL:\n"
                     f"• Total de transacciones: {total_transacciones}\n"
                     f"• Monto total movimentado: ${total_movimientos:,.2f}\n"
                     f"• Territorios registrados: {territorios}\n"
                     f"• Cuentas únicas: {self.df['Account'].nunique()}",
            "datos": []
        }

 INTERFAZ WEB (HTML + CSS + JS)

Archivo: frontend/index.html   HTML

<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chatbot Financiero - General Ledger</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>🤖 Chatbot Financiero</h1>
            <p>Consultas sobre el Libro Mayor Contable</p>
        </div>

        <div class="chat-messages" id="chatMessages">
            <div class="message bot-message">
                <div class="message-content">
                    ¡Hola! 👋 Soy tu asistente contable. Podés preguntarme sobre:<br>
                    • Gastos e ingresos por territorio<br>
                    • Totales por mes<br>
                    • Resumen general de cuentas<br><br>
                    <em>Ejemplo: "¿Cuáles fueron los gastos del territorio norte?"</em>
                </div>
            </div>
        </div>

        <div class="chat-input-container">
            <input
                type="text"
                id="userInput"
                placeholder="Escribí tu consulta contable..."
                autocomplete="off"
            >
            <button id="sendBtn" onclick="sendMessage()">Enviar ➤</button>
        </div>
    </div>

    <script src="script.js"></script>
</body>
</html>

Archivo:frontend/style.css           CSS

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

body {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px;
}

.chat-container {
    width: 100%;
    max-width: 700px;
    height: 85vh;
    background: #fff;
    border-radius: 20px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.chat-header {
    background: linear-gradient(135deg, #2c3e50, #3498db);
    color: white;
    padding: 20px;
    text-align: center;
}

.chat-header h1 {
    font-size: 1.5rem;
    margin-bottom: 5px;
}

.chat-header p {
    font-size: 0.9rem;
    opacity: 0.9;
}

.chat-messages {
    flex: 1;
    padding: 20px;
    overflow-y: auto;
    background: #f5f7fa;
}

.message {
    margin-bottom: 15px;
    display: flex;
    animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.user-message {
    justify-content: flex-end;
}

.bot-message {
    justify-content: flex-start;
}

.message-content {
    max-width: 75%;
    padding: 12px 18px;
    border-radius: 18px;
    line-height: 1.5;
    font-size: 0.95rem;
    white-space: pre-line;
}

.user-message .message-content {
    background: #3498db;
    color: white;
    border-bottom-right-radius: 4px;
}

.bot-message .message-content {
    background: #e9ecef;
    color: #2c3e50;
    border-bottom-left-radius: 4px;
}

.chat-input-container {
    padding: 15px 20px;
    background: white;
    border-top: 1px solid #e0e0e0;
    display: flex;
    gap: 10px;
}

#userInput {
    flex: 1;
    padding: 12px 18px;
    border: 2px solid #e0e0e0;
    border-radius: 25px;
    font-size: 1rem;
    outline: none;
    transition: border-color 0.3s;
}

#userInput:focus {
    border-color: #3498db;
}

#sendBtn {
    padding: 12px 25px;
    background: linear-gradient(135deg, #3498db, #2c3e50);
    color: white;
    border: none;
    border-radius: 25px;
    cursor: pointer;
    font-size: 1rem;
    font-weight: bold;
    transition: transform 0.2s;
}

#sendBtn:hover {
    transform: scale(1.05);
}

#sendBtn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

Archivo: frontend/script.js   Javascript

const API_URL = "http://localhost:8000/chat";

// Enviar mensaje al presionar Enter
document.getElementById('userInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

async function sendMessage() {
    const input = document.getElementById('userInput');
    const message = input.value.trim();

    if (!message) return;

    // Agregar mensaje del usuario al chat
    addMessage(message, 'user');
    input.value = '';

    // Deshabilitar input mientras se procesa
    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;
    input.disabled = true;

    // Mostrar indicador de "escribiendo..."
    const typingIndicator = addTypingIndicator();

    try {
        // Llamar a la API de FastAPI
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query: message })
        });

        if (!response.ok) {
            throw new Error(`Error HTTP: ${response.status}`);
        }

        const data = await response.json();

        // Remover indicador de typing
        typingIndicator.remove();

        // Agregar respuesta del bot
        addMessage(data.respuesta, 'bot');

    } catch (error) {
        typingIndicator.remove();
        addMessage(`❌ Error al conectar con el servidor: ${error.message}`, 'bot');
        console.error('Error:', error);
    } finally {
        sendBtn.disabled = false;
        input.disabled = false;
        input.focus();
    }
}

function addMessage(text, sender) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = text;

    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);

    // Scroll al final
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    return messageDiv;
}

function addTypingIndicator() {
    const messagesContainer = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message';
    typingDiv.id = 'typingIndicator';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = '<em>Analizando datos contables...</em> ⏳';

    typingDiv.appendChild(contentDiv);
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    return typingDiv;
}

Archivo: requirements.txt  TXT

fastapi==0.104.1
uvicorn==0.24.0
pandas==2.1.3
pydantic==2.5.0

Consultas predefinidas para probar el chatbot, demostrar su capacidad, y validar que el merge y el procesamiento funcionan correctamente.

Pregunta: "¿Cuál es el total de gastos en cada territorio?"
Objetivo: Agrupar por territorio y sumar los gastos.

# Filtrar solo gastos y agrupar por territorio
gastos_por_territorio = (
    df_merged[df_merged['Account_Type'] == 'Gasto']
    .groupby('Territory')['Amount']
    .sum()
    .sort_values(ascending=False)
)

print(gastos_por_territorio)

Pregunta: "¿Cuáles son las 5 cuentas contables más utilizadas?"
Objetivo: Contar transacciones por cuenta y mostrar el top 5.

# Contar transacciones por cuenta
cuentas_mas_usadas = (
    df_merged['Account_Name']
    .value_counts()
    .head(5)
)

print(cuentas_mas_usadas)

Pregunta: "¿Cuál es el balance total por tipo de cuenta (Activo, Pasivo, Ingreso, Gasto)?"
Objetivo: Agrupar por tipo de cuenta y calcular el balance neto.

# Agrupar por tipo de cuenta y sumar montos
balance_por_tipo = (
    df_merged.groupby('Account_Type')['Amount']
    .sum()
    .sort_values(ascending=False)
)

print(balance_por_tipo)

Pregunta técnica: "¿Qué porcentaje de las cuentas concentran el 80% de los movimientos?"
Objetivo: Aplicar el principio de Pareto para identificar las cuentas críticas.

# Contar transacciones por cuenta
transacciones_por_cuenta = df_merged['Account_Name'].value_counts()

# Calcular porcentaje acumulado
total_transacciones = transacciones_por_cuenta.sum()
porcentaje_acumulado = (transacciones_por_cuenta.cumsum() / total_transacciones) * 100

# Encontrar cuántas cuentas representan el 80%
cuentas_top_80 = porcentaje_acumulado[porcentaje_acumulado <= 80]

print(f"Cuentas que concentran el 80%: {len(cuentas_top_80)} de {len(transacciones_por_cuenta)}")
print(f"Porcentaje: {(len(cuentas_top_80) / len(transacciones_por_cuenta) * 100):.1f}%")

Pregunta técnica: "¿Hay transacciones con montos atípicos (outliers) que se desvíen más de 2 desvíos estándar?"
Objetivo: Usar estadística para detectar anomalías en los montos de transacciones.

import pandas as pd
import os

# --- BEGIN: Data setup and DataProcessor class definition for standalone execution ---
# Create data directory if it doesn't exist
if not os.path.exists('data'):
    os.makedirs('data')

# Create GL.csv with example data
with open('data/GL.csv', 'w') as f:
    f.write("""Date,Account,Debit,Credit,Description,Territory,Journal_Entry_ID
2024-01-15,1000,5000.00,0.00,Venta de servicios,North,JE001
2024-01-15,4000,0.00,5000.00,Ingreso por servicios,North,JE001
2024-01-20,6000,1200.00,0.00,Alquiler oficina,South,JE002
2024-01-20,1100,0.00,1200.00,Pago alquiler,South,JE002
2024-02-01,6100,800.00,0.00,Suministros de oficina,East,JE003
2024-02-01,1100,0.00,800.00,Pago suministros,East,JE003
2024-02-10,1000,7500.00,0.00,Venta de productos,West,JE004
2024-02-10,4000,0.00,7500.00,Ingreso por productos,West,JE004
2024-03-05,6200,2000.00,0.00,Salarios empleados,North,JE005
2024-03-05,1100,0.00,2000.00,Pago de salarios,North,JE005""")

# Create Chart_of_Accounts.csv with example data
with open('data/Chart_of_Accounts.csv', 'w') as f:
    f.write("""Account_Code,Account_Name,Account_Type,Normal_Balance
1000,Cuentas por Cobrar,Activo,Debit
1100,Bancos,Activo,Debit
2000,Cuentas por Pagar,Pasivo,Credit
4000,Ingresos por Servicios,Ingreso,Credit
4100,Ingresos por Productos,Ingreso,Credit
6000,Gastos de Alquiler,Gasto,Debit
6100,Gastos de Suministros,Gasto,Debit
6200,Gastos de Salarios,Gasto,Debit""")

class DataProcessor:
    """
    Clase encargada de cargar, limpiar y procesar los datos contables.
    Lee los archivos CSV del dataset General Ledger.
    """

    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.df_gl = None              # DataFrame del Libro Mayor
        self.df_accounts = None        # DataFrame del Plan de Cuentas
        self.df_merged = None          # DataFrame resultante del merge

        # Cargar y procesar al inicializar
        self._load_data()
        self._clean_data()
        self._merge_data()

    def _load_data(self):
        """Lee los archivos CSV desde la carpeta data/"""
        gl_path = os.path.join(self.data_dir, "GL.csv")
        accounts_path = os.path.join(self.data_dir, "Chart_of_Accounts.csv")

        # ============================================
        # DATAFRAME 1: LIBRO MAYOR (GL.csv)
        # ============================================
        self.df_gl = pd.read_csv(gl_path, parse_dates=['Date'])

        # ============================================
        # DATAFRAME 2: PLAN DE CUENTAS (Chart_of_Accounts.csv)
        # ============================================
        self.df_accounts = pd.read_csv(accounts_path)

    def _clean_data(self):
        """
        Limpieza de datos:
        - Eliminar filas completamente vacías
        - Rellenar NaN en descripciones
        - Convertir tipos de datos numéricos
        - Estandarizar nombres de territorios
        """
        # --- Limpieza del Libro Mayor ---
        self.df_gl = self.df_gl.dropna(subset=['Account', 'Date'])
        self.df_gl['Description'] = self.df_gl['Description'].fillna('Sin descripción')
        self.df_gl['Debit'] = pd.to_numeric(self.df_gl['Debit'], errors='coerce').fillna(0)
        self.df_gl['Credit'] = pd.to_numeric(self.df_gl['Credit'], errors='coerce').fillna(0)
        self.df_gl['Amount'] = self.df_gl['Debit'] - self.df_gl['Credit']
        if 'Territory' in self.df_gl.columns:
            self.df_gl['Territory'] = self.df_gl['Territory'].str.strip().str.title()

        # --- Limpieza del Plan de Cuentas ---
        self.df_accounts = self.df_accounts.dropna(subset=['Account_Code'])
        self.df_accounts['Account_Name'] = self.df_accounts['Account_Name'].str.strip()

    def _merge_data(self):
        """
        Realiza merge entre el Libro Mayor y el Plan de Cuentas
        para enriquecer las transacciones con nombres de cuentas y tipos.
        """
        self.df_merged = pd.merge(
            self.df_gl,
            self.df_accounts,
            left_on='Account',
            right_on='Account_Code',
            how='left',
            suffixes=('_gl', '_acc')
        )

        self.df_merged['Account_Name'] = self.df_merged['Account_Name'].fillna('Cuenta Desconocida')
        self.df_merged['Account_Type'] = self.df_merged['Account_Type'].fillna('Otro')

    def get_dataframe(self):
        """Retorna el DataFrame procesado y listo para consultar."""
        return self.df_merged

    def get_summary(self):
        """Retorna un resumen estadístico de los datos."""
        return {
            "total_transacciones": len(self.df_merged),
            "total_territorios": self.df_merged['Territory'].nunique() if 'Territory' in self.df_merged.columns else 0,
            "total_cuentas": self.df_merged['Account'].nunique(),
            "rango_fechas": {
                "desde": str(self.df_merged['Date'].min().date()),
                "hasta": str(self.df_merged['Date'].max().date())
            },
            "tipos_cuenta": self.df_merged['Account_Type'].value_counts().to_dict()
        }
# --- END: Data setup and DataProcessor class definition ---

# Initialize DataProcessor and get the merged DataFrame
processor = DataProcessor(data_dir="data")
df_merged = processor.get_dataframe()

# Calcular media y desvío estándar de los montos
media = df_merged['Amount'].mean()
std = df_merged['Amount'].std()

# Definir límites (±2 desvíos estándar)
limite_superior = media + (2 * std)
limite_inferior = media - (2 * std)

# Filtrar outliers
outliers = df_merged[
    (df_merged['Amount'] > limite_superior) |
    (df_merged['Amount'] < limite_inferior)
][['Date', 'Account_Name', 'Amount', 'Territory']]

print(f"Outliers detectados: {len(outliers)}")
... print(outliers)
... 
... El chatbot no solo responde preguntas básicas, sino que puede hacer análisis de datos avanzado y detectar problemas reales en los datos contables.
... 
...  **ARQUITECTURA CON LLM Y SKILLS**
... 
... Usuario → Pregunta en lenguaje natural
...     ↓
... FastAPI recibe la consulta
...     ↓
... ┌─────────────────────────────────────────┐
... │         ROUTER DE INTENCIONES           │
... │  (LLM clasifica qué skill usar)         │
... └─────────────────────────────────────────┘
...     ↓
... ┌─────────────────────────────────────────┐
... │           SISTEMA DE SKILLS             │
... │  • Skill: Análisis Estadístico          │
... │  • Skill: Generación de Gráficos        │
... │  • Skill: Detección de Anomalías        │
... │  • Skill: Forecasting/Predicción        │
... │  • Skill: Generación de Reportes        │
... └─────────────────────────────────────────┘
...     ↓
... Ejecuta el skill correspondiente
...     ↓
... LLM formatea la respuesta en lenguaje natural
...     ↓
... Respuesta al usuario
... 
...  DEPENDENCIAS requirements.txt
... 
... TXT
... 
... fastapi==0.104.1
... uvicorn==0.24.0
... pandas==2.1.3
... pydantic==2.5.0
... openai==1.3.7
... matplotlib==3.8.2
... seaborn==0.13.0
... plotly==5.18.0
scikit-learn==1.3.2
numpy==1.26.2
python-dotenv==1.0.0

Bash

pip install -r requirements.txt

API KEYS

Archivo: .env

# OpenAI API Key (obtener en https://platform.openai.com/api-keys)
OPENAI_API_KEY=tu_api_key_aqui

# Opcional: Si querés usar modelos locales con Ollama
OLLAMA_BASE_URL=http://localhost:11434
USE_LOCAL_LLM=false

# Configuración del modelo
LLM_MODEL=gpt-3.5-turbo
LLM_TEMPERATURE=0.7

LLM

Archivo: backend/llm_client.py

Python

import os
from openai import OpenAI
from dotenv import load_dotenv
import requests
import json

load_dotenv()

class LLMClient:
    """
    Cliente LLM que soporta OpenAI y modelos locales (Ollama).
    """

    def __init__(self):
        self.use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
        self.model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))

        if not self.use_local:
            # OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("⚠️ OPENAI_API_KEY no configurada en .env")
            self.client = OpenAI(api_key=api_key)
        else:
            # Ollama (modelos locales)
            self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def generate_response(self, prompt: str, system_prompt: str = None) -> str:
        """
        Genera una respuesta usando el LLM configurado.
        """
        if self.use_local:
            return self._generate_with_ollama(prompt, system_prompt)
        else:
            return self._generate_with_openai(prompt, system_prompt)

    def _generate_with_openai(self, prompt: str, system_prompt: str = None) -> str:
        """Genera respuesta usando OpenAI API."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"❌ Error al generar respuesta con LLM: {str(e)}"

    def _generate_with_ollama(self, prompt: str, system_prompt: str = None) -> str:
        """Genera respuesta usando Ollama (modelos locales)."""
        full_prompt = ""
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()["response"].strip()
        except Exception as e:
            return f"❌ Error al generar respuesta con Ollama: {str(e)}"

    def classify_intent(self, query: str) -> dict:
        """
        Usa el LLM para clasificar la intención del usuario y determinar qué skill usar.
        """
        system_prompt = """
        Sos un clasificador de intenciones para un chatbot financiero.
        Analizá la consulta del usuario y devolvé un JSON con:
        - "skill": el nombre del skill a usar (stats_analysis, chart_generation, anomaly_detection, forecasting, report_generation, basic_query)
        - "parameters": dict con parámetros extraídos (ej: {"territory": "North", "account_type": "Gasto"})
        - "confidence": float entre 0 y 1

        Skills disponibles:
        - stats_analysis: análisis estadístico (media, mediana, desvío estándar)
        - chart_generation: generar gráficos
        - anomaly_detection: detectar outliers/anomalías
        - forecasting: predicción de tendencias
        - report_generation: generar reportes completos
        - basic_query: consultas simples de filtrado

        Devolvé SOLO el JSON, sin texto adicional.
        """

        prompt = f"Consulta del usuario: {query}"

        response = self.generate_response(prompt, system_prompt)

        try:
            # Extraer JSON de la respuesta
            result = json.loads(response)
            return result
        except json.JSONDecodeError:
            # Si falla el parsing, retornar basic_query por defecto
            return {
                "skill": "basic_query",
                "parameters": {},
                "confidence": 0.5
            }

**SKILLS**

Archivo: backend/skills/base_skill.py

Python

from abc import ABC, abstractmethod
import pandas as pd

class BaseSkill(ABC):
    """Clase base para todos los skills."""

    def __init__(self, df: pd.DataFrame):
        self.df = df

    @abstractmethod
    def execute(self, parameters: dict) -> dict:
        """
        Ejecuta el skill con los parámetros dados.
        Retorna: {"result": ..., "message": "..."}
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Retorna descripción del skill."""
        pass

Archivo: backend/skills/stats_analysis.py

Python

from .base_skill import BaseSkill
import pandas as pd
import numpy as np

class StatsAnalysisSkill(BaseSkill):
    """Skill para análisis estadístico de datos financieros."""

    def execute(self, parameters: dict) -> dict:
        """
        Realiza análisis estadístico sobre los datos.
        """
        territory = parameters.get("territory")
        account_type = parameters.get("account_type")

        # Filtrar datos según parámetros
        df_filtered = self.df.copy()

        if territory and territory != "todos":
            df_filtered = df_filtered[df_filtered['Territory'] == territory]

        if account_type and account_type != "todos":
            df_filtered = df_filtered[df_filtered['Account_Type'] == account_type]

        if len(df_filtered) == 0:
            return {
                "result": None,
                "message": "No hay datos para los parámetros especificados."
            }

        # Calcular estadísticas
        stats = {
            "total_transacciones": len(df_filtered),
            "monto_total": df_filtered['Amount'].sum(),
            "media": df_filtered['Amount'].mean(),
            "mediana": df_filtered['Amount'].median(),
            "desvio_estandar": df_filtered['Amount'].std(),
            "minimo": df_filtered['Amount'].min(),
            "maximo": df_filtered['Amount'].max(),
            "percentil_25": df_filtered['Amount'].quantile(0.25),
            "percentil_75": df_filtered['Amount'].quantile(0.75)
        }

        return {
            "result": stats,
            "message": "Análisis estadístico completado"
        }

    def get_description(self) -> str:
        return "Análisis estadístico de transacciones financieras"

Archivo: backend/skills/chart_generation.py


Python

from .base_skill import BaseSkill
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from io import BytesIO

class ChartGenerationSkill(BaseSkill):
    """Skill para generar gráficos de datos financieros."""

    def execute(self, parameters: dict) -> dict:
        """
        Genera gráficos basados en los parámetros.
        """
        chart_type = parameters.get("chart_type", "bar")
        territory = parameters.get("territory")
        account_type = parameters.get("account_type")

        # Filtrar datos
        df_filtered = self.df.copy()

        if territory and territory != "todos":
            df_filtered = df_filtered[df_filtered['Territory'] == territory]

        if account_type and account_type != "todos":
            df_filtered = df_filtered[df_filtered['Account_Type'] == account_type]

        # Configurar estilo
        sns.set_style("whitegrid")
        fig, ax = plt.subplots(figsize=(10, 6))

        if chart_type == "bar":
            # Gráfico de barras por territorio
            data = df_filtered.groupby('Territory')['Amount'].sum()
            data.plot(kind='bar', ax=ax, color='steelblue')
            ax.set_title('Montos por Territorio', fontsize=14, fontweight='bold')
            ax.set_xlabel('Territorio')
            ax.set_ylabel('Monto ($)')
            plt.xticks(rotation=45)

        elif chart_type == "line":
            # Gráfico de línea temporal
            df_filtered['Date'] = pd.to_datetime(df_filtered['Date'])
            data = df_filtered.set_index('Date').resample('M')['Amount'].sum()
            data.plot(kind='line', ax=ax, marker='o', color='green')
            ax.set_title('Tendencia Mensual', fontsize=14, fontweight='bold')
            ax.set_xlabel('Fecha')
            ax.set_ylabel('Monto ($)')

        elif chart_type == "pie":
            # Gráfico de torta por tipo de cuenta
            data = df_filtered.groupby('Account_Type')['Amount'].sum().abs()
            data.plot(kind='pie', ax=ax, autopct='%1.1f%%')
            ax.set_title('Distribución por Tipo de Cuenta', fontsize=14, fontweight='bold')
            ax.set_ylabel('')

        plt.tight_layout()

        # Convertir gráfico a base64
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()

        return {
            "result": {
                "chart_base64": img_base64,
                "chart_type": chart_type
            },
            "message": f"Gráfico {chart_type} generado exitosamente"
        }

    def get_description(self) -> str:
        return "Generación de gráficos financieros (barras, líneas, torta)"

Archivo: backend/skills/anomaly_detection.py

Python

from .base_skill import BaseSkill
import pandas as pd
import numpy as np

class AnomalyDetectionSkill(BaseSkill):
    """Skill para detectar anomalías y outliers en datos financieros."""

    def execute(self, parameters: dict) -> dict:
        """
        Detecta outliers usando método de desvío estándar y IQR.
        """
        threshold = parameters.get("threshold", 2.0)  # Número de desvíos estándar

        # Calcular estadísticas
        mean = self.df['Amount'].mean()
        std = self.df['Amount'].std()

        # Método 1: Desvío estándar
        upper_limit = mean + (threshold * std)
        lower_limit = mean - (threshold * std)

        outliers_std = self.df[
            (self.df['Amount'] > upper_limit) |
            (self.df['Amount'] < lower_limit)
        ].copy()

        # Método 2: IQR (Interquartile Range)
        Q1 = self.df['Amount'].quantile(0.25)
        Q3 = self.df['Amount'].quantile(0.75)
        IQR = Q3 - Q1

        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        outliers_iqr = self.df[
            (self.df['Amount'] < lower_bound) |
            (self.df['Amount'] > upper_bound)
        ].copy()

        # Combinar resultados
        result = {
            "total_transacciones": len(self.df),
            "estadisticas": {
                "media": mean,
                "desvio_estandar": std,
                "rango_normal": {
                    "minimo": lower_limit,
                    "maximo": upper_limit
                }
            },
            "outliers_metodo_std": {
                "cantidad": len(outliers_std),
                "transacciones": outliers_std[['Date', 'Account_Name', 'Amount', 'Territory']].head(10).to_dict('records')
            },
            "outliers_metodo_iqr": {
                "cantidad": len(outliers_iqr),
                "transacciones": outliers_iqr[['Date', 'Account_Name', 'Amount', 'Territory']].head(10).to_dict('records')
            },
            "recomendacion": "Revisar las transacciones marcadas como outliers para validar su correcto registro."
        }

        return {
            "result": result,
            "message": f"Detección de anomalías completada. Se encontraron {len(outliers_std)} outliers (método std) y {len(outliers_iqr)} outliers (método IQR)."
        }

    def get_description(self) -> str:
        return "Detección de anomalías y outliers en transacciones"

 Archivo: backend/skills/forecasting.py

Python

from .base_skill import BaseSkill
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

class ForecastingSkill(BaseSkill):
    """Skill para predicción de tendencias financieras."""

    def execute(self, parameters: dict) -> dict:
        """
        Predice tendencias futuras usando regresión lineal.
        """
        periods = parameters.get("periods", 3)  # Meses a predecir
        account_type = parameters.get("account_type", "todos")

        # Filtrar por tipo de cuenta
        df_filtered = self.df.copy()
        if account_type != "todos":
            df_filtered = df_filtered[df_filtered['Account_Type'] == account_type]

        # Agrupar por mes
        df_filtered['Date'] = pd.to_datetime(df_filtered['Date'])
        monthly_data = df_filtered.set_index('Date').resample('M')['Amount'].sum().reset_index()

        if len(monthly_data) < 3:
            return {
                "result": None,
                "message": "No hay suficientes datos históricos para realizar predicciones (mínimo 3 meses)."
            }

        # Preparar datos para regresión
        monthly_data['month_num'] = range(len(monthly_data))
        X = monthly_data[['month_num']]
        y = monthly_data['Amount']

        # Entrenar modelo
        model = LinearRegression()
        model.fit(X, y)

        # Predecir futuros períodos
        future_months = pd.DataFrame({
            'month_num': range(len(monthly_data), len(monthly_data) + periods)
        })

        predictions = model.predict(future_months)

        # Calcular métricas del modelo
        r_squared = model.score(X, y)
        trend = "creciente" if model.coef_[0] > 0 else "decreciente"

        result = {
            "modelo": {
                "tipo": "Regresión Lineal",
                "r_squared": r_squared,
                "coeficiente": model.coef_[0],
                "tendencia": trend
            },
            "predicciones": [
                {
                    "mes": i + 1,
                    "monto_predicho": pred
                }
                for i, pred in enumerate(predictions)
            ],
            "datos_historicos": monthly_data[['Date', 'Amount']].to_dict('records'),
            "recomendacion": f"La tendencia es {trend}. {'Se espera un aumento' if trend == 'creciente' else 'Se espera una disminución'} en los próximos {periods} meses."
        }

        return {
            "result": result,
            "message": f"Predicción completada para {periods} períodos. R² = {r_squared:.3f}"
        }

    def get_description(self) -> str:
        return "Predicción de tendencias financieras usando machine learning"

Archivo: backend/skills/report_generation.py

Python

from .base_skill import BaseSkill
import pandas as pd

class ReportGenerationSkill(BaseSkill):
    """Skill para generar reportes financieros completos."""

    def execute(self, parameters: dict) -> dict:
        """
        Genera un reporte financiero completo.
        """
        territory = parameters.get("territory", "todos")
        include_charts = parameters.get("include_charts", False)

        # Filtrar datos
        df_filtered = self.df.copy()
        if territory != "todos":
            df_filtered = df_filtered[df_filtered['Territory'] == territory]

        # Calcular métricas
        total_transacciones = len(df_filtered)
        total_monto = df_filtered['Amount'].sum()

        # Desglose por tipo de cuenta
        breakdown_by_type = df_filtered.groupby('Account_Type').agg({
            'Amount': ['count', 'sum', 'mean']
        }).round(2)

        # Top 5 cuentas
        top_accounts = df_filtered['Account_Name'].value_counts().head(5)

        # Análisis temporal
        df_filtered['Date'] = pd.to_datetime(df_filtered['Date'])
        monthly_trend = df_filtered.set_index('Date').resample('M')['Amount'].sum()

        # Generar reporte
        report = {
            "titulo": f"Reporte Financiero{' - Territorio ' + territory if territory != 'todos' else ' General'}",
            "resumen_ejecutivo": {
                "total_transacciones": total_transacciones,
                "monto_total": total_monto,
                "periodo": {
                    "desde": str(df_filtered['Date'].min().date()),
                    "hasta": str(df_filtered['Date'].max().date())
                }
            },
            "desglose_por_tipo": breakdown_by_type.to_dict(),
            "top_cuentas": top_accounts.to_dict(),
            "tendencia_mensual": monthly_trend.to_dict(),
            "indicadores_clave": {
                "ticket_promedio": df_filtered['Amount'].mean(),
                "transaccion_maxima": df_filtered['Amount'].max(),
                "transaccion_minima": df_filtered['Amount'].min()
            }
        }

        return {
            "result": report,
            "message": "Reporte financiero generado exitosamente"
        }

    def get_description(self) -> str:
        return "Generación de reportes financieros completos"

Archivo: backend/skills/__init__.py

Python

from .stats_analysis import StatsAnalysisSkill
from .chart_generation import ChartGenerationSkill
from .anomaly_detection import AnomalyDetectionSkill
from .forecasting import ForecastingSkill
from .report_generation import ReportGenerationSkill

__all__ = [
    'StatsAnalysisSkill',
    'ChartGenerationSkill',
    'AnomalyDetectionSkill',
    'ForecastingSkill',
    'ReportGenerationSkill'
]

**CHATBOT ACTUALIZADO CON LLM Y SKILLS**

Archivo: backend/chatbot_engine.py

import pandas as pd
from llm_client import LLMClient
from skills import (
    StatsAnalysisSkill,
    ChartGenerationSkill,
    AnomalyDetectionSkill,
    ForecastingSkill,
    ReportGenerationSkill
)

class ChatbotEngine:
    """
    Motor del chatbot con LLM y sistema de skills.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.llm = LLMClient()

        # Inicializar skills
        self.skills = {
            "stats_analysis": StatsAnalysisSkill(df),
            "chart_generation": ChartGenerationSkill(df),
            "anomaly_detection": AnomalyDetectionSkill(df),
            "forecasting": ForecastingSkill(df),
            "report_generation": ReportGenerationSkill(df)
        }

        print(f"🧠 Chatbot inicializado con {len(self.skills)} skills y LLM")

    def process_query(self, query: str) -> dict:
        """
        Procesa la consulta del usuario usando LLM para clasificar intención
        y ejecuta el skill correspondiente.
        """
        print(f"\n📥 Consulta recibida: {query}")

        # Paso 1: Clasificar intención con LLM
        intent = self.llm.classify_intent(query)
        print(f"🎯 Intención clasificada: {intent}")

        skill_name = intent.get("skill", "basic_query")
        parameters = intent.get("parameters", {})

        # Paso 2: Ejecutar el skill correspondiente
        if skill_name == "basic_query":
            # Consulta básica sin skill especializado
            result = self._handle_basic_query(query)
        elif skill_name in self.skills:
            # Ejecutar skill especializado
            skill = self.skills[skill_name]
            skill_result = skill.execute(parameters)
            result = skill_result["result"]
            message = skill_result["message"]
        else:
            result = None
            message = "No se encontró un skill adecuado para esta consulta."

        # Paso 3: Formatear respuesta con LLM
        formatted_response = self._format_response_with_llm(query, result, skill_name)

        return {
            "texto": formatted_response,
            "datos": result if isinstance(result, (list, dict)) else [],
            "skill_usado": skill_name,
            "chart_base64": result.get("chart_base64") if isinstance(result, dict) and "chart_base64" in result else None
        }

    def _handle_basic_query(self, query: str) -> dict:
        """Maneja consultas básicas sin skill especializado."""
        query_lower = query.lower()

        # Lógica básica de filtrado (similar al código anterior)
        if "territorio" in query_lower:
            return self._query_by_territory(query_lower)
        elif "gasto" in query_lower or "ingreso" in query_lower:
            return self._query_by_account_type(query_lower)
        else:
            return {"mensaje": "Consulta básica procesada"}

    def _query_by_territory(self, query: str) -> dict:
        """Filtra datos por territorio."""
        territorios = {"norte": "North", "sur": "South", "este": "East", "oeste": "West"}

        territorio_encontrado = None
        for key, value in territorios.items():
            if key in query:
                territorio_encontrado = value
                break

        if territorio_encontrado and 'Territory' in self.df.columns:
            datos = self.df[self.df['Territory'] == territorio_encontrado]
            total = datos['Amount'].sum()

            return {
                "territorio": territorio_encontrado,
                "total": total,
                "transacciones": len(datos)
            }
        return {}

    def _query_by_account_type(self, query: str) -> dict:
        """Filtra por tipo de cuenta."""
        if "gasto" in query:
            datos = self.df[self.df['Account_Type'] == 'Gasto']
            total = datos['Amount'].sum()
            tipo = "Gastos"
        else:
            datos = self.df[self.df['Account_Type'] == 'Ingreso']
            total = datos['Amount'].abs().sum()
            tipo = "Ingresos"

        return {
            "tipo": tipo,
            "total": total,
            "transacciones": len(datos)
        }

    def _format_response_with_llm(self, query: str, result: dict, skill_name: str) -> str:
        """
        Usa el LLM para formatear la respuesta en lenguaje natural.
        """
        system_prompt = """
        Sos un asistente financiero experto. Tu tarea es tomar los resultados de un análisis
        de datos y convertirlos en una respuesta clara, profesional y útil para el usuario.

        Reglas:
        - Sé conciso pero completo
        - Usa emojis para hacer la respuesta más visual
        - Incluye los números más importantes
        - Si hay gráficos, mencioná que se generaron
        - Si hay anomalías o insights importantes, destacalos
        - Usá formato markdown para mejor legibilidad
        """

        prompt = f"""
        Consulta del usuario: {query}

        Skill utilizado: {skill_name}

        Resultado del análisis:
        {result}

        Generá una respuesta clara y profesional para el usuario basada en estos resultados.
        """

        response = self.llm.generate_response(prompt, system_prompt)
        return response

**EJEMPLOS DE CONSULTAS AVANZADAS PARA LA DEMOSTRACION**

Archivo: demo_queries.txt

CONSULTAS PARA DEMOSTRAR CAPACIDADES DEL CHATBOT

CONSULTAS BÁSICAS (Sin LLM/Skills):
1. "¿Cuáles fueron los gastos del territorio norte?"
2. "Mostrame los ingresos de febrero"
3. "¿Cuál es el total de transacciones?"

CONSULTAS CON SKILL - ANÁLISIS ESTADÍSTICO:
4. "Hacé un análisis estadístico de los gastos del territorio sur"
5. "Quiero ver las estadísticas de las transacciones de ingresos"

CONSULTAS CON SKILL - GENERACIÓN DE GRÁFICOS:
6. "Generá un gráfico de barras de los gastos por territorio"
7. "Mostrame un gráfico de línea de la tendencia mensual de ingresos"
8. "Creá un gráfico de torta de la distribución por tipo de cuenta"

CONSULTAS CON SKILL - DETECCIÓN DE ANOMALÍAS:
9. "Detectá anomalías en las transacciones financieras"
10. "¿Hay outliers en los montos de las transacciones?"

CONSULTAS CON SKILL - FORECASTING:
11. "Predecí la tendencia de gastos para los próximos 3 meses"
12. "¿Cómo van a ser los ingresos en el próximo trimestre?"

CONSULTAS CON SKILL - GENERACIÓN DE REPORTES:
13. "Generá un reporte financiero completo del territorio norte"
14. "Quiero un reporte general de todas las transacciones"

CONSULTAS COMPLEJAS (Combinación de skills):
15. "Analizá estadísticamente los gastos del territorio sur y detectá anomalías"
16. "Generá un gráfico de la tendencia de ingresos y predecí los próximos 2 meses"

TIP PARA LA DEMOSTRACION:
- Empezá con consultas básicas para mostrar que funciona
- Luego mostrá una consulta con gráfico (impacto visual)
- Después mostrá detección de anomalías (valor de negocio)
- Terminá con forecasting (capacidad predictiva)

INTERFAZ WEB PARA MOSTRAR GRÁFICOS

frontend/script.js

Javascript

// Función para mostrar gráficos en el chat
function displayChart(chartBase64) {
    const messagesContainer = document.getElementById('chatMessages');
    const chartDiv = document.createElement('div');
    chartDiv.className = 'message bot-message';

    const imgDiv = document.createElement('div');
    imgDiv.className = 'message-content';
    imgDiv.innerHTML = `<img src="data:image/png;base64,${chartBase64}" style="max-width: 100%; border-radius: 10px; margin-top: 10px;" alt="Gráfico generado">`;

    chartDiv.appendChild(imgDiv);
    messagesContainer.appendChild(chartDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Modificar la función sendMessage para manejar gráficos
// (Reemplazar la sección donde se agrega la respuesta del bot)
/*
if (data.chart_base64) {
    displayChart(data.chart_base64);
}
addMessage(data.respuesta, 'bot');
*/

CÓMO **PROBARLO**

bash

# 1. Configurar API key en .env
# OPENAI_API_KEY=tu_key_aqui

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar el backend
cd backend
python main.py

# 4. Probar consultas avanzadas en la interfaz web
# Ejemplo: "Generá un gráfico de barras de los gastos por territorio"

CONSEJOS PARA LA PRESENTACIÓN
Empezar con lo básico: Mostrá una consulta simple para que vean que funciona
Impacto visual: Usá "Generá un gráfico de barras de gastos por territorio" - el gráfico aparece en el chat
Valor de negocio: Mostrá "Detectá anomalías en las transacciones" - encuentra outliers automáticamente
Capacidad predictiva: "Predecí la tendencia de gastos para los próximos 3 meses" - usa machine learning
Cierre con broche: "Generá un reporte financiero completo" - automatización total

El chatbot pasa de ser un simple buscador, a un "Asistente financiero inteligente con IA"

