#!/usr/bin/env python3
"""Testes rápidos do gerador de letreiros:  python3 test_lettering.py"""
import io
import math
import pyembroidery as pe
import lettering

CASES = [
    dict(text="Felipe", font="great_vibes", max_w=40),
    dict(text="João\nFrederico", font="parisienne", max_w=85),
    dict(text="07/11/2026", font="dancing", max_w=60),
    dict(text="BIA", font="quicksand", max_h=30),
    dict(text="Ana", font="pacifico", max_h=25),
    dict(text="Luísa Maria", font="playfair", max_w=85, stretch_y=130),
]


def check(case):
    r = lettering.make(**case)
    st = pe.read_pes(io.BytesIO(r["pes"])).stitches
    xs = [s[0] for s in st]; ys = [s[1] for s in st]
    assert min(xs) == 0 and min(ys) == 0, "origem tem que ser o canto (0,0)"
    if case.get("max_w"):
        assert r["width_mm"] <= case["max_w"] + 0.05, "passou da largura máxima"
    if case.get("max_h"):
        assert r["height_mm"] <= case["max_h"] + 0.05, "passou da altura máxima"
    longest = max(math.dist(a[:2], b[:2]) for a, b in zip(st, st[1:])
                  if (a[2] & 0xFF) == pe.STITCH and (b[2] & 0xFF) == pe.STITCH) / 10
    assert longest <= 7.0, "ponto longo demais (%.1f mm)" % longest
    for i, s in enumerate(st):  # corte de linha sempre onde a agulha está
        if (s[2] & 0xFF) == pe.TRIM:
            assert tuple(st[i - 1][:2]) == tuple(s[:2]), "corte fora do lugar"
    print("ok  %-18s %-12s %5.1f x %4.1f mm  %5d pontos  %2d cortes" % (
        case["text"].replace("\n", "/"), case["font"], r["width_mm"], r["height_mm"], r["stitches"], r["trims"]))


if __name__ == "__main__":
    for c in CASES:
        check(c)
    print("tudo certo")
