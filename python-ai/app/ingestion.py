import ast
import csv
import html
import io
import json
import re
from pathlib import Path
from xml.etree import ElementTree

import yaml
from openpyxl import load_workbook

from .embeddings import EmbeddingProvider, HashEmbeddingProvider
from .semantic_chunking import semantic_chunk

MAX_CHUNKS = 500
CODE_SUFFIXES = {
    ".go", ".py", ".ts", ".tsx", ".js", ".java", ".tf", ".cs", ".kt", ".cpp", ".rs", ".sql"
}


def parse_file(
    filename: str,
    content: bytes,
    schema: str = "",
    embedding_provider: EmbeddingProvider | None = None,
) -> list[str]:
    provider = embedding_provider or HashEmbeddingProvider()
    units = parse_units(filename, content, schema)
    return semantic_chunk(units[:MAX_CHUNKS], provider)[:MAX_CHUNKS]


def parse_units(filename: str, content: bytes, schema: str = "") -> list[str]:
    """Parse deterministic structural units without choosing a chunking strategy."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".xlsx":
        units = _parse_xlsx_units(content, schema)
    elif suffix == ".csv":
        units = _parse_csv_units(content)
    elif suffix in {".yaml", ".yml"}:
        units = _parse_structured_units(yaml.safe_load(content.decode("utf-8-sig")))
    elif suffix == ".json":
        units = _parse_structured_units(json.loads(content.decode("utf-8-sig")))
    elif suffix in {".drawio", ".xml"}:
        units = _parse_drawio_units(content)
    elif suffix in {".puml", ".plantuml"}:
        units = _parse_plantuml_units(content.decode("utf-8-sig"))
    elif suffix in CODE_SUFFIXES:
        units = _parse_code_units(content.decode("utf-8-sig"), suffix)
    elif suffix in {".md", ".txt"}:
        units = _parse_document_units(content.decode("utf-8-sig"), suffix)
    else:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")
    return units[:MAX_CHUNKS]


def _parse_xlsx_units(content: bytes, schema: str) -> list[str]:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheets = [workbook[schema]] if schema and schema in workbook.sheetnames else list(workbook.worksheets)
    units: list[str] = []
    for sheet in sheets:
        rows = sheet.iter_rows(values_only=True)
        headers = [
            str(value).strip() if value is not None else f"column_{index + 1}"
            for index, value in enumerate(next(rows, []))
        ]
        for row_number, row in enumerate(rows, start=2):
            values = [
                f"{headers[index]}: {value}"
                for index, value in enumerate(row)
                if value not in (None, "")
            ]
            if values:
                units.append(f"Sheet: {sheet.title}. Row: {row_number}. " + "; ".join(values))
    return units


def _parse_csv_units(content: bytes) -> list[str]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    return [
        f"Row: {index}. " + "; ".join(f"{key}: {value}" for key, value in row.items() if value)
        for index, row in enumerate(reader, start=2)
        if any(row.values())
    ]


def _parse_structured_units(value: object, path: str = "root") -> list[str]:
    if isinstance(value, list):
        return [
            chunk
            for index, item in enumerate(value)
            for chunk in _parse_structured_units(item, f"{path}[{index}]")
        ]
    if isinstance(value, dict):
        scalar = [
            f"{key}: {item}" for key, item in value.items() if not isinstance(item, (dict, list))
        ]
        chunks = [f"{path}. " + "; ".join(scalar)] if scalar else []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                chunks.extend(_parse_structured_units(item, f"{path}.{key}"))
        return chunks
    return [f"{path}: {value}"]


def _parse_drawio_units(content: bytes) -> list[str]:
    root = ElementTree.fromstring(content)
    cells = {cell.get("id", ""): cell for cell in root.iter("mxCell")}
    entities = {
        cell_id: _clean_label(cell.get("value", ""))
        for cell_id, cell in cells.items()
        if cell.get("vertex") == "1" and _clean_label(cell.get("value", ""))
    }
    relations: dict[str, list[str]] = {cell_id: [] for cell_id in entities}
    standalone: list[str] = []
    for cell in cells.values():
        if cell.get("edge") != "1":
            continue
        source_id, target_id = cell.get("source", ""), cell.get("target", "")
        source, target = entities.get(source_id, source_id), entities.get(target_id, target_id)
        label = _clean_label(cell.get("value", ""))
        relation = f"Relationship: {source} -> {target}" + (f". Label: {label}" if label else "")
        if source_id in relations:
            relations[source_id].append(f"Outgoing {relation}")
        if target_id in relations:
            relations[target_id].append(f"Incoming {relation}")
        if source_id not in relations and target_id not in relations and (source or target):
            standalone.append(relation)
    units = [
        "\n".join([f"Diagram entity: {label}", *relations[cell_id]])
        for cell_id, label in entities.items()
    ]
    return units + standalone


def _parse_plantuml_units(value: str) -> list[str]:
    return [
        line.strip()
        for line in value.splitlines()
        if line.strip() and not line.strip().startswith(("'", "@start", "@end"))
    ]


def _clean_label(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value))).strip()


def _parse_python_units(value: str) -> list[str]:
    lines = value.splitlines()
    try:
        tree = ast.parse(value)
    except SyntaxError:
        return _parse_generic_code_units(value)
    nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if not nodes:
        return [value.strip()] if value.strip() else []
    starts = [max(0, node.lineno - 1) for node in nodes]
    units: list[str] = []
    for index, start in enumerate(starts):
        if index == 0:
            start = 0
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        units.append("\n".join(lines[start:end]).strip())
    return [unit for unit in units if unit]


DECLARATION = re.compile(
    r"^\s*(?:export\s+|public\s+|private\s+|protected\s+|static\s+|async\s+)*"
    r"(?:class|interface|type|enum|function|func|def|module|package|resource|data|provider|"
    r"variable|output|impl|struct|trait)\b"
)


def _parse_generic_code_units(value: str) -> list[str]:
    lines = value.splitlines()
    starts = [index for index, line in enumerate(lines) if DECLARATION.match(line)]
    if not starts:
        paragraphs = re.split(r"\n\s*\n", value)
        return [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]
    units: list[str] = []
    for index, start in enumerate(starts):
        if index == 0:
            start = 0
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        units.append("\n".join(lines[start:end]).strip())
    return [unit for unit in units if unit]


def _parse_code_units(value: str, suffix: str) -> list[str]:
    return _parse_python_units(value) if suffix == ".py" else _parse_generic_code_units(value)


def _parse_document_units(value: str, suffix: str) -> list[str]:
    if suffix == ".md":
        starts = [match.start() for match in re.finditer(r"(?m)^#{1,6}\s+", value)]
        if starts:
            starts = ([0] if starts[0] else []) + starts
            return [
                value[start:end].strip()
                for start, end in zip(starts, starts[1:] + [len(value)], strict=True)
                if value[start:end].strip()
            ]
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n", value) if paragraph.strip()]
