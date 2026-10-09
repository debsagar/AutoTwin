"""Read-only evidence tools; source values are never rewritten."""
import csv
import hashlib
import itertools
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


def preview(value, depth=0):
    if depth > 5:
        return "<nested value omitted>"
    if isinstance(value, dict):
        return {k: preview(v, depth + 1) for k, v in itertools.islice(value.items(), 3)}
    if isinstance(value, list):
        return [preview(v, depth + 1) for v in value[:3]]
    if isinstance(value, float) and not math.isfinite(value):
        return f"<nonstandard JSON number: {value}>"
    return value[:200] if isinstance(value, str) else value


def profile(path: Path, pointer: str = ""):
    """Describe CSV, JSON or XES structure, with explicit sampling limits."""
    result = {"bytes": path.stat().st_size, "format": path.suffix.lower()}
    if pointer and path.suffix.lower() != ".json":
        raise ValueError("JSON pointers apply to JSON files only")
    with path.open("rb") as stream:
        result["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            fields = reader.fieldnames
            if not fields or any(not f for f in fields) or len(set(fields)) != len(fields):
                raise ValueError("CSV requires unique nonempty headers")
            blanks, samples, count = Counter(), [], 0
            for count, row in enumerate(reader, 1):
                if None in row or None in row.values():
                    raise ValueError(f"CSV record {count}: inconsistent field count")
                blanks.update(k for k, v in row.items() if not v.strip())
                if count <= 3:
                    samples.append({"record": count, "values": {k: v[:200] for k, v in row.items()}})
        result.update(rows=count, columns=fields, empty_cells=dict(blanks), samples=samples,
                      limits="Full row/empty-cell counts. First 3 records only; cells clipped at 200 chars. N/A tokens retained.")
    elif path.suffix.lower() == ".json":
        if result["bytes"] > 20_000_000:
            raise ValueError("JSON preview currently limited to 20 MB per file")
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if pointer:
            if not pointer.startswith("/"):
                raise ValueError("JSON pointer must start with /")
            for part in pointer[1:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                if isinstance(value, list):
                    if not part.isdecimal():
                        raise ValueError("Expected a nonnegative JSON array index")
                    value = value[int(part)]
                else:
                    value = value[part]
        result.update(pointer=pointer, root_type=type(value).__name__,
                      root_entries=len(value) if isinstance(value, (dict, list)) else None,
                      keys=list(value)[:50] if isinstance(value, dict) else None,
                      sample=preview(value),
                      limits="Keys: first 50 at selected pointer. Preview: first 3 entries per object/list, depth <=5, strings <=200 chars. Marked nonstandard numbers are not nulls. No joins verified. Drill down with a JSON pointer for omitted fields.")
    elif path.suffix.lower() == ".xes":
        samples = []
        with path.open("rb") as stream:
            for _, element in ET.iterparse(stream, events=("end",)):
                if element.tag.rsplit("}", 1)[-1] == "trace":
                    samples.append(ET.tostring(element, encoding="unicode")[:6000])
                    element.clear()
                    if len(samples) == 3:
                        break
        result.update(samples=samples, limits="First 3 traces only, each clipped at 6000 chars; no total count or global conclusions.")
    else:
        raise ValueError("Supported formats: .csv, .json, .xes")
    return result


def column_summary(path: Path, column: str):
    """Exact CSV value counts on at most 100,000 records; never infer semantics."""
    if path.suffix.lower() != ".csv":
        raise ValueError("Column summaries currently support CSV only")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if column not in (reader.fieldnames or []):
            raise ValueError("Unknown column")
        counts, n = Counter(), 0
        for n, row in enumerate(itertools.islice(reader, 100_000), 1):
            if None in row or None in row.values():
                raise ValueError(f"CSV record {n}: inconsistent field count")
            counts[row[column]] += 1
        truncated = next(reader, None) is not None
    return {"column": column, "records_examined": n, "truncated": truncated,
            "distinct_values": len(counts), "literal_empty": counts[""],
            "most_common": [(v[:200], c) for v, c in counts.most_common(5)],
            "limits": "Counts concern examined records only; no date parsing or joins."}
