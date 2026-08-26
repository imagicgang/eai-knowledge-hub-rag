import csv
import html
import io
import json
import re
from pathlib import Path
from xml.etree import ElementTree

import yaml
from openpyxl import load_workbook

MAX_CHUNKS = 500


def parse_file(filename: str, content: bytes, schema: str = "") -> list[str]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".xlsx":
        return _parse_xlsx(content, schema)
    if suffix == ".csv":
        return _parse_csv(content)
    if suffix in {".yaml", ".yml"}:
        return _parse_structured(yaml.safe_load(content.decode("utf-8-sig")))
    if suffix == ".json":
        return _parse_structured(json.loads(content.decode("utf-8-sig")))
    if suffix in {".drawio", ".xml"}:
        return _parse_drawio(content)
    if suffix in {".go", ".py", ".ts", ".tsx", ".js", ".java", ".tf", ".md", ".txt"}:
        return _chunk_text(content.decode("utf-8-sig"))
    raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")


def _parse_xlsx(content: bytes, schema: str) -> list[str]:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook[schema] if schema and schema in workbook.sheetnames else workbook.active
    rows = sheet.iter_rows(values_only=True)
    headers = [str(value).strip() if value is not None else f"column_{index + 1}" for index, value in enumerate(next(rows, []))]
    chunks = []
    for row in rows:
        values = [f"{headers[index]}: {value}" for index, value in enumerate(row) if value not in (None, "")]
        if values:
            chunks.append(f"Sheet: {sheet.title}. " + "; ".join(values))
    return chunks[:MAX_CHUNKS]


def _parse_csv(content: bytes) -> list[str]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    return ["; ".join(f"{key}: {value}" for key, value in row.items() if value) for row in reader][:MAX_CHUNKS]


def _parse_structured(value: object, path: str = "root") -> list[str]:
    if isinstance(value, list):
        chunks = []
        for index, item in enumerate(value):
            chunks.extend(_parse_structured(item, f"{path}[{index}]"))
        return chunks[:MAX_CHUNKS]
    if isinstance(value, dict):
        scalar = [f"{key}: {item}" for key, item in value.items() if not isinstance(item, (dict, list))]
        chunks = [f"{path}. " + "; ".join(scalar)] if scalar else []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                chunks.extend(_parse_structured(item, f"{path}.{key}"))
        return chunks[:MAX_CHUNKS]
    return [f"{path}: {value}"]


def _parse_drawio(content: bytes) -> list[str]:
    root = ElementTree.fromstring(content)
    cells = {cell.get("id", ""): cell for cell in root.iter("mxCell")}
    chunks = []
    for cell in cells.values():
        value = _clean_label(cell.get("value", ""))
        if cell.get("edge") == "1":
            source = _clean_label(cells.get(cell.get("source", ""), ElementTree.Element("x")).get("value", cell.get("source", "")))
            target = _clean_label(cells.get(cell.get("target", ""), ElementTree.Element("x")).get("value", cell.get("target", "")))
            if source or target:
                chunks.append(f"Relationship: {source} -> {target}" + (f". Label: {value}" if value else ""))
        elif cell.get("vertex") == "1" and value:
            chunks.append(f"Diagram entity: {value}")
    return chunks[:MAX_CHUNKS]


def _clean_label(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", html.unescape(value)).strip()


def _chunk_text(value: str, lines_per_chunk: int = 40) -> list[str]:
    lines = [line.rstrip() for line in value.splitlines()]
    return ["\n".join(lines[index : index + lines_per_chunk]).strip() for index in range(0, len(lines), lines_per_chunk) if "\n".join(lines[index : index + lines_per_chunk]).strip()][:MAX_CHUNKS]
