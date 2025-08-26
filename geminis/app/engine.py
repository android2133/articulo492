#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Resalta / subraya automáticamente valores en un PDF.
- Primero intenta texto nativo; si no, usa OCR (Tesseract).
- Búsqueda estricta para evitar falsos positivos (palabras sueltas como "a", "la", etc.).
- Guarda el PDF anotado y un JSON de trazabilidad en una carpeta.

Requisitos del sistema:
- Tesseract instalado (y el idioma spa si usarás español).
  Ubuntu/Debian: sudo apt-get install -y tesseract-ocr tesseract-ocr-spa
  macOS (brew): brew install tesseract
"""

import os
import json
import re
import unicodedata
from typing import Any, List, Dict, Tuple, Optional

import fitz  # PyMuPDF
from rapidfuzz import fuzz
from PIL import Image
import pytesseract


# =============================================================================
# CONFIG (edita aquí)
# =============================================================================

PDF_PATH = "7.1_CONSTITUTIVA RDAT_6619.pdf"
OUT_DIR = "salida"                  # carpeta donde se escriben los resultados
MODE = "highlight"                  # "underline" | "highlight" | "squiggly"
LANG = "spa"                        # idioma Tesseract (p.ej. "spa", "spa+eng")
DPI_OCR = 300                       # rasterización para OCR
MIN_SCORE = 90                      # similitud mínima (0-100)
MAX_NGRAM = 18                      # tamaño máximo de ventana (en palabras)
FIRST_ONLY = False                   # anotar solo la primera coincidencia por valor
NO_OCR = False                      # True = no usar OCR (solo texto nativo)
TESSERACT_CMD = None                # ruta a tesseract si no está en PATH, o None

# Lista de valores a buscar (desde tu LLM o definidos a mano)
VALUES: List[str] = [
    "LIC. ANTONIO MARTIN VILLALPANDO",
    "PATRICIO FRANCISCO PASQUEL QUINTANA",
    {
        "text": """A).- Poder general para pleitos y cobranzas, de acuerdo con el párrafo Primero del artículo dos mil trescientos ochenta y cuatro del Código Civil para el Estado de San Luis Potosí, su correlativo el dos mil quinientos cincuenta y cuatro del Código Civil para el Distrito Federal en materia común y para toda la República en materia federal y sus correlativos de los Estados del resto de la República, con todas las facultades generales y las especiales que requieran poder o cláusula especia.-""",
        "very_permissive": True,
        "marker": "P",             # o "*"
        "marker_side": "left"     # o "left"right
    }
]


# =============================================================================
# Utilidades de normalización y tokens
# =============================================================================

def normalize_text(s: str) -> str:
    """Minúsculas, sin acentos y con solo letras/dígitos; espacios colapsados."""
    if s is None:
        return ""
    s = s.lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", " ", s)  # deja letras / dígitos
    s = " ".join(s.split())
    return s


def significant_tokens(s: str) -> List[str]:
    """Tokens normalizados de tamaño >=3 (evita 'a', 'o', 'la', etc.)."""
    return [t for t in normalize_text(s).split() if len(t) >= 3]


def ordered_token_overlap(cand: List[str], targ: List[str]) -> int:
    """Cuenta cuántos tokens de 'targ' aparecen en 'cand' en el MISMO orden (subsecuencia)."""
    i = j = 0
    count = 0
    while i < len(cand) and j < len(targ):
        if cand[i] == targ[j]:
            count += 1
            j += 1
        i += 1
    return count


def ngram_for_value(value: str, cap: int = 24) -> int:
    toks = significant_tokens(value)
    return max(4, min(cap, len(toks) + 2))

def _best_match(words, phrase, min_score_anchor: int) -> Optional[Dict]:
    local_ngram = ngram_for_value(phrase)
    cands = find_matches(
        words, phrase,
        max_ngram=local_ngram,
        min_score=min_score_anchor,
        allow_overlapping=False
    )
    return cands[0] if cands else None

def find_long_span(words: List[Dict], target: str,
                   anchor_len: int = 6,
                   min_score_anchor: int = 88) -> List[Dict]:
    """
    Para objetivos largos: toma anclas (inicio / medio / fin) y,
    si al menos dos aparecen en orden, subraya desde la primera a la última.
    """
    targ_norm = normalize_text(target)
    toks = significant_tokens(targ_norm)
    if len(toks) <= anchor_len * 2:
        return []  # no es “largo”; que lo maneje el match normal

    # anclas
    a1 = " ".join(toks[:anchor_len])
    mid = len(toks) // 2
    aM = " ".join(toks[max(0, mid - anchor_len // 2): mid + (anchor_len // 2 or 1)])
    a2 = " ".join(toks[-anchor_len:])

    b1 = _best_match(words, a1, min_score_anchor)
    bM = _best_match(words, aM, min_score_anchor)
    b2 = _best_match(words, a2, min_score_anchor)

    pair = None
    candidates = []
    if b1 and b2: candidates.append((b1, b2))
    if b1 and bM: candidates.append((b1, bM))
    if bM and b2: candidates.append((bM, b2))
    if not candidates:
        return []

    # elige el par que cubra más texto pero sin invertir el orden
    ordered = [p for p in candidates if p[0]["start"] <= p[1]["end"]]
    if not ordered:
        return []
    pair = max(ordered, key=lambda pr: pr[1]["end"] - pr[0]["start"])

    s = min(pair[0]["start"], pair[1]["start"])
    e = max(pair[0]["end"],   pair[1]["end"])

    rects = [words[k]["rect"] for k in range(s, e + 1)]
    text  = " ".join(words[k]["text"] for k in range(s, e + 1))
    score = min(pair[0]["score"], pair[1]["score"])  # conservador

    return [{
        "start": s, "end": e, "score": score, "text": text, "rects": rects
    }]

def find_matches_for_value(words: List[Dict], target: str,
                           max_ngram: int, min_score: int,
                           very_permissive: bool = False) -> List[Dict]:
    """
    Orden de intentos:
    1) Estricto por palabras (rápido y preciso).
    2) Si el objetivo es largo: anclas (inicio/medio/fin).
    3) Fallback por caracteres (tolerante).
    4) (Solo si very_permissive=True) Barrido por ventanas de tokens (muy tolerante).
    """
    # 1) estricto
    strict = find_matches(words, target, max_ngram=max_ngram,
                          min_score=min_score, allow_overlapping=False)
    if strict:
        return strict

    # 2) anclas para textos largos
    if len(significant_tokens(target)) > 14:
        long_m = find_long_span(words, target, anchor_len=6,
                                min_score_anchor=max(86, min_score - 2))
        if long_m:
            return long_m

    # 3) fallback por caracteres
    target_n = normalize_text(target)
    stream, spans, token_starts = build_char_stream(words)
    best = best_char_window(stream, target_n, token_starts, min_score=max(78, min_score - 6))
    if best:
        mm = charspan_to_match(words, spans, best["char_start"], best["char_end"])
        if mm:
            mm["score"] = best["score"]
            return [mm]

    # 4) MUY permisivo (solo si se pide)
    if very_permissive:
        vp = very_permissive_sweep(words, target, base_min_score=max(74, min_score - 10))
        if vp:
            return vp

    return []

    
    
from rapidfuzz import fuzz

def build_char_stream(words: List[Dict]) -> tuple[str, list[tuple[int,int,int]], list[int]]:
    """
    Construye un string normalizado de toda la página y un mapeo de char→token.
    Devuelve: (stream, spans, token_starts)
      - stream: "palabra1 palabra2 ..."
      - spans:  lista de (char_start, char_end, token_idx) para cada token incluido
      - token_starts: lista con todos los char_start (para iterar por límites de token)
    """
    pieces = []
    spans = []
    token_starts = []
    pos = 0
    for idx, w in enumerate(words):
        t = normalize_text(w["text"])
        if not t:
            continue
        if pieces:
            pieces.append(" ")
            pos += 1
        start = pos
        pieces.append(t)
        pos += len(t)
        spans.append((start, pos, idx))
        token_starts.append(start)
    stream = "".join(pieces)
    return stream, spans, token_starts


def best_char_window(stream: str, target_n: str, token_starts: list[int],
                     min_score: int = 82) -> Optional[Dict]:
    """
    Busca la mejor subcadena de 'stream' parecida a 'target_n' usando similitud por caracteres.
    - Explora ventanas con longitudes entre 60% y 160% del target, empezando en límites de tokens.
    - Devuelve {'char_start','char_end','score'} o None.
    """
    L = len(target_n)
    if L < 8 or len(stream) < 8:
        return None

    minL = max(4, int(0.6 * L))
    maxL = min(len(stream), int(1.6 * L))

    best = None
    # Recorremos solo inicios en límites de token para no explotar combinatoria
    for s in token_starts:
        if s >= len(stream):
            break
        for winL in (minL, int(0.8*L), L, int(1.2*L), maxL):
            e = min(len(stream), s + winL)
            if e - s < 4:
                continue
            cand = stream[s:e]
            # Para ventanas, partial_ratio suele ir mejor
            score = max(fuzz.partial_ratio(cand, target_n), fuzz.ratio(cand, target_n))
            if score >= min_score and (best is None or score > best["score"]):
                best = {"char_start": s, "char_end": e, "score": int(score)}
    return best


def charspan_to_match(words: List[Dict], spans: list[tuple[int,int,int]],
                      cs: int, ce: int) -> Optional[Dict]:
    """
    Convierte un rango de caracteres (cs, ce) a un match con rects y texto
    utilizando el mapeo spans (char_start, char_end, token_idx).
    """
    sel_tokens = []
    for (s, e, idx) in spans:
        if e <= cs:
            continue
        if s >= ce:
            break
        sel_tokens.append(idx)

    if not sel_tokens:
        return None

    s_idx = min(sel_tokens)
    e_idx = max(sel_tokens)
    rects = [words[k]["rect"] for k in range(s_idx, e_idx + 1)]
    text = " ".join(words[k]["text"] for k in range(s_idx, e_idx + 1))
    # score se coloca a nivel de quien llamó
    return {"start": s_idx, "end": e_idx, "text": text, "rects": rects}


def coerce_values(values):
    """
    Acepta strings o dicts {'text': str, 'very_permissive': bool}
    Devuelve lista de dicts uniformes.
    """
    norm = []
    for v in values:
        if isinstance(v, str):
            norm.append({"text": v, "very_permissive": False})
        elif isinstance(v, dict) and "text" in v:
            norm.append({
                "text": v["text"],
                "very_permissive": bool(v.get("very_permissive", False))
            })
        else:
            # ignora entradas inválidas
            continue
    return norm


def very_permissive_sweep(words: List[Dict], target: str,
                          base_min_score: int = 75,
                          max_window_cap: int = 120) -> List[Dict]:
    """
    Búsqueda MUY permisiva a nivel tokens:
    - Construye lista de tokens normalizados de la página.
    - Barremos ventanas contiguas con tamaños en [0.35..2.1] * len(target_tokens),
      acotado por max_window_cap para evitar explosión.
    - Usamos max(partial_ratio, ratio) y nos quedamos con el mejor > base_min_score.
    """
    targ_n = normalize_text(target)
    targ_tokens = significant_tokens(targ_n)
    if not targ_tokens:
        return []

    # tokens normalizados de la página
    norm_tokens = []
    for w in words:
        t = normalize_text(w["text"])
        if t:
            norm_tokens.append(t)

    n = len(norm_tokens)
    if n == 0:
        return []

    m = len(targ_tokens)
    min_w = max(4, int(0.35 * m))
    max_w = min(n, max_window_cap, int(2.1 * m) + 4)

    best = None
    # barrido con tamaños discretizados para reducir costo
    size_candidates = sorted(set([
        min_w, int(0.5 * m), int(0.8 * m), m, int(1.2 * m),
        int(1.5 * m), max_w
    ]))
    size_candidates = [s for s in size_candidates if 4 <= s <= max_w]

    for i in range(0, n):
        for wsize in size_candidates:
            j = i + wsize
            if j > n:
                break
            cand_n = " ".join(norm_tokens[i:j])
            # partial ayuda con inserciones/borrados
            sc = max(fuzz.partial_ratio(cand_n, targ_n), fuzz.ratio(cand_n, targ_n))
            if sc >= base_min_score and (best is None or sc > best["score"]):
                best = {"i": i, "j": j, "score": int(sc)}
        # micro-corte para no explotar en páginas enormes
        # (si quieres, cambia a i += 1; esto es por claridad)
    if not best:
        return []

    # mapeo de indices de token -> rects/text usando 'words'
    # necesitamos el índice real de 'words' que corresponde a cada token normalizado
    # Volvemos a recorrer 'words' y vamos sumando tokens válidos
    real_indices = []
    for idx, w in enumerate(words):
        t = normalize_text(w["text"])
        if t:
            real_indices.append(idx)

    s_idx = real_indices[best["i"]]
    e_idx = real_indices[best["j"] - 1]

    rects = [words[k]["rect"] for k in range(s_idx, e_idx + 1)]
    text  = " ".join(words[k]["text"] for k in range(s_idx, e_idx + 1))
    return [{
        "start": s_idx,
        "end": e_idx,
        "score": best["score"],
        "text": text,
        "rects": rects
    }]



# =============================================================================
# Extracción de palabras + cajas
# =============================================================================

def words_with_boxes_native(page: fitz.Page) -> List[Dict]:
    """Palabras con rects desde texto nativo."""
    words = page.get_text("words")
    out = []
    for x0, y0, x1, y1, w, *_ in words:
        if not w or not str(w).strip():
            continue
        out.append({"text": str(w), "rect": fitz.Rect(x0, y0, x1, y1)})
    return out


def page_image_for_ocr(page: fitz.Page, dpi: int = 300) -> Image.Image:
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img


def words_with_boxes_ocr(page: fitz.Page, lang: str = "spa", dpi: int = 300) -> Tuple[List[Dict], float]:
    """OCR por palabra usando Tesseract, mapeando px -> puntos PDF (72 dpi)."""
    img = page_image_for_ocr(page, dpi=dpi)
    data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)

    words = []
    for i in range(len(data["text"])):
        t = data["text"][i]
        if not t or not str(t).strip():
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        x0 = x * 72.0 / dpi
        y0 = y * 72.0 / dpi
        x1 = (x + w) * 72.0 / dpi
        y1 = (y + h) * 72.0 / dpi
        words.append({"text": str(t), "rect": fitz.Rect(x0, y0, x1, y1)})

    confs = [int(c) for c in data.get("conf", []) if str(c).isdigit()]
    avg_conf = (sum(confs) / len(confs)) if confs else 0.0
    return words, avg_conf


# =============================================================================
# Búsqueda estricta (evita falsos positivos)
# =============================================================================

def find_matches(words: List[Dict], target: str, max_ngram: int = 12,
                 min_score: int = 90, allow_overlapping: bool = False) -> List[Dict]:
    """
    Estricto: exige longitud mínima (>=60% del objetivo) y que >=80% de los tokens
    significativos del objetivo aparezcan en orden en el candidato.
    Usa fuzz.ratio (no partial / token_set).
    """
    target_n = normalize_text(target)
    if not target_n:
        return []

    targ_sig = significant_tokens(target_n)
    if not targ_sig:
        return []

    need_in_order = max(1, int(round(0.8 * len(targ_sig))))

    n = len(words)
    norm_words = [normalize_text(w["text"]) for w in words]
    candidates: List[Dict] = []

    for i in range(n):
        merged_norm_parts = []
        merged_orig_parts = []
        rects: List[fitz.Rect] = []

        for j in range(i, min(i + max_ngram, n)):
            merged_norm_parts.append(norm_words[j])
            merged_orig_parts.append(words[j]["text"])
            rects.append(words[j]["rect"])

            cand_n = " ".join(merged_norm_parts)
            if not cand_n:
                continue

            # 1) longitud mínima
            if len(cand_n) < 0.6 * len(target_n):
                continue

            # 2) tokens significativos en orden
            cand_sig = [t for t in " ".join(merged_norm_parts).split() if len(t) >= 3]
            if ordered_token_overlap(cand_sig, targ_sig) < need_in_order:
                continue

            # 3) similitud estricta
            score = fuzz.ratio(cand_n, target_n)
            if score >= min_score:
                candidates.append({
                    "start": i,
                    "end": j,
                    "score": int(score),
                    "text": " ".join(merged_orig_parts),
                    "rects": rects.copy()
                })

    if not candidates:
        return []

    # ordena por score alto y ventana corta
    candidates.sort(key=lambda c: (-c["score"], (c["end"] - c["start"])))

    if allow_overlapping:
        return candidates

    # greedy sin solapes
    selected: List[Dict] = []
    used = [False] * n
    for c in candidates:
        if any(used[k] for k in range(c["start"], c["end"] + 1)):
            continue
        for k in range(c["start"], c["end"] + 1):
            used[k] = True
        selected.append(c)

    return selected


# =============================================================================
# Anotación (segura)
# =============================================================================

def _is_valid_rect(r: fitz.Rect) -> bool:
    try:
        if r is None:
            return False
        if (r.width <= 0) or (r.height <= 0):
            return False
        vals = [r.x0, r.y0, r.x1, r.y1]
        if any(v is None for v in vals):
            return False
        if any((v != v) for v in vals):  # NaN
            return False
        if any(abs(v) == float('inf') for v in vals):
            return False
        return True
    except Exception:
        return False


def annotate(page: fitz.Page, rects: List[fitz.Rect], mode: str = "underline"):
    """Crea una anotación por rectángulo (palabra/fragmento), validando cada rect."""
    if not rects:
        return
    mode = (mode or "underline").lower().strip()

    for r in rects:
        if not isinstance(r, fitz.Rect):
            try:
                r = fitz.Rect(r)
            except Exception:
                continue
        if not _is_valid_rect(r):
            continue
        try:
            if mode == "highlight":
                page.add_highlight_annot(r)
            elif mode == "squiggly":
                page.add_squiggly_annot(r)
            else:
                page.add_underline_annot(r)
        except Exception:
            # si PyMuPDF se queja por algún rect, seguimos con los demás
            continue


# =============================================================================
# Proceso principal
# =============================================================================

# def process_pdf(pdf_path: str,
#                 values: List[str],
#                 out_dir: str,
#                 mode: str = "underline",
#                 lang: str = "spa",
#                 dpi_ocr: int = 300,
#                 min_score: int = 90,
#                 max_ngram: int = 12,
#                 first_only: bool = False,
#                 no_ocr: bool = False,
#                 tesseract_cmd: Optional[str] = None) -> Dict:
#     """Recorre el PDF y anota coincidencias para cada valor."""
#     if tesseract_cmd:
#         pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

#     if not os.path.isfile(pdf_path):
#         raise FileNotFoundError(f"No se encontró el PDF: {pdf_path}")

#     os.makedirs(out_dir, exist_ok=True)

#     base = os.path.splitext(os.path.basename(pdf_path))[0]
#     out_pdf = os.path.join(out_dir, f"{base}_annot.pdf")
#     out_json = os.path.join(out_dir, f"{base}_matches.json")

#     doc = fitz.open(pdf_path)
#     results: Dict[str, List[Dict]] = {v: [] for v in values}

#     try:
#         value_done = {v: False for v in values}

#         for page_num in range(len(doc)):
#             page = doc[page_num]

#             native_words = words_with_boxes_native(page)
#             native_available = len(native_words) > 0

#             ocr_words, _avg_conf = ([], 0.0)

#             for v in values:
#                 if first_only and value_done[v]:
#                     continue

#                 matches: List[Dict] = []
#                 if native_available:
#                     matches = find_matches(
#                         native_words, v,
#                         max_ngram=max_ngram,
#                         min_score=min_score,
#                         # allow_overlapping=False
#                     )

#                 if not matches and not no_ocr:
#                     if not ocr_words:
#                         ocr_words, _avg_conf = words_with_boxes_ocr(page, lang=lang, dpi=dpi_ocr)
#                     if ocr_words:
#                         matches = find_matches(
#                             ocr_words, v,
#                             max_ngram=max_ngram,
#                             min_score=min_score,
#                             # allow_overlapping=False
#                         )

#                 for m in matches:
#                     annotate(page, m["rects"], mode=mode)
#                     results[v].append({
#                         "page": page_num,
#                         "score": m["score"],
#                         "matched_text": m["text"],
#                         "rects": [list(r) for r in m["rects"]]
#                     })
#                     if first_only:
#                         value_done[v] = True
#                         break

#         doc.save(out_pdf, deflate=True)
#         with open(out_json, "w", encoding="utf-8") as f:
#             json.dump({
#                 "pdf": os.path.abspath(pdf_path),
#                 "output_pdf": os.path.abspath(out_pdf),
#                 "values": values,
#                 "results": results
#             }, f, ensure_ascii=False, indent=2)

#         print("✅ Listo")
#         print("PDF anotado:", os.path.abspath(out_pdf))
#         print("JSON:", os.path.abspath(out_json))
#         for v, lst in results.items():
#             print(f" - '{v}': {len(lst)} match(es)")
#         return {"output_pdf": out_pdf, "output_json": out_json, "results": results}

#     finally:
#         doc.close()

# def process_pdf(pdf_path: str,
#                 values: List[str],
#                 out_dir: str,
#                 mode: str = "underline",
#                 lang: str = "spa",
#                 dpi_ocr: int = 300,
#                 min_score: int = 90,
#                 max_ngram: int = 12,
#                 first_only: bool = False,
#                 no_ocr: bool = False,
#                 tesseract_cmd: Optional[str] = None) -> Dict:
#     """
#     Recorre el PDF y anota coincidencias para cada valor.
#     'values' puede ser:
#       - List[str]  -> búsqueda normal (estricta/anclas/chars)
#       - List[dict] -> cada dict: {'text': str, 'very_permissive': bool}
#     """

#     # --- helper local para normalizar la lista de valores ---
#     def _coerce_values_list(vals) -> List[Dict[str, Any]]:
#         norm = []
#         for v in vals:
#             if isinstance(v, str):
#                 norm.append({"text": v, "very_permissive": False})
#             elif isinstance(v, dict) and "text" in v:
#                 norm.append({
#                     "text": v["text"],
#                     "very_permissive": bool(v.get("very_permissive", False))
#                 })
#             # entradas inválidas se ignoran silenciosamente
#         return norm

#     if tesseract_cmd:
#         pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

#     if not os.path.isfile(pdf_path):
#         raise FileNotFoundError(f"No se encontró el PDF: {pdf_path}")

#     os.makedirs(out_dir, exist_ok=True)

#     base = os.path.splitext(os.path.basename(pdf_path))[0]
#     out_pdf = os.path.join(out_dir, f"{base}_annot.pdf")
#     out_json = os.path.join(out_dir, f"{base}_matches.json")

#     # Normaliza 'values' a lista de dicts {'text', 'very_permissive'}
#     values_norm = _coerce_values_list(values)

#     # Diccionarios de resultados/estado indexados por el texto objetivo
#     results: Dict[str, List[Dict]] = {v["text"]: [] for v in values_norm}
#     value_done: Dict[str, bool] = {v["text"]: False for v in values_norm}

#     doc = fitz.open(pdf_path)

#     try:
#         for page_num in range(len(doc)):
#             page = doc[page_num]

#             # Palabras nativas (si el PDF no es escaneado)
#             native_words = words_with_boxes_native(page)
#             native_available = len(native_words) > 0

#             # OCR diferido (solo si hace falta)
#             ocr_words, _avg_conf = ([], 0.0)

#             # Recorre cada valor a buscar
#             for vobj in values_norm:
#                 v_text = vobj["text"]
#                 v_flag = vobj.get("very_permissive", False)

#                 if first_only and value_done[v_text]:
#                     continue

#                 matches: List[Dict] = []

#                 # 1) Intento con texto nativo
#                 if native_available:
#                     matches = find_matches_for_value(
#                         native_words,
#                         v_text,
#                         max_ngram=max_ngram,
#                         min_score=min_score,
#                         very_permissive=v_flag
#                     )

#                 # 2) Fallback con OCR si no hubo match nativo y el OCR está permitido
#                 if not matches and not no_ocr:
#                     if not ocr_words:
#                         ocr_words, _avg_conf = words_with_boxes_ocr(page, lang=lang, dpi=dpi_ocr)
#                     if ocr_words:
#                         matches = find_matches_for_value(
#                             ocr_words,
#                             v_text,
#                             max_ngram=max_ngram,
#                             min_score=min_score,
#                             very_permissive=v_flag
#                         )

#                 # 3) Anotar y registrar resultados
#                 for m in matches:
#                     annotate(page, m["rects"], mode=mode)
#                     results[v_text].append({
#                         "page": page_num,
#                         "score": m.get("score", 0),
#                         "matched_text": m.get("text", ""),
#                         "rects": [list(r) for r in m.get("rects", [])]
#                     })
#                     if first_only:
#                         value_done[v_text] = True
#                         break  # solo el primer match para este valor en todo el doc

#         # Guardar PDF y JSON de trazabilidad
#         doc.save(out_pdf, deflate=True)
#         with open(out_json, "w", encoding="utf-8") as f:
#             json.dump({
#                 "pdf": os.path.abspath(pdf_path),
#                 "output_pdf": os.path.abspath(out_pdf),
#                 "values": [v["text"] for v in values_norm],
#                 "results": results
#             }, f, ensure_ascii=False, indent=2)

#         print("✅ Listo")
#         print("PDF anotado:", os.path.abspath(out_pdf))
#         print("JSON:", os.path.abspath(out_json))
#         for vtext, lst in results.items():
#             print(f" - '{vtext}': {len(lst)} match(es)")
#         return {"output_pdf": out_pdf, "output_json": out_json, "results": results}

#     finally:
#         doc.close()


def process_pdf(pdf_path: str,
                values: List[str],
                out_dir: str,
                mode: str = "highlight",
                lang: str = "spa",
                dpi_ocr: int = 300,
                min_score: int = 90,
                max_ngram: int = 12,
                first_only: bool = False,
                no_ocr: bool = False,
                tesseract_cmd: Optional[str] = None,
                # Opciones visuales del marcador / highlight:
                # highlight_rgb: Tuple[float, float, float] = (1.0, 0.92, 0.23),  # amarillo típico
                highlight_rgb=(1.0, 0.92, 0.23),  # amarillo “marcatexto”

                # marker_style: str = "filled",    # "filled" (fondo color marcatexto, texto blanco) o "text" (sólo letra coloreada)
                # marker_box_pt: float = 14.0,     # tamaño del recuadro del marcador (pts)
                marker_style="filled",              # << letra P/* amarilla (sin fondo)
                marker_box_pt=48,
                marker_margin_pt: float = 8.0,   # margen entre el párrafo y el marcador (pts)
                marker_text_color: Tuple[float, float, float] = (0, 0, 0)  # para style="filled"
                ) -> Dict:
    """
    Recorre el PDF y anota coincidencias para cada valor, agregando un marcador lateral
    (P o *) a la izquierda o derecha del párrafo cuando así se indique por valor.

    'values' puede ser:
      - List[str]
      - List[dict]: cada dict puede incluir:
         {
           "text": "cadena a buscar",
           "very_permissive": True/False,
           "marker": "P"  (o "*"),
           "marker_side": "right"  (o "left")
         }
    """

    # ---------------- helpers locales (solo para esta función) ----------------

    from typing import Any

    def _coerce_values_list(vals) -> List[Dict[str, Any]]:
        """
        Normaliza 'values' a una lista de dicts:
        {'text': str, 'very_permissive': bool, 'marker': Optional[str], 'marker_side': Optional[str]}
        """
        norm = []
        for v in vals:
            if isinstance(v, str):
                norm.append({"text": v, "very_permissive": False, "marker": None, "marker_side": None})
            elif isinstance(v, dict) and "text" in v:
                norm.append({
                    "text": v["text"],
                    "very_permissive": bool(v.get("very_permissive", False)),
                    "marker": v.get("marker"),  # "P" o "*"
                    "marker_side": (v.get("marker_side") or "").lower() if v.get("marker_side") else None
                })
            # entradas inválidas se ignoran
        return norm

    def _union_rect(rects: List[fitz.Rect]) -> fitz.Rect:
        """Rectángulo envolvente de una lista de rects."""
        x0 = min(r.x0 for r in rects)
        y0 = min(r.y0 for r in rects)
        x1 = max(r.x1 for r in rects)
        y1 = max(r.y1 for r in rects)
        return fitz.Rect(x0, y0, x1, y1)

    def _add_side_marker(page: fitz.Page,
                         anchor: fitz.Rect,
                         text: str = "P",
                         side: str = "right",
                         color_rgb: Tuple[float, float, float] = (1.0, 0.92, 0.23),
                         style: str = "filled",
                         box_pt: float = 14.0,
                         margin_pt: float = 6.0,
                         text_rgb: Tuple[float, float, float] = (1, 1, 1)) -> Optional[fitz.Annot]:
        """
        Dibuja un marcador (FreeText annot) junto al rectángulo 'anchor'.
        - side: "left" / "right"
        - style: "filled" -> fondo color marcatexto + texto blanco
                 "text"   -> sin fondo, texto del color marcatexto
        """
        # Caja del marcador según el centro vertical del párrafo
        y_mid = (anchor.y0 + anchor.y1) / 2.0
        h = box_pt
        w = box_pt
        y0 = y_mid - h / 2.0
        y1 = y_mid + h / 2.0

        if side == "left":
            x1 = anchor.x0 - margin_pt
            x0 = x1 - w
            # si se sale por la izquierda, intentamos derecha
            if x0 < 0:
                x0 = anchor.x1 + margin_pt
                x1 = x0 + w
        else:  # right o cualquier otro valor
            x0 = anchor.x1 + margin_pt
            x1 = x0 + w
            # si se sale por la derecha, intentamos izquierda
            if x1 > page.rect.x1:
                x1 = anchor.x0 - margin_pt
                x0 = x1 - w

        # clamp vertical a la página
        if y0 < 0:
            y1 = y1 - y0
            y0 = 0
        if y1 > page.rect.y1:
            delta = y1 - page.rect.y1
            y0 -= delta
            y1 -= delta

        rect = fitz.Rect(x0, y0, x1, y1)

        try:
            annot = page.add_freetext_annot(rect, text)
        except Exception:
            return None

        try:
            if style == "filled":
                annot.set_colors(stroke=color_rgb, fill=color_rgb, text=text_rgb)
                annot.set_opacity(0.95)
                annot.set_border(width=0.5)
            else:  # "text"
                annot.set_colors(stroke=color_rgb, fill=None, text=color_rgb)
                annot.set_opacity(1.0)
                annot.set_border(width=0.0)
            # fuente y tamaño: usa casi todo el recuadro
            try:
                annot.set_font("helv", size=box_pt * 0.8)
            except Exception:
                pass
            annot.update()
        except Exception:
            pass

        return annot
    
    # def _add_side_marker(page: fitz.Page,
    #                  anchor: fitz.Rect,
    #                  text: str = "P",
    #                  side: str = "right",
    #                  color_rgb: Tuple[float, float, float] = (1.0, 0.92, 0.23),  # amarillo
    #                  style: str = "text",        # "text" = solo letra amarilla, "filled" = etiqueta amarilla
    #                  box_pt: float = 44.0,       # tamaño GRANDE por defecto
    #                  margin_pt: float = 8.0,
    #                  text_rgb: Tuple[float, float, float] = (0, 0, 0)) -> Optional[fitz.Annot]:
    #     """
    #     Dibuja un marcador lateral (FreeText).
    #     - style="text": letra del color 'color_rgb' (sin fondo).
    #     - style="filled": etiqueta con fondo 'color_rgb' y letra 'text_rgb' (negro/blanco).
    #     """
    #     y_mid = (anchor.y0 + anchor.y1) / 2.0
    #     h = box_pt
    #     w = box_pt
    #     y0 = y_mid - h / 2.0
    #     y1 = y_mid + h / 2.0

    #     if side == "left":
    #         x1 = anchor.x0 - margin_pt
    #         x0 = x1 - w
    #         if x0 < 0:
    #             x0 = anchor.x1 + margin_pt
    #             x1 = x0 + w
    #     else:  # right (default)
    #         x0 = anchor.x1 + margin_pt
    #         x1 = x0 + w
    #         if x1 > page.rect.x1:
    #             x1 = anchor.x0 - margin_pt
    #             x0 = x1 - w

    #     # clamp vertical dentro de la página
    #     if y0 < 0:
    #         y1 = y1 - y0
    #         y0 = 0
    #     if y1 > page.rect.y1:
    #         delta = y1 - page.rect.y1
    #         y0 -= delta
    #         y1 -= delta

    #     rect = fitz.Rect(x0, y0, x1, y1)

    #     try:
    #         annot = page.add_freetext_annot(rect, text)
    #     except Exception:
    #         return None

    #     try:
    #         annot.set_border(width=0.0)
    #         annot.set_flags(fitz.ANNOT_PRINT)  # asegúralo para impresión / flatten

    #         if style == "filled":
    #             # etiqueta amarilla sólida con texto en negro (o blanco si prefieres)
    #             annot.set_colors(stroke=color_rgb, fill=color_rgb, text=text_rgb)
    #             annot.set_opacity(0.95)
    #             # fuerza colores en la apariencia:
    #             annot.update(
    #                 fontsize=box_pt * 0.82,
    #                 text_color=text_rgb,
    #                 fill_color=color_rgb,
    #                 color=color_rgb
    #             )
    #         else:
    #             # solo la letra amarilla (sin fondo)
    #             annot.set_colors(stroke=None, fill=None, text=color_rgb)
    #             annot.set_opacity(1.0)
    #             annot.update(
    #                 fontsize=box_pt * 0.88,
    #                 text_color=color_rgb,   # <- clave para que no salga negra
    #                 fill_color=None,
    #                 color=None
    #             )
    #         # fuente (si falla 'helv', PyMuPDF mantiene la que tenga):
    #         try:
    #             annot.set_font("helv", size=box_pt * 0.88)
    #         except Exception:
    #             pass

    #         annot.update()  # reconstruye appearance
    #     except Exception:
    #         pass

    #     return annot
    
    # def _add_side_marker(page: fitz.Page,
    #                  anchor: fitz.Rect,
    #                  text: str = "P",
    #                  side: str = "right",
    #                  color_rgb: Tuple[float, float, float] = (1.0, 0.92, 0.23),  # amarillo
    #                  style: str = "filled",        # "filled" = etiqueta amarilla; "text" = solo letra
    #                  box_pt: float = 44.0,
    #                  margin_pt: float = 8.0,
    #                  text_rgb: Tuple[float, float, float] = (0, 0, 0)) -> None:
    #     """
    #     Pinta un marcador como contenido del PDF (no anotación) y ajusta
    #     automáticamente el tamaño de fuente para que siempre quepa en el rectángulo.
    #     """
    #     # --- rectángulo del marcador, centrado vertical al párrafo ---
    #     y_mid = (anchor.y0 + anchor.y1) / 2.0
    #     h = box_pt
    #     w = box_pt
    #     y0 = y_mid - h / 2.0
    #     y1 = y_mid + h / 2.0

    #     if side == "left":
    #         x1 = anchor.x0 - margin_pt
    #         x0 = x1 - w
    #         if x0 < 0:
    #             x0 = anchor.x1 + margin_pt
    #             x1 = x0 + w
    #     else:  # right por defecto
    #         x0 = anchor.x1 + margin_pt
    #         x1 = x0 + w
    #         if x1 > page.rect.x1:
    #             x1 = anchor.x0 - margin_pt
    #             x0 = x1 - w

    #     # clamp vertical
    #     if y0 < 0:
    #         y1 = y1 - y0
    #         y0 = 0
    #     if y1 > page.rect.y1:
    #         delta = y1 - page.rect.y1
    #         y0 -= delta
    #         y1 -= delta

    #     rect = fitz.Rect(x0, y0, x1, y1)

    #     # --- fondo (si style filled) ---
    #     if style == "filled":
    #         r = max(2.0, box_pt * 0.25)  # esquinas redondeadas
    #         sh = page.new_shape()
    #         try:
    #             sh.draw_round_rect(rect, r)
    #         except Exception:
    #             sh.draw_rect(rect)
    #         sh.finish(color=None, fill=color_rgb, width=0)
    #         sh.commit()

    #     # --- medir y ajustar tamaño de letra (con 'helv', built-in seguro) ---
    #     fontname = "helv"  # ¡no uses helvB!
    #     fs = box_pt * (0.90 if style == "text" else 0.85)
    #     min_fs = max(7.5, box_pt * 0.33)
    #     max_iters = 20

    #     def cap_h(size: float) -> float:
    #         return 0.70 * size  # aprox. altura de mayúscula

    #     def text_w(size: float) -> float:
    #         try:
    #             return fitz.get_text_length(text, fontname=fontname, fontsize=size)
    #         except Exception:
    #             return len(text) * size * 0.55

    #     while max_iters > 0:
    #         if text_w(fs) <= rect.width * 0.9 and cap_h(fs) <= rect.height * 0.9:
    #             break
    #         fs *= 0.90
    #         max_iters -= 1
    #         if fs < min_fs:
    #             fs = min_fs
    #             break

    #     # --- pintar texto ---
    #     page.insert_textbox(
    #         rect, text,
    #         fontsize=fs,
    #         fontname=fontname,
    #         color=((0, 0, 0) if style == "filled" else (0, 0, 0)),  # filled: letra en text_rgb; text: letra amarilla
    #         align=fitz.TEXT_ALIGN_CENTER
    #     )

            
        # No devolvemos nada: queda horneado en el contenido del PDF


    # -------------------------------------------------------------------------

    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"No se encontró el PDF: {pdf_path}")

    os.makedirs(out_dir, exist_ok=True)

    base = os.path.splitext(os.path.basename(pdf_path))[0]
    out_pdf = os.path.join(out_dir, f"{base}_annot.pdf")
    out_json = os.path.join(out_dir, f"{base}_matches.json")

    # Normaliza 'values' a lista de dicts con metadatos
    values_norm = _coerce_values_list(values)

    # Diccionarios de resultados/estado indexados por el texto objetivo
    results: Dict[str, List[Dict]] = {v["text"]: [] for v in values_norm}
    value_done: Dict[str, bool] = {v["text"]: False for v in values_norm}

    doc = fitz.open(pdf_path)

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]

            # Palabras nativas (si el PDF no es escaneado)
            native_words = words_with_boxes_native(page)
            native_available = len(native_words) > 0

            # OCR diferido (solo si hace falta)
            ocr_words, _avg_conf = ([], 0.0)

            for vobj in values_norm:
                v_text = vobj["text"]
                v_flag = bool(vobj.get("very_permissive", False))
                v_marker = vobj.get("marker")            # "P" / "*" / None
                v_side = (vobj.get("marker_side") or "").lower() if vobj.get("marker_side") else None
                if v_side not in ("left", "right"):
                    v_side = "right"  # por defecto, derecha

                if first_only and value_done[v_text]:
                    continue

                matches: List[Dict] = []

                # 1) Intento con texto nativo
                if native_available:
                    matches = find_matches_for_value(
                        native_words,
                        v_text,
                        max_ngram=max_ngram,
                        min_score=min_score,
                        very_permissive=v_flag
                    )

                # 2) Fallback con OCR si no hubo match nativo y OCR permitido
                if not matches and not no_ocr:
                    if not ocr_words:
                        ocr_words, _avg_conf = words_with_boxes_ocr(page, lang=lang, dpi=dpi_ocr)
                    if ocr_words:
                        matches = find_matches_for_value(
                            ocr_words,
                            v_text,
                            max_ngram=max_ngram,
                            min_score=min_score,
                            very_permissive=v_flag
                        )

                # 3) Anotar y registrar resultados
                for m in matches:
                    # (a) subrayado / highlight palabra por palabra (tu función annotate)
                    annotate(page, m["rects"], mode=mode)  # si quisieras colorear, añade color/opacidad en tu annotate

                    # (b) agrega marcador lateral si está pedido
                    if v_marker:
                        try:
                            anchor = _union_rect([fitz.Rect(r) for r in m["rects"]]) if m.get("rects") else None
                        except Exception:
                            anchor = None

                        if anchor is not None:
                            _add_side_marker(
                                page,
                                anchor=anchor,
                                text=str(v_marker),
                                side=v_side,
                                color_rgb=highlight_rgb,
                                style=marker_style,
                                box_pt=marker_box_pt,
                                margin_pt=marker_margin_pt,
                                text_rgb=marker_text_color
                            )

                    # (c) guarda trazabilidad
                    results[v_text].append({
                        "page": page_num,
                        "score": m.get("score", 0),
                        "matched_text": m.get("text", ""),
                        "rects": [list(r) for r in m.get("rects", [])],
                        "marker": v_marker,
                        "marker_side": v_side
                    })

                    if first_only:
                        value_done[v_text] = True
                        break  # solo el primer match para este valor en todo el doc

        # Guardar PDF y JSON de trazabilidad
        doc.save(out_pdf, deflate=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump({
                "pdf": os.path.abspath(pdf_path),
                "output_pdf": os.path.abspath(out_pdf),
                "values": [v["text"] for v in values_norm],
                "results": results
            }, f, ensure_ascii=False, indent=2)

        print("✅ Listo")
        print("PDF anotado:", os.path.abspath(out_pdf))
        print("JSON:", os.path.abspath(out_json))
        for vtext, lst in results.items():
            print(f" - '{vtext}': {len(lst)} match(es)")
        return {"output_pdf": out_pdf, "output_json": out_json, "results": results}

    finally:
        doc.close()



# =============================================================================
# Entrypoint (sin CLI)
# =============================================================================

if __name__ == "__main__":
    process_pdf(
        pdf_path=PDF_PATH,
        values=VALUES,
        out_dir=OUT_DIR,
        mode=MODE,
        lang=LANG,
        dpi_ocr=DPI_OCR,
        min_score=MIN_SCORE,
        max_ngram=MAX_NGRAM,
        first_only=FIRST_ONLY,
        no_ocr=NO_OCR,
        tesseract_cmd=TESSERACT_CMD
    )
