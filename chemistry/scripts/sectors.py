#!/usr/bin/env python3
"""Municipality → Riyadh amanah sector mapping for the chemistry pipeline.

The 5-sector taxonomy (East/North/West/Central/South branches) comes from the
microbiology schema `lab_data_2025_v1.yaml`. Chemistry never had a sector
column; this module adds one, with normalization for the messy municipality
values (`البلدية/ الروضة`, typos, private samples, junk).

Public API:
  sector_for(municipality) -> (sector | None, flag)
      flag ∈ {None (mapped), 'private', 'no_municipality', 'unmapped'}
"""
from __future__ import annotations
import re

# sub-municipality (بلدية) → sector branch name
SUB_TO_SECTOR = {
    "الروضة": "فرع أمانة في الشرق", "الشرق": "فرع أمانة في الشرق",
    "الشمال": "فرع أمانة في الشمال",
    "العريجاء": "فرع أمانة في الغرب", "عرقة": "فرع أمانة في الغرب", "نمار": "فرع أمانة في الغرب",
    "الملز": "فرع أمانة في المنطقة الوسطى", "المعذر": "فرع أمانة في المنطقة الوسطى",
    "العليا": "فرع أمانة في المنطقة الوسطى", "الشميسي": "فرع أمانة في المنطقة الوسطى",
    "البطحاء": "فرع أمانة في المنطقة الوسطى",
    "العزيزية": "فرع أمانة في الجنوب", "الحاير": "فرع أمانة في الجنوب",
    "الشفا": "فرع أمانة في الجنوب", "السلي": "فرع أمانة في الجنوب", "النسيم": "فرع أمانة في الجنوب",
}

# spelling variants / typos of the sub-municipality names → canonical sub
SUB_ALIASES = {
    "الشفاء": "الشفا", "لعليا": "العليا", "اللملز": "الملز", "بطحاء": "البطحاء",
    "شمال": "الشمال", "العريجا": "العريجاء", "عرقه": "عرقة", "الروضه": "الروضة",
    "النسيم ": "النسيم", "المعذر ": "المعذر",
}

# raw values that already name a sector directly (from schema sector_raw_aliases)
SECTOR_RAW_ALIASES = {
    "وسط الرياض": "فرع أمانة في المنطقة الوسطى",
    "القطاع وسط الرياض": "فرع أمانة في المنطقة الوسطى",
    "قطاع الشمال": "فرع أمانة في الشمال",
    "الشمال": "فرع أمانة في الشمال",
}

_PRIVATE = ("عينة خاصة", "private")
_PREFIX = re.compile(r"^\s*(?:-\s*)?(?:البلدية|بلدية|بلدبة)\s*/?\s*")


def _strip(m: str) -> str:
    s = str(m).strip().strip("()").strip()
    s = _PREFIX.sub("", s).strip()
    return " ".join(s.split())


def sector_for(municipality):
    """Return (sector | None, flag)."""
    if municipality is None:
        return None, "no_municipality"
    raw = str(municipality).strip()
    low = raw.lower()
    if not raw or raw in ("-", "NA", "nan", "<NA>"):
        return None, "no_municipality"
    if any(p in low or p in raw for p in _PRIVATE):
        return None, "private"
    # direct sector-name aliases first
    if raw in SECTOR_RAW_ALIASES:
        return SECTOR_RAW_ALIASES[raw], None
    sub = _strip(raw)
    sub = SUB_ALIASES.get(sub, sub)
    sec = SUB_TO_SECTOR.get(sub) or SECTOR_RAW_ALIASES.get(sub)
    if sec:
        return sec, None
    return None, "unmapped"
