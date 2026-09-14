#!/usr/bin/env python3
"""
check_briefs.py — catch naming drift between a video script, storyboard briefs,
and supplied product art (bonus-cover / brand asset filenames).

Usage:
    check_briefs.py <storyboard.json> [--rows A-B|list] [--names extra.txt] [--strict]

Stdlib only.
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

CURLY = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
}

def denorm_quotes(s: str) -> str:
    for k, v in CURLY.items():
        s = s.replace(k, v)
    return s


def norm(s: str) -> str:
    """lowercase, strip punctuation, collapse spaces"""
    s = denorm_quotes(s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


TOKEN_STOP = {"and", "of", "the", "a", "an", "&", "our", "your"}


def singularize(t: str) -> str:
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 4 and t.endswith("es") and not t.endswith(("ses", "xes")):
        return t[:-1]
    if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def tokenize(s: str) -> list:
    return [singularize(t) for t in norm(s).split(" ") if t and t not in TOKEN_STOP]


def tokset(s: str) -> set:
    return set(tokenize(s))


# words too generic to ever count as a "content word" that triggers a
# Title-Case candidate scan, or to be reported as a meaningful drift cause
NOISE_WORDS = {
    "course", "video", "chart", "step", "steps", "today", "now", "get",
    "learn", "you", "your", "this", "that", "will", "with", "from",
}

# ---------------------------------------------------------------------------
# Canonical name catalogue
# ---------------------------------------------------------------------------

class Canon:
    def __init__(self, name: str, source: str):
        self.name = name
        self.source = source
        self.norm = norm(name)
        self.tokens = tokset(name)

    def __repr__(self):
        return f"<Canon {self.name!r} from {self.source}>"


def find_brand_dir(project: Path, storyboard: dict) -> Path:
    brands_dir = project / "brands"
    brand_key = storyboard.get("brand")
    if brand_key:
        cand = brands_dir / brand_key
        if cand.is_dir():
            return cand
    subs = [d for d in brands_dir.iterdir() if d.is_dir()] if brands_dir.is_dir() else []
    if len(subs) == 1:
        return subs[0]
    if subs:
        # fall back to first, but warn
        print(f"WARNING: multiple brand dirs under {brands_dir}, using {subs[0].name}", file=sys.stderr)
        return subs[0]
    raise SystemExit(f"No brand directory found under {brands_dir}")


def build_canon_list(project: Path, storyboard: dict, names_file: str | None):
    brand_dir = find_brand_dir(project, storyboard)
    refs_dir = brand_dir / "refs"
    entries = []
    seen_norm = {}

    def add(name, source):
        n = norm(name)
        if not n:
            return
        if n in seen_norm:
            seen_norm[n].source += f", {source}"
            return
        c = Canon(name, source)
        seen_norm[n] = c
        entries.append(c)

    if refs_dir.is_dir():
        for p in sorted(refs_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in IMG_EXTS:
                rel = p.relative_to(brand_dir)
                add(p.stem, f"art:{rel}")

    brand_json = brand_dir / "brand.json"
    if brand_json.is_file():
        try:
            bj = json.loads(brand_json.read_text())
        except Exception as e:
            print(f"WARNING: could not parse {brand_json}: {e}", file=sys.stderr)
            bj = {}
        for p in bj.get("products", []) or []:
            add(p, "brand.json:products")

    if names_file:
        for line in Path(names_file).read_text().splitlines():
            line = line.strip()
            if line:
                add(line, f"--names:{names_file}")

    return entries, brand_dir


def word_doc_freq(entries):
    freq = {}
    for e in entries:
        for w in e.tokens:
            freq[w] = freq.get(w, 0) + 1
    return freq


# a word is "generic" (safe to drop / elide) if it recurs across >=2 distinct
# canonical names -- i.e. it's a shared modifier ("futures", "trading",
# "guide", "quick", "start") rather than the word(s) that uniquely identify
# ONE specific product ("order", "types" only ever appear in one cheat sheet).
GENERIC_MIN_DOCFREQ = 2


# ---------------------------------------------------------------------------
# Candidate extraction
# ---------------------------------------------------------------------------

QUOTE_RE = re.compile(r'"([^"]{2,60})"|(?<![\w])\'([^\']{2,60})\'(?![\w])')

# 2-6 consecutive capitalized-word tokens, allowing small connector words and
# an optional leading number ("25 Beginner Mistakes")
TITLECASE_RE = re.compile(
    r"\b(?:\d+\s+)?[A-Z][A-Za-z0-9]*(?:\s+(?:&|and|of|the)?\s*[A-Z][A-Za-z0-9]*){1,5}\b"
)


def extract_candidates(text: str, content_words: set) -> list:
    if not text:
        return []
    text = denorm_quotes(text)
    cands = []

    for m in QUOTE_RE.finditer(text):
        phrase = m.group(1) or m.group(2)
        if phrase:
            cands.append(phrase.strip())

    for m in TITLECASE_RE.finditer(text):
        phrase = m.group(0).strip()
        toks = tokenize(phrase)
        if any(t in content_words for t in toks):
            cands.append(phrase)

    # de-dup, preserve order
    out = []
    seen = set()
    for c in cands:
        n = norm(c)
        if n and n not in seen:
            seen.add(n)
            out.append(c)
    return out


# ---------------------------------------------------------------------------
# Matching / classification
# ---------------------------------------------------------------------------

class Finding:
    def __init__(self, level, candidate, best, ratio, overlap, detail):
        self.level = level  # EXACT / NEAR / DRIFT / UNKNOWN
        self.candidate = candidate
        self.best = best  # Canon or None
        self.ratio = ratio
        self.overlap = overlap
        self.detail = detail


def match_candidate(cand: str, entries: list, freq: dict) -> Finding:
    nc = norm(cand)
    tc = tokset(cand)
    if not tc:
        return None
    if all(t.isdigit() for t in tc):
        return None  # bare number (badge/counter text like '9' or '25'), not a name

    scored = []
    for e in entries:
        if not e.tokens:
            continue
        ratio = difflib.SequenceMatcher(None, nc, e.norm).ratio()
        union = tc | e.tokens
        overlap = len(tc & e.tokens) / len(union) if union else 0.0
        scored.append((0.5 * ratio + 0.5 * overlap, ratio, overlap, e))

    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    _, ratio, overlap, best = scored[0]
    te = best.tokens

    # 1. exact
    if tc == te or ratio >= 0.97:
        return Finding("EXACT", cand, best, ratio, overlap, "matches canonical art/name")

    # 2. pure elision: candidate tokens are a strict subset of canonical tokens.
    #    Safe (NEAR) only if every dropped word is a common/shared modifier
    #    across the canonical set; dropping a word that uniquely identifies
    #    THIS product is real drift.
    if tc < te:
        missing = te - tc
        if all(freq.get(w, 0) >= GENERIC_MIN_DOCFREQ for w in missing):
            return Finding(
                "NEAR", cand, best, ratio, overlap,
                f"script elides shared/common word(s) {sorted(missing)} present in art \"{best.name}\""
            )
        else:
            rare = sorted(w for w in missing if freq.get(w, 0) < GENERIC_MIN_DOCFREQ)
            return Finding(
                "DRIFT", cand, best, ratio, overlap,
                f"drops distinguishing word(s) {rare} — art is \"{best.name}\", not just \"{cand}\""
            )

    # 3. candidate is a SUPERSET of the canonical tokens (script says more than
    #    the art title, e.g. names two products in one breath). Safe (NEAR) if
    #    the extra word(s) belong to another canonical entry (a sibling
    #    product genuinely also being referenced); otherwise the script
    #    invented an extra qualifier that isn't reflected anywhere.
    if te < tc:
        extra = tc - te
        sibling_vocab = set()
        for oe in entries:
            if oe is not best and extra & oe.tokens:
                sibling_vocab |= oe.tokens
        if extra <= sibling_vocab:
            return Finding(
                "NEAR", cand, best, ratio, overlap,
                f"script names multiple products together; {sorted(extra)} belongs to a sibling product, "
                f"core match is \"{best.name}\""
            )
        return Finding(
            "DRIFT", cand, best, ratio, overlap,
            f"script adds word(s) {sorted(extra)} not part of art title \"{best.name}\""
        )

    # 4. genuine word substitution: candidate and canonical share some tokens
    #    but each also has a differing token in the same "slot" (e.g.
    #    trading <-> trade). This is drift even when the strings look similar.
    extra = tc - te
    missing = te - tc
    if extra and missing and overlap >= 0.35:
        return Finding(
            "DRIFT", cand, best, ratio, overlap,
            f"word substitution — script says {sorted(extra)}, art \"{best.name}\" says {sorted(missing)}"
        )

    # 5. fall back to ratio bands; require a meaningful shared-token fraction
    #    (not just >0) so a stray shared word between otherwise-unrelated
    #    short phrases doesn't get reported (main noise-reduction gate).
    if overlap < 0.4:
        return None
    if ratio >= 0.75:
        return Finding("NEAR", cand, best, ratio, overlap, f"close match to \"{best.name}\"")
    if ratio >= 0.45:
        return Finding("DRIFT", cand, best, ratio, overlap, f"loosely resembles \"{best.name}\" but differs")
    return Finding("UNKNOWN", cand, best, ratio, overlap,
                    f"shares a content word with \"{best.name}\" but is a weak match — possibly unbuilt art")


# ---------------------------------------------------------------------------
# Row-level checks
# ---------------------------------------------------------------------------

FIELDS = ["script", "brief", "visual_direction", "notes"]


def gather_row_text(row, field):
    v = row.get(field)
    if v is None:
        return ""
    if isinstance(v, list):
        # notes can be a list of strings (incl. "[generated] ..." entries)
        return "\n".join(str(x) for x in v)
    return str(v)


def slug_tokens(filename: str) -> set:
    stem = Path(filename).stem
    stem = re.sub(r"^\d+[_\-]*", "", stem)  # drop leading row number
    return tokset(stem.replace("_", " ").replace("-", " "))


def check_row(row, entries, freq, content_words):
    n = row.get("n")
    findings_by_field = {}
    for field in FIELDS:
        text = gather_row_text(row, field)
        cands = extract_candidates(text, content_words)
        results = []
        for c in cands:
            f = match_candidate(c, entries, freq)
            if f is not None:
                results.append(f)
        if results:
            findings_by_field[field] = results

    # Suppress a DRIFT/UNKNOWN finding that is just a shorter echo of a fuller
    # mention elsewhere in the SAME row that already resolved EXACT/NEAR
    # (e.g. visual_direction says "Quick Start" after the brief already spelled
    # out "Coinbase Quick Start Guide" / "Hyperliquid Quick Start Guide").
    validated_tokensets = []
    for results in findings_by_field.values():
        for f in results:
            if f.level in ("EXACT", "NEAR"):
                validated_tokensets.append(tokset(f.candidate))
    for field, results in list(findings_by_field.items()):
        kept = []
        for f in results:
            tc = tokset(f.candidate)
            if f.level in ("DRIFT", "UNKNOWN") and any(
                tc and tc < vt for vt in validated_tokensets
            ):
                continue  # redundant partial echo of an already-validated mention
            kept.append(f)
        findings_by_field[field] = kept

    # brief-invented-name check: a NEAR/EXACT product named in the brief
    # whose canonical art is never (even fuzzily) referenced in the script
    invented = []
    brief_hits = findings_by_field.get("brief", [])
    script_hits = findings_by_field.get("script", [])
    script_best_names = {f.best.norm for f in script_hits if f.best}
    for f in brief_hits:
        if (f.level in ("EXACT", "NEAR") and f.best and f.best.source.startswith("art:")
                and f.best.norm not in script_best_names):
            # also allow partial token overlap with *any* script candidate/text
            script_tokens = tokset(gather_row_text(row, "script"))
            if not (f.best.tokens & script_tokens):
                invented.append(f)

    # asset-slug light check
    slug_mismatches = []
    best_script_products = [f for f in script_hits if f.level in ("EXACT", "NEAR", "DRIFT")]
    if best_script_products:
        for asset in row.get("assets", []) or []:
            poster = asset.get("poster") or asset.get("file")
            if not poster:
                continue
            st = slug_tokens(poster)
            if not st:
                continue
            matched_any = False
            for f in best_script_products:
                if f.best and (f.best.tokens & st):
                    matched_any = True
                    break
            if not matched_any and any(t not in NOISE_WORDS for t in st):
                slug_mismatches.append((poster, st, [f.best.name for f in best_script_products if f.best]))

    return findings_by_field, invented, slug_mismatches


# ---------------------------------------------------------------------------
# Row range parsing
# ---------------------------------------------------------------------------

def parse_rows_arg(arg: str, all_ns: list) -> set:
    if not arg:
        return set(all_ns)
    out = set()
    for part in arg.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("--rows", default=None, help="e.g. 30-35 or 1,4,9")
    ap.add_argument("--names", default=None, help="extra newline-separated canonical names")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any DRIFT found")
    args = ap.parse_args()

    sb_path = Path(args.storyboard).expanduser()
    storyboard = json.loads(sb_path.read_text())
    project = sb_path.parent

    entries, brand_dir = build_canon_list(project, storyboard, args.names)
    freq = word_doc_freq(entries)
    content_words = set()
    for e in entries:
        content_words |= e.tokens
    content_words -= NOISE_WORDS

    all_ns = [r.get("n") for r in storyboard["rows"]]
    wanted = parse_rows_arg(args.rows, all_ns)

    print(f"Canonical names loaded: {len(entries)} (brand dir: {brand_dir})")
    print()

    counts = {"EXACT": 0, "NEAR": 0, "DRIFT": 0, "UNKNOWN": 0}
    drift_rows = []

    for row in storyboard["rows"]:
        n = row.get("n")
        if n not in wanted:
            continue
        findings_by_field, invented, slug_mismatches = check_row(row, entries, freq, content_words)

        any_output = any(findings_by_field.values()) or invented or slug_mismatches
        print(f"--- Row {n} " + "-" * 60)
        if not any_output:
            print("  (no candidate product mentions found)")
            print()
            continue

        for field in FIELDS:
            results = findings_by_field.get(field, [])
            for f in results:
                counts[f.level] += 1
                tag = {"EXACT": "OK", "NEAR": "info", "DRIFT": "WARNING", "UNKNOWN": "note"}[f.level]
                artname = f.best.name if f.best else "?"
                print(f"  [{f.level:7s}] ({tag:7s}) {field:17s} \"{f.candidate}\" -> \"{artname}\"  "
                      f"(ratio={f.ratio:.2f} overlap={f.overlap:.2f})")
                print(f"            {f.detail}")
                if f.level == "DRIFT":
                    drift_rows.append(n)

        for f in invented:
            print(f"  [INVENTED] brief names \"{f.candidate}\" (~\"{f.best.name}\") — "
                  f"not mentioned anywhere in the script")

        for poster, st, script_names in slug_mismatches:
            print(f"  [SLUG?   ] asset \"{poster}\" tokens {sorted(st)} don't overlap "
                  f"script-named product(s) {script_names}")

        print()

    print("=" * 70)
    print(f"SUMMARY  EXACT={counts['EXACT']}  NEAR={counts['NEAR']}  "
          f"DRIFT={counts['DRIFT']}  UNKNOWN={counts['UNKNOWN']}")
    if drift_rows:
        print(f"Rows with DRIFT: {sorted(set(drift_rows))}")

    if args.strict and counts["DRIFT"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
