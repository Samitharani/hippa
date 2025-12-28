# app/services/phi_detector.py
import re
from typing import List, Dict
PHONE_LINE_RE = re.compile(r'^(.*Phone\s*:\s*.*)$', re.IGNORECASE | re.MULTILINE)
SSN_RE = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
DOB_LINE_RE = re.compile(r'^(.*DOB\s*:\s*.*)$', re.IGNORECASE | re.MULTILINE)
ADDR_KEYWORDS = ['Street','St.','Avenue','Apt','Rd','Road','Boulevard','Blvd','Lane','Ln','Suite']
# name heuristic: capitalized two words at start of line (very naive)
NAME_LINE_RE = re.compile(r'^(.*Name\s*:\s*.*)$', re.IGNORECASE | re.MULTILINE)


def detect_phi(text: str) -> List[Dict]:
    items = []
    for m in PHONE_LINE_RE.finditer(text):
        items.append({
        "field": "phone",
        "value": m.group(1),
        "start": m.start(1),
        "end": m.end(1)
    })
    for m in SSN_RE.finditer(text):
        items.append({"field":"ssn","value":m.group(0),"start":m.start(),"end":m.end()})
    for m in DOB_LINE_RE.finditer(text):
        items.append({
        "field": "dob",
        "value": m.group(1),
        "start": m.start(1),
        "end": m.end(1)
    })
    for m in NAME_LINE_RE.finditer(text):
        items.append({
        "field": "name",
        "value": m.group(1),
        "start": m.start(1),
        "end": m.end(1)
    })

    # naive address detection
    for kw in ADDR_KEYWORDS:
        idx = text.find(kw)
        if idx!=-1:
            # find line
            start = text.rfind('\n', 0, idx) + 1
            end = text.find('\n', idx)
            if end == -1: end = len(text)
            value = text[start:end].strip()
            items.append({"field":"address","value":value,"start":start,"end":end})
            break
    # dedupe by (start,end)
    seen = set()
    dedup=[]
    for it in items:
        key=(it['start'],it['end'],it['field'])
        if key in seen: continue
        seen.add(key); dedup.append(it)
    return dedup
