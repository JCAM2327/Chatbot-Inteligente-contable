"""Tests for app/main.py — API endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app, state
from app.data_processing import load_data, load_csv, detectar_relaciones


@pytest.fixture(autouse=True)
def ensure_state_loaded():
    """Ensure app state is loaded before each test."""
    if state.df is None:
        df, etl_stats, merges = load_data()
        raw_dfs = {
            "GL": load_csv("GL.csv"),
            "chart_of_accounts": load_csv("chart_of_accounts.csv"),
            "territory": load_csv("territory.csv"),
            "calendar": load_csv("calendar.csv"),
        }
        modelo = detectar_relaciones(raw_dfs)
        state.update(df=df, etl_stats=etl_stats, merges=merges, modelo=modelo, data_source="sample")


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.anyio
async def test_resumen(client):
    resp = await client.get("/resumen")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_registros" in data
    assert data["total_registros"] > 0


@pytest.mark.anyio
async def test_modelo(client):
    resp = await client.get("/modelo")
    assert resp.status_code == 200
    data = resp.json()
    assert "relaciones" in data
    assert "tablas" in data
    assert "columnas_por_tabla" in data


@pytest.mark.anyio
async def test_chat_ventas(client):
    resp = await client.post("/chat", json={"question": "cuánto se vendió en 2019"})
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "2019" in data["answer"]


@pytest.mark.anyio
async def test_chat_gastos(client):
    resp = await client.post("/chat", json={"question": "cuánto se gastó"})
    assert resp.status_code == 200
    assert "answer" in resp.json()


@pytest.mark.anyio
async def test_chat_neto(client):
    resp = await client.post("/chat", json={"question": "resultado neto"})
    assert resp.status_code == 200
    assert "answer" in resp.json()


@pytest.mark.anyio
async def test_chat_pais(client):
    resp = await client.post("/chat", json={"question": "qué país tuvo mayor movimiento"})
    assert resp.status_code == 200
    assert "answer" in resp.json()


@pytest.mark.anyio
async def test_chat_cuenta(client):
    resp = await client.post("/chat", json={"question": "qué cuenta tiene mayor monto"})
    assert resp.status_code == 200
    assert "answer" in resp.json()


@pytest.mark.anyio
async def test_chat_etl(client):
    resp = await client.post("/chat", json={"question": "qué limpieza se hizo"})
    assert resp.status_code == 200
    assert "answer" in resp.json()


@pytest.mark.anyio
async def test_chat_unknown(client):
    resp = await client.post("/chat", json={"question": "blablabla"})
    assert resp.status_code == 200
    assert "No entendí" in resp.json()["answer"]


@pytest.mark.anyio
async def test_chat_returns_labels_and_values(client):
    resp = await client.post("/chat", json={"question": "total de ventas"})
    data = resp.json()
    assert "labels" in data
    assert "values" in data
    assert isinstance(data["labels"], list)
    assert isinstance(data["values"], list)
