import os
import re
import json
from typing import Dict, Any, List

# Regex helpers
ROMAN = re.compile(r"^[IVXLCDM]+$")
DIGIT = re.compile(r"^\d+$")
LETTER = re.compile(r"^[a-z]$")
BULLET = re.compile(r"^\s*-\s+")

def is_roman(s): return bool(ROMAN.fullmatch(s or ""))
def is_digit(s): return bool(DIGIT.fullmatch(s or ""))
def is_letter(s): return bool(LETTER.fullmatch(s or ""))

def clean_text(x):
    if x is None: return ""
    x = str(x).replace("\r", "").strip()
    x = re.sub(r"[ \t]+\n", "\n", x)
    x = re.sub(r"\s+", " ", x)
    return x.strip()

def split_docs(text: str) -> List[str]:
    if not text: return []
    lines = text.replace("\r", "").split("\n")
    out, cur = [], None
    for ln in lines:
        if BULLET.match(ln):
            if cur: out.append(cur.strip())
            cur = BULLET.sub("", ln).strip()
        else:
            if cur is None:
                cur = ln.strip()
            else:
                cur += " " + ln.strip()
    if cur and cur.strip(): out.append(cur.strip())
    out = [re.sub(r"\s+", " ", d).strip() for d in out if d and d.strip()]
    return out

def split_title(text: str) -> list:
    if not text:
        return []
    text = clean_text(text)
    parts = re.split(r",|\n", text)
    return [p.strip() for p in parts if p.strip()]

def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data: Dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)