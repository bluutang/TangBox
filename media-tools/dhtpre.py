#!/usr/bin/env python3
"""Resolve a VidHide (dhtpre.com) embed to its stream endpoints.

The page hides the links in a packed-JS eval(function(p,a,c,k,e,d)) block, so we
unbase the symbol table and substitute before reading the `links` object.
"""
import json, re, sys, urllib.request

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                   " (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
    "Referer": "https://dhtpre.com/",
    "Origin": "https://dhtpre.com",
}
ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

def unpack(embed_url, timeout=20):
    req = urllib.request.Request(embed_url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        html = r.read().decode("utf-8", "ignore")
    packed = re.findall(r"eval\(function\(p,a,c,k,e,d\).+?\.split\('\|'\)\)\)", html, re.DOTALL)
    if not packed:
        return None, "no packed block", len(html)
    m = re.search(r"\}\('(.*)',\s*(\d+),\s*(\d+),\s*'(.*)'\.split\('\|'\)", packed[0], re.DOTALL)
    if not m:
        return None, "packed block did not parse", len(html)
    payload, radix, _count, symtab = m.groups()
    radix = int(radix); syms = symtab.split("|")
    def unbase(v, r):
        n = 0
        for ch in v: n = n * r + ALPHABET.index(ch)
        return n
    def sub(mo):
        w = mo.group(0)
        try:
            i = unbase(w, radix)
            return syms[i] if i < len(syms) and syms[i] else w
        except Exception:
            return w
    unpacked = re.sub(r"\b[0-9a-zA-Z]+\b", sub, payload)
    lm = re.search(r"var\s+links\s*=\s*(\{[^;]+\})", unpacked)
    if not lm:
        return None, "no links object in unpacked js", len(html)
    return json.loads(lm.group(1)), None, len(html)

if __name__ == "__main__":
    links, err, size = unpack(sys.argv[1])
    print(json.dumps({"links": links, "error": err, "html_bytes": size}, indent=1))
