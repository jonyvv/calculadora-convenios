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
- En ESCALA_SALARIAL_CATEGORIAS, copia literalmente el nombre completo del puesto/rol/categoria de la celda original. No lo abrevies, no lo partas por palabras, no lo conviertas en tags.
- Cada puesto de la escala debe ser una fila independiente. Si la tabla tiene 30 puestos, devuelve 30 filas.
- No uses nombres genericos como "categoria", "puesto", "operario" o "administrativo" si la tabla trae un nombre mas especifico.
- Si el codigo/categoria de origen es una letra o numero (A, B, 1, 2, etc.), ponelo en category_id y conserva el nombre completo en puesto_rol_categoria.
- Si la tabla contiene jornada completa, jornada reducida, media jornada, supervisor, coordinador, oficial, auxiliar, peon, conductor, chofer, administrativo u otros modificadores, mantenelos dentro de puesto_rol_categoria.
- Mantene importes tal como aparecen, con pesos, puntos y comas.
- Si un valor aplica por categoria, agrega una fila por categoria.
- Si un valor no esta indicado, escribi NO_INDICADO.
- En retenciones/deducciones, cada fila debe ser una retencion separada. No agrupes jubilacion, obra social, ley 19032, sindicato, seguro, contribucion solidaria ni aportes en una sola fila.
- Extrae siempre las retenciones legales argentinas si aparecen en el documento o en la tabla: Jubilacion 11%, Ley 19.032 / INSSJP / PAMI 3%, Obra Social 3%. Deben ser filas separadas.
- No reemplaces Jubilacion + Ley 19.032 + Obra Social por una fila generica llamada "Aportes" salvo que el documento solo lo muestre agregado y no permita separarlo.
- Si aparece "Aportes de ley" junto con el detalle de sus componentes, desagregalo en JUBILACION, LEY_19032 y OBRA_SOCIAL.
- Si el documento no trae codigo para una retencion, crea un code corto desde el concepto: JUBILACION, OBRA_SOCIAL, LEY_19032, SINDICATO, SEGURO_SEPELIO, CONTRIBUCION_SOLIDARIA, etc.
- Si hay varias vigencias o meses, conserva la columna/periodo original.
- Si un concepto depende de una carga mensual del usuario (kilometros, km, viajes, dias, comidas por dia, pernoctadas, comisiones, productividad variable), en observaciones escribi "CARGA_MANUAL" y conserva la unidad en base u observaciones.
- No conviertas viaticos por kilometro, viajes, pernoctadas o comisiones en importes automaticos mensuales.
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


MULTI_FILE_CONTEXT_PROMPT = """
Los archivos adjuntos pertenecen al MISMO convenio colectivo o al mismo expediente salarial.
Tratalos como documentos complementarios: convenio base, paritaria, escala salarial, acta acuerdo, resolucion, anexos o planillas.

Reglas de asociacion entre archivos:
- No crees convenios separados por archivo.
- Si un archivo trae reglas y otro trae escalas, unifica reglas + escalas en una sola salida.
- Si aparece el mismo CCT en un archivo y la escala salarial en otro, usa ese CCT para todo el resultado.
- Si una tabla de escala esta en Excel/PDF separado, conserva la relacion de cada puesto/rol/categoria con su basico.
- Si dos archivos tienen vigencias distintas, conserva el periodo original en la columna periodo y usa como version la vigencia salarial mas especifica.
- Si hay informacion repetida, prioriza la tabla mas detallada y agrega la fuente en observaciones.
- En observaciones indica el archivo fuente cuando ayude a entender de donde salio la regla.
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
            try:
                Path(temp_path).unlink(missing_ok=True)
            except PermissionError:
                pass

    def extract_documents(self, documents: list[tuple[str, bytes]]) -> str:
        if len(documents) == 1:
            filename, content = documents[0]
            return self.extract_text(filename, content)
        if not self.client.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini document extraction")

        import google.generativeai as genai

        genai.configure(api_key=self.client.settings.gemini_api_key)
        temp_paths = []
        uploaded_files = []
        try:
            for filename, content in documents:
                suffix = Path(filename).suffix or ".txt"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
                    temp.write(content)
                    temp_paths.append(temp.name)
                uploaded_files.append(genai.upload_file(temp_paths[-1], display_name=filename))

            file_list = "\n".join(f"- {filename}" for filename, _ in documents)
            model = genai.GenerativeModel(self.client.settings.gemini_model)
            response = model.generate_content(
                [
                    EXTRACTION_PROMPT,
                    MULTI_FILE_CONTEXT_PROMPT,
                    f"Archivos enviados para un unico convenio:\n{file_list}",
                    *uploaded_files,
                ],
                generation_config={
                    "temperature": 0,
                    "max_output_tokens": self.client.settings.gemini_max_output_tokens,
                },
                request_options={"timeout": self.client.settings.gemini_timeout_seconds},
            )
            return response.text or ""
        except Exception as exc:
            raise RuntimeError(f"Gemini multi-document extraction failed: {exc}") from exc
        finally:
            for temp_path in temp_paths:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except PermissionError:
                    pass


class MockGeminiDocumentTextExtractor(GeminiDocumentTextExtractor):
    def __init__(self):
        pass

    def extract_text(self, filename: str, content: bytes) -> str:
        return content.decode("utf-8", errors="ignore")

    def extract_documents(self, documents: list[tuple[str, bytes]]) -> str:
        return "\n\n".join(
            f"## SOURCE_DOCUMENT: {filename}\n{content.decode('utf-8', errors='ignore')}"
            for filename, content in documents
        )
