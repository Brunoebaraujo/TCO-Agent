"""
Extrai blocos estruturados da resposta em texto do agente TCO.

O agente emite dois tipos de bloco estruturado:
- <<<TCO_RESULT>>> ... <<<END_TCO_RESULT>>>: JSON com o resultado completo do cálculo.
- <<<PENDING>>> ... <<<END_PENDING>>>: texto corrido com as pendências para o vendedor
  copiar e enviar ao cliente quando precisar pausar a conversa.

Ambos são extraídos e retornados separadamente do texto conversacional, para que o
frontend renderize cada um de forma adequada (dashboard para o TCO, painel copiável
para as pendências) em vez de mostrar o conteúdo bruto ao usuário.
"""
import json
import re
from typing import Optional, Tuple

_COMPLETE_PATTERN = re.compile(
    r"<<<TCO_RESULT>>>\s*(.*?)\s*<<<END_TCO_RESULT>>>",
    re.DOTALL,
)

_TRUNCATED_PATTERN = re.compile(
    r"<<<TCO_RESULT>>>\s*(.*)$",
    re.DOTALL,
)

_PENDING_PATTERN = re.compile(
    r"<<<PENDING>>>\s*(.*?)\s*<<<END_PENDING>>>",
    re.DOTALL,
)


def _try_repair_truncated_json(raw: str) -> Optional[dict]:
    """
    Tenta fechar um JSON cortado no meio, removendo a última propriedade
    incompleta e fechando as chaves/colchetes pendentes.
    Retorna None se não for recuperável.
    """
    raw = raw.strip().rstrip(",")

    lines = raw.split("\n")
    while lines and not re.search(r'[\]}",]\s*$', lines[-1].rstrip()):
        lines.pop()
    candidate = "\n".join(lines).rstrip().rstrip(",")

    open_braces = candidate.count("{") - candidate.count("}")
    open_brackets = candidate.count("[") - candidate.count("]")

    closing = ("]" * max(open_brackets, 0)) + ("}" * max(open_braces, 0))
    attempt = candidate + closing

    try:
        return json.loads(attempt)
    except json.JSONDecodeError:
        return None


def extract_tco_result(text: str) -> Tuple[str, Optional[dict], Optional[str]]:
    """
    Retorna (texto_limpo, tco_result_ou_None, pending_text_ou_None).

    Extrai e remove da resposta:
    - O bloco <<<TCO_RESULT>>> (se presente) → retorna como dict
    - O bloco <<<PENDING>>> (se presente) → retorna como string de texto

    O texto restante (conversacional) é retornado limpo, sem os blocos.
    """
    pending_text: Optional[str] = None
    tco_result: Optional[dict] = None

    # Extrai PENDING primeiro (não tem lógica de repair — é só texto)
    pending_match = _PENDING_PATTERN.search(text)
    if pending_match:
        pending_text = pending_match.group(1).strip()
        text = _PENDING_PATTERN.sub("", text)

    # Extrai TCO_RESULT
    match = _COMPLETE_PATTERN.search(text)
    if match:
        raw_json = match.group(1)
        try:
            tco_result = json.loads(raw_json)
            text = _COMPLETE_PATTERN.sub("", text)
        except json.JSONDecodeError:
            pass
    else:
        truncated_match = _TRUNCATED_PATTERN.search(text)
        if truncated_match:
            data = _try_repair_truncated_json(truncated_match.group(1))
            if data:
                tco_result = data
                text = _TRUNCATED_PATTERN.sub("", text)

    clean_text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return clean_text, tco_result, pending_text
