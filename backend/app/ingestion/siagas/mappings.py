SOURCE = "SIAGAS"
URL = "https://geoportal.sgb.gov.br/server/rest/services/hidrologia/SIAGAS_MODDAD/FeatureServer/0"
VERSION = "siagas-v1"
# Registry descriptors only. No field here creates a time-series observation.
FIELDS = {
    "str_aquifero": "aquifer",
    "str_tipo_situacao": "registry_status",
    "str_uso_agua": "declared_use",
    "str_natureza_ponto": "point_type",
}
UNITS = {"num_profundidade": "m", "ne": "m", "nd": "m", "num_vazao_especifica": "m³/h/m"}
