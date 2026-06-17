"""
Extrai o bloco estruturado de resultado de TCO da resposta em texto do agente.

O agente é instruído (via system prompt) a emitir um bloco JSON delimitado por
<<<TCO_RESULT>>> ... <<<END_TCO_RESULT>>> quando o cálculo estiver completo.
Esta função separa esse bloco do texto conversacional, para que o frontend
possa renderizar a tabela/gráfico em vez de mostrar o JSON cru.
"""
import json
import re
from typing import Optional, Tuple

_PATTERN = re.compile(
    r"<<<TCO_RESULT>>>\s*(.*?)\s*<<<END_TCO_RESULT>>>",
    re.DOTALL,
)


def extract_tco_result(text: str) -> Tuple[str, Optional[dict]]:
    """
    Retorna (texto_sem_o_bloco, dados_estruturados_ou_None).

    Se o JSON dentro dos marcadores estiver malformado, retorna o texto
    original intacto e None — preferimos mostrar o texto bruto ao vendedor
    do que falhar silenciosamente ou quebrar a resposta.
    """
    match = _PATTERN.search(text)
    if not match:
        return text, None

    raw_json = match.group(1)
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return text, None

    clean_text = _PATTERN.sub("", text)
    # Normaliza 3+ quebras de linha consecutivas (resíduo da remoção do bloco) para no máximo 2
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()
    return clean_text, data
