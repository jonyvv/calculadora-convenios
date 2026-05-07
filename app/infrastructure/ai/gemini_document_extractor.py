import tempfile
from pathlib import Path

from app.infrastructure.ai.gemini_client import GeminiClient


EXTRACTION_PROMPT = """
Sos un extractor tecnico de convenios colectivos argentinos para un sistema de liquidacion de sueldos.

Objetivo: transcribir y normalizar SOLO datos salariales verificables del archivo. No liquides sueldos, no inventes importes, no completes valores faltantes.

Extrae especialmente:
1. Escala salarial con cada puesto/rol/categoria y su basico asociado.
2. Haberes remunerativos con importe, porcentaje, formula o base.
3. Haberes no remunerativos con importe, porcentaje, formula o base.
4. Retenciones/deducciones con alicuota, importe y base.
5. Horas extra y otros conceptos si aparecen.

Reglas criticas:
- Si hay tablas, preserva la relacion fila-columna. Una fila de escala debe mantener puesto/rol/categoria + basico en la misma linea.
- No separes importes de sus categorias.
- No resumas tablas salariales.
- Mantene importes tal como aparecen, con pesos, puntos y comas.
- Si un valor aplica por categoria, agrega una fila por categoria.
- Si un valor no esta indicado, escribi NO_INDICADO.
- Si hay varias vigencias o meses, conserva la columna/periodo original.
- No expliques nada fuera de las secciones pedidas.

Devuelve texto plano en este formato exacto:

## METADATA
convenio:
actividad:
sindicato:
jurisdiccion:
vigencia_desde:
vigencia_hasta:
fuente:

## ESCALA_SALARIAL_CATEGORIAS
| category_id | puesto_rol_categoria | periodo | basico | total_remunerativo | observaciones |

## HABERES_REMUNERATIVOS
| code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |

## HABERES_NO_REMUNERATIVOS
| code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |

## RETENCIONES_DEDUCCIONES
| code | concepto | porcentaje | importe | base | observaciones |

## HORAS_EXTRA
| code | concepto | multiplicador | porcentaje | base | observaciones |

## AMBIGUEDADES
- 
"""


class GeminiDocumentTextExtractor:
    def __init__(self, client: GeminiClient):
        self.client = client

    def extract_text(self, filename: str, content: bytes) -> str:
        if not self.client.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini document extraction")

        import google.generativeai as genai

        genai.configure(api_key=self.client.settings.gemini_api_key)
        suffix = Path(filename).suffix or ".txt"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp.write(content)
            temp_path = temp.name

        try:
            uploaded = genai.upload_file(temp_path, display_name=filename)
            model = genai.GenerativeModel(self.client.settings.gemini_model)
            response = model.generate_content(
                [
                    EXTRACTION_PROMPT,
                    uploaded,
                ],
                generation_config={
                    "temperature": 0,
                    "max_output_tokens": self.client.settings.gemini_max_output_tokens,
                },
                request_options={"timeout": self.client.settings.gemini_timeout_seconds},
            )
            return response.text or ""
        except Exception as exc:
            raise RuntimeError(f"Gemini document extraction failed: {exc}") from exc
        finally:
            Path(temp_path).unlink(missing_ok=True)


class MockGeminiDocumentTextExtractor(GeminiDocumentTextExtractor):
    def __init__(self):
        pass

    def extract_text(self, filename: str, content: bytes) -> str:
        return content.decode("utf-8", errors="ignore")
