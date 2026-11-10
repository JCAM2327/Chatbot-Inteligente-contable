import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

__all__ = ["redactar_respuesta", "formatear_con_ia", "cargar_env"]

MODELO_GEMINI = "gemini-2.0-flash"


def cargar_env() -> Path | None:
    """Carga .env si existe; si no, usa las variables del proceso.

    Render y otros servicios definen las variables de entorno directamente,
    por lo que la ausencia de .env no debe impedir arrancar la aplicación.
    """
    script_dir = Path(__file__).resolve().parent
    env_path = script_dir
    for _ in range(6):
        candidate = env_path / ".env"
        if candidate.is_file():
            load_dotenv(dotenv_path=candidate, verbose=False)
            logger.info(".env cargado desde: %s", candidate)
            return candidate
        env_path = env_path.parent
    logger.info("Sin archivo .env; se usan variables de entorno del proceso")
    return None


def validar_clave() -> str:
    """Valida que GEMINI_API_KEY exista y tenga formato esperado."""
    api_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("AI_API_KEY", "")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY no esta definida. "
            "Copia tu clave de Google AI Studio en el archivo .env "
            "o configúrala como variable de entorno."
        )
    if api_key.startswith("AQ."):
        logger.info("Clave Gemini (formato AQ.) cargada correctamente")
    else:
        logger.warning("La clave no empieza con 'AQ.' — verificar formato")
    return api_key


def _es_groq(url: str) -> bool:
    return "groq.com" in url


def _extraer_respuesta(data: dict, es_groq: bool) -> str | None:
    if es_groq:
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
    return None


def _llamar_gemini(
    system_msg: str, prompt: str, fallback: str, temp: float, max_tokens: int
) -> tuple[str, bool]:
    """Llama a Gemini usando google-genai SDK."""
    api_key = validar_clave()
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODELO_GEMINI,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_msg,
                temperature=temp,
                max_output_tokens=max_tokens,
            ),
        )
        texto = response.text
        if texto and texto.strip():
            return texto.strip(), True
    except Exception as e:
        logger.warning("Error al llamar a Gemini SDK: %s", e)
    return fallback, False


def _llamar_groq(
    system_msg: str, prompt: str, fallback: str, api_url: str, api_key: str, temp: float, max_tokens: int
) -> tuple[str, bool]:
    """Llama a Groq usando httpx (API REST directa)."""
    import httpx

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        "temperature": temp,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        with httpx.Client(timeout=15) as http_client:
            resp = http_client.post(api_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            texto = _extraer_respuesta(data, es_groq=True)
            if texto and texto.strip():
                return texto.strip(), True
    except Exception as e:
        logger.warning("Error al llamar a Groq: %s", e)
    return fallback, False


def redactar_respuesta(texto_original: str, pregunta: str, modo: str = "reformat") -> tuple[str, bool]:
    """Devuelve (texto_formateado, fue_modificado_por_ia).

    modo="reformat": reescribe datos numéricos en lenguaje natural.
    modo="free": charla libre, responde cualquier pregunta con ayuda del contexto.
    """
    cargar_env()
    if os.getenv("USE_AI_FORMATTER", "").lower() != "true":
        return texto_original, False

    api_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("AI_API_KEY", "")
    api_url = os.getenv("AI_API_URL", "").rstrip("/")
    if not api_key:
        logger.warning("USE_AI_FORMATTER=true pero no hay GEMINI_API_KEY")
        return texto_original, False

    if modo == "free":
        system_msg = (
            "Sos un asistente contable experto pero respondés de forma INFORMAL y AMIGABLE, "
            "como un colega explicándole algo a otro. Usás frases como:\n"
            "- \"Hola, mirá...\"\n"
            "- \"Te cuento que...\"\n"
            "- \"Dale, acá va la info...\"\n"
            "- \"Che, con respecto a...\"\n\n"
            "REGLAS:\n"
            "1. Si la pregunta es sobre contabilidad, finanzas o datos del libro mayor, "
            "usá SOLO el contexto proporcionado para responder.\n"
            "2. Si la pregunta es de otro tema (deportes, política, cultura, etc.), "
            "respondé brevemente con lo que sepas y luego ofrecé ayuda contable.\n"
            "3. **NUNCA inventes números financieros** — si no están en el contexto, decilo.\n"
            "4. Sé conversacional y cálido, no un menú de opciones.\n\n"
            f"Contexto del libro mayor:\n{texto_original}"
        )
        prompt = pregunta
        max_tokens = 500
        temp = 0.7
    else:
        system_msg = (
            "Sos un asistente contable experto pero respondés de forma INFORMAL y AMIGABLE, "
            "como un amigo explicando datos. Tu estilo incluye:\n"
            "- \"Hola, mirá...\"\n"
            "- \"Te cuento que...\"\n"
            "- \"Dale, acá va la data...\"\n"
            "- \"Che, con respecto a tu consulta...\"\n\n"
            "NUNCA inventes números ni agregues información que no esté presente. "
            "Usá SOLO los datos proporcionados."
        )
        prompt = (
            f"Pregunta del usuario: {pregunta}\n\n"
            f"Datos del libro mayor:\n{texto_original}\n\n"
            "Respondé de forma informal y amigable usando los datos de arriba. "
            "NUNCA inventes números. Usá SOLO los datos proporcionados. "
            "Incluí los montos exactos con su formato $X,XXX.XX."
        )
        max_tokens = 400
        temp = 0.5

    if _es_groq(api_url):
        return _llamar_groq(system_msg, prompt, texto_original, api_url, api_key, temp, max_tokens)
    else:
        return _llamar_gemini(system_msg, prompt, texto_original, temp, max_tokens)


def formatear_con_ia(texto_original: str, pregunta: str) -> str:
    return redactar_respuesta(texto_original, pregunta)
