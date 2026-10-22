#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lettering.py — Gerador automático de letreiros (nomes/datas/frases) em .PES.

Você escolhe o texto, a fonte, a cor e o tamanho; o programa monta os pontos:

  * Ponto cheio (zigue-zague / satin) seguindo o traço de cada letra.
  * Base (underlay) por baixo de cada traço, para o bordado ficar firme.
  * Densidade sempre em milímetros: ao mudar o tamanho ou esticar,
    os pontos são recalculados — não ficam nem amontoados nem abertos.
  * Traços muito largos (letras grandes/grossas) viram preenchimento (tatami).
  * Ordem de costura da ESQUERDA para a DIREITA, linha por linha: cada traço
    termina na ponta oposta e o próximo começa onde o anterior parou
    (sem ir ao fim e voltar ao começo). Pingos de "i" e acentos são
    bordados quando a agulha passa por eles.
  * Arremate (nó) no começo e no fim de cada trecho; corte de linha só
    quando precisa pular de uma letra solta para outra.
  * Arquivo final com origem no canto (0,0) e cortes na posição da agulha
    (a máquina mostra e borda o desenho inteiro, sem deslocamento).

Uso pela linha de comando:
    python3 lettering.py "Felipe" --fonte great_vibes --largura 80 --saida felipe.pes
    python3 lettering.py "João\\nFrederico" --fonte parisienne --largura 90 --altura 50
    python3 lettering.py --fontes            # lista as fontes disponíveis

Requer: pip3 install -r requirements-letreiro.txt
"""
import argparse
import io
import math
import os

import numpy as np
import cv2
import pyembroidery as pe
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Polygon, Point
from shapely import affinity
from skimage.morphology import skeletonize

BASE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BASE, "fonts")
PX = 20          # resolução interna: pixels por milímetro
SPM = 850        # pontos por minuto (para estimar o tempo)

# chave: (arquivo, peso p/ fontes variáveis, nome bonito, descrição)
FONTS = {
    "great_vibes":  ("GreatVibes-Regular.ttf", None, "Great Vibes", "clássica e delicada"),
    "parisienne":   ("Parisienne-Regular.ttf", None, "Parisienne", "romântica, com floreio"),
    "allura":       ("Allura-Regular.ttf", None, "Allura", "leve e elegante"),
    "alex_brush":   ("AlexBrush-Regular.ttf", None, "Alex Brush", "pincel, inclinada"),
    "dancing":      ("DancingScript[wght].ttf", 600, "Dancing Script", "encorpada, fácil de ler"),
    "cookie":       ("Cookie-Regular.ttf", None, "Cookie", "arredondada, cheinha"),
    "pacifico":     ("Pacifico-Regular.ttf", None, "Pacifico", "gordinha, divertida"),
    "playfair":     ("PlayfairDisplay-Italic[wght].ttf", 500, "Playfair Itálico", "tradicional, com serifa"),
    "quicksand":    ("Quicksand[wght].ttf", 700, "Quicksand", "letra de forma, infantil"),
}


# ======================================================================
# 1) TEXTO -> IMAGEM (máscara) em tamanho real
# ======================================================================
def _font(key, size_px):
    fn, weight, _, _ = FONTS[key]
    f = ImageFont.truetype(os.path.join(FONT_DIR, fn), size_px)
    if weight:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def _crop(m, pad=0):
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return m
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return np.pad(m, pad) if pad else m


def _render_line(text, key, font_mm, spacing_mm):
    size = max(8, int(round(font_mm * PX)))
    f = _font(key, size)
    W = int(size * (len(text) + 2) * 1.2) + int(abs(spacing_mm) * PX * len(text))
    big = Image.new("L", (W, int(size * 2.6)), 0)
    d = ImageDraw.Draw(big)
    if abs(spacing_mm) < 1e-6:
        d.text((size * 0.5, size * 0.6), text, font=f, fill=255)
    else:  # espaçamento extra entre letras (desenha uma a uma)
        x = size * 0.5
        for ch in text:
            d.text((x, size * 0.6), ch, font=f, fill=255)
            x += f.getlength(ch) + spacing_mm * PX
    return _crop((np.array(big) > 127).astype(np.uint8))


def _stack_lines(masks, gap_mm, align="center"):
    """Empilha linhas medindo a distância real entre a tinta (floreios encaixam).
    Devolve (máscara, imagem com o nº da linha de cada pixel)."""
    W = max(m.shape[1] for m in masks)
    gap = int(round(gap_mm * PX))
    comp = ids = None
    for li, m in enumerate(masks):
        off = (W - m.shape[1]) // 2 if align == "center" else (0 if align == "left" else W - m.shape[1])
        row = np.zeros((m.shape[0], W), np.uint8)
        row[:, off:off + m.shape[1]] = m
        if comp is None:
            comp, ids = row, row * (li + 1)
            continue
        k = PX  # tolerância horizontal de 1 mm
        bottom = np.full(W, -10**6)
        for x in range(W):
            col = np.nonzero(comp[:, max(0, x - k):x + k + 1].any(axis=1))[0]
            if len(col):
                bottom[x] = col.max()
        top = np.array([np.nonzero(row[:, x])[0].min() if row[:, x].any() else 10**6 for x in range(W)])
        dy = int(np.max(bottom - top)) + gap + 1
        H = max(comp.shape[0], dy + row.shape[0])
        new = np.zeros((H, W), np.uint8); nid = np.zeros((H, W), np.uint8)
        new[:comp.shape[0]] |= comp; nid[:ids.shape[0]] = ids
        new[dy:dy + row.shape[0]] |= row
        nid[dy:dy + row.shape[0]][row > 0] = li + 1
        comp, ids = new, nid
    return comp, ids


def render_mask(text, key, font_mm, stretch_x=1.0, stretch_y=1.0, spacing_mm=0.0, line_gap_mm=1.5):
    lines = [ln for ln in text.replace("\r", "").split("\n") if ln.strip()] or [" "]
    masks = [_render_line(ln, key, font_mm, spacing_mm) for ln in lines]
    m, ids = _stack_lines(masks, line_gap_mm)
    if abs(stretch_x - 1) > 1e-3 or abs(stretch_y - 1) > 1e-3:
        h, w = m.shape
        size = (max(1, int(w * stretch_x)), max(1, int(h * stretch_y)))
        m = (cv2.resize(m * 255, size, interpolation=cv2.INTER_LINEAR) > 127).astype(np.uint8)
        ids = cv2.resize(ids, size, interpolation=cv2.INTER_NEAREST)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return np.pad(m, 40), np.pad(ids, 40)


def fit_font_size(text, key, max_w=None, max_h=None, font_mm=None, margin=0.5, **kw):
    """Acha o tamanho de fonte que respeita largura/altura máximas (mm)."""
    if font_mm:
        return font_mm
    if not max_w and not max_h:
        max_h = 20.0
    f = 20.0
    for _ in range(4):
        m = _crop(render_mask(text, key, f, **kw)[0])
        h, w = m.shape[0] / PX, m.shape[1] / PX
        s = min((max_w - margin) / w if max_w else 1e9, (max_h - margin) / h if max_h else 1e9)
        if abs(s - 1) < 0.004:
            break
        f *= s
    return f


# ======================================================================
# 2) MÁSCARA -> TRAÇOS (esqueleto) -> colunas de ponto cheio
# ======================================================================
def _trace(skel):
    skel = skel.copy().astype(np.uint8)
    H, W = skel.shape
    nb = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    def neigh(y, x):
        return [(y + dy, x + dx) for dy, dx in nb
                if 0 <= y + dy < H and 0 <= x + dx < W and skel[y + dy, x + dx]]

    paths = []
    while True:
        ys, xs = np.nonzero(skel)
        if len(ys) == 0:
            break
        ends = [(y, x) for y, x in zip(ys, xs) if len(neigh(y, x)) == 1]
        cur = min(ends, key=lambda p: p[1]) if ends else (ys[0], xs[0])
        path = [cur]
        skel[cur] = 0
        while True:
            ns = neigh(*cur)
            if not ns:
                break
            if len(path) > 3:  # segue reto nos cruzamentos
                vy, vx = cur[0] - path[-4][0], cur[1] - path[-4][1]
                ns.sort(key=lambda p: -((p[0] - cur[0]) * vy + (p[1] - cur[1]) * vx)
                        / math.hypot(p[0] - cur[0], p[1] - cur[1]))
            cur = ns[0]
            skel[cur] = 0
            path.append(cur)
        paths.append([(float(x), float(y)) for y, x in path])
    return paths


def _chaikin(q, it=3):
    for _ in range(it):
        if len(q) < 3:
            return q
        n = [q[0]]
        for u, v in zip(q, q[1:]):
            n += [(0.75 * u[0] + 0.25 * v[0], 0.75 * u[1] + 0.25 * v[1]),
                  (0.25 * u[0] + 0.75 * v[0], 0.25 * u[1] + 0.75 * v[1])]
        n.append(q[-1])
        q = n
    return q


class Column:
    """Um traço da letra: linha central (mm) + meia-largura em cada ponto."""

    def __init__(self, center, halfw, comp):
        self.c = center          # lista de (x,y) mm, amostrados a cada `step`
        self.h = halfw           # meia-largura (mm) em cada amostra
        self.comp = comp         # nº do componente (letra/pedaço) a que pertence
        self.closed = math.dist(center[0], center[-1]) < 0.6

    def ends(self):
        return self.c[0], self.c[-1]

    def reversed(self):
        return Column(self.c[::-1], self.h[::-1], self.comp)

    def rotate_to(self, i):  # para traços fechados (o, e): começa no ponto i
        c = self.c[:-1]; h = self.h[:-1]
        c = c[i:] + c[:i]; h = h[i:] + h[:i]
        return Column(c + [c[0]], h + [h[0]], self.comp)


def build_columns(mask, dist, lab, density):
    step = density / 2.0                      # um vai-e-vem a cada `density` mm
    skel = skeletonize(mask > 0)
    cols = []
    for p in _trace(skel):
        if len(p) < 3:
            continue
        ls = LineString(p)
        hw0 = max(dist[int(p[0][1]), int(p[0][0])], dist[int(p[-1][1]), int(p[-1][0])])
        if ls.length < max(0.9 * PX, hw0 * 1.6):  # galhinho de cruzamento: o vizinho cobre
            continue
        q = _chaikin(list(ls.simplify(1.5).coords))
        closed = math.dist(q[0], q[-1]) < 0.6 * PX
        if not closed:  # estica as pontas até o fim do traço
            def ext(a, b):
                hw = dist[min(dist.shape[0] - 1, int(a[1])), min(dist.shape[1] - 1, int(a[0]))]
                dd = math.dist(a, b) or 1
                return (a[0] + (a[0] - b[0]) / dd * hw * 0.55, a[1] + (a[1] - b[1]) / dd * hw * 0.55)
            q[0] = ext(q[0], q[1]); q[-1] = ext(q[-1], q[-2])
        ls = LineString(q)
        L = ls.length / PX
        k = max(2, int(L / step))
        c = [ls.interpolate(ls.length * i / k).coords[0] for i in range(k + 1)]
        raw = [dist[min(dist.shape[0] - 1, max(0, int(y))), min(dist.shape[1] - 1, max(0, int(x)))] / PX for x, y in c]
        sm = [float(np.median(raw[max(0, i - 3):i + 4])) for i in range(len(raw))]
        mid = c[len(c) // 2]
        comp = int(lab[min(lab.shape[0] - 1, int(mid[1])), min(lab.shape[1] - 1, int(mid[0]))])
        cols.append(Column([(x / PX, y / PX) for x, y in c], sm, comp))
    return cols


# ======================================================================
# 3) Pontos de cada peça
# ======================================================================
def _normal(c, i):
    a = c[max(0, i - 2)]; b = c[min(len(c) - 1, i + 2)]
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1
    return -dy / n, dx / n


def column_stitches(col, pull=0.12, min_w=1.2, extra=0.3, max_half=3.5):
    """Base + ponto cheio de UM traço. Começa em c[0] e TERMINA em c[-1].
    min_w: largura mínima do traço (mm) — abaixo disso o bordado afunda no tecido.
    extra: engrossa todos os traços (mm), para o letreiro aparecer mais."""
    c = col.c
    hw = [min(max(h + pull + extra / 2, min_w / 2), max_half) for h in col.h]
    n = len(c)
    out = []
    # 1) base: caminhada central de ida (pontos de ~1.5 mm)
    walk = [c[i] for i in range(0, n, max(1, int(1.5 / max(1e-6, math.dist(c[0], c[1]) if n > 1 else 1))))]
    out += walk + [c[-1]]
    # 2) volta: zigue-zague aberto (traço largo) ou nova caminhada central (traço fino)
    if max(hw) >= 0.5:  # traço de 1 mm ou mais: base em zigue-zague (levanta o ponto cheio)
        stride = max(1, int(round(1.4 / max(1e-6, math.dist(c[0], c[1])))))
        for j, i in enumerate(range(n - 1, -1, -stride)):
            nx, ny = _normal(c, i); s = hw[i] * 0.6 * (1 if j % 2 else -1)
            out.append((c[i][0] + nx * s, c[i][1] + ny * s))
        out.append(c[0])
    else:
        out += walk[::-1] + [c[0]]
    # 3) ponto cheio de ida (termina na ponta oposta)
    for i in range(n):
        nx, ny = _normal(c, i); s = hw[i] if i % 2 else -hw[i]
        out.append((c[i][0] + nx * s, c[i][1] + ny * s))
    out.append(c[-1])
    return out


def tatami_rows(poly, angle, spacing, length=3.2):
    """Preenchimento em fileiras (vai-e-volta), contornando buracos (B, A, O...).
    Agrupa as fileiras em blocos contínuos e liga os blocos por dentro da forma.
    Devolve lista de trechos contínuos (cada um é uma lista de pontos)."""
    cen = poly.centroid
    rp = affinity.rotate(poly, -angle, origin=cen)
    minx, miny, maxx, maxy = rp.bounds
    rows = []
    y = miny + spacing / 2
    while y < maxy:
        inter = rp.intersection(LineString([(minx - 1, y), (maxx + 1, y)]))
        segs = []
        for g in getattr(inter, "geoms", [inter]):
            if g.is_empty or g.geom_type != "LineString":
                continue
            xs_ = sorted(p[0] for p in g.coords)
            if xs_[-1] - xs_[0] >= 0.3:
                segs.append((xs_[0], xs_[-1], y))
        rows.append(sorted(segs))
        y += spacing
    used = [[False] * len(r) for r in rows]
    blocks = []
    for ri in range(len(rows)):
        for si in range(len(rows[ri])):
            if used[ri][si]:
                continue
            blk = []; r, k = ri, si
            while True:
                used[r][k] = True
                blk.append(rows[r][k])
                a_, b_, _ = rows[r][k]
                nxt = None
                if r + 1 < len(rows):
                    for j, (a2, b2, _) in enumerate(rows[r + 1]):
                        if not used[r + 1][j] and a2 < b_ - 0.2 and b2 > a_ + 0.2:
                            nxt = j
                            break
                if nxt is None:
                    break
                r, k = r + 1, nxt
            blocks.append(blk)
    out = []
    for blk in blocks:
        pts = []
        for i, (a_, b_, yy) in enumerate(blk):
            off = (i % 3) * length / 3
            xs_ = [a_] + [x for x in (a_ - (a_ % length) + off + k * length for k in range(int((b_ - a_) / length) + 3))
                          if a_ + 0.4 < x < b_ - 0.4] + [b_]
            if pts and abs(pts[-1][0] - xs_[-1]) < abs(pts[-1][0] - xs_[0]):
                xs_ = xs_[::-1]           # começa a fileira pela ponta mais perto
            if pts:
                e = pts[-1]; d = math.dist(e, (xs_[0], yy))
                if d > 2.0:               # degrau na borda: anda em pontos curtos
                    n = int(math.ceil(d / 2.0))
                    pts += [(e[0] + (xs_[0] - e[0]) * j / n, e[1] + (yy - e[1]) * j / n) for j in range(1, n)]
            pts += [(x, yy) for x in xs_]
        out.append([affinity.rotate(Point(p), angle, origin=cen).coords[0] for p in pts])
    # liga blocos: escolhe o próximo bloco mais perto (podendo inverter)
    if not out:
        return out
    res = [out.pop(0)]
    while out:
        e = res[-1][-1]
        bi, rev = min(((i, rv) for i in range(len(out)) for rv in (0, 1)),
                      key=lambda t: math.dist(e, out[t[0]][-1 if t[1] else 0]))
        blk = out.pop(bi)
        blk = blk[::-1] if rev else blk
        if LineString([e, blk[0]]).within(poly.buffer(0.05)):
            n = int(math.ceil(math.dist(e, blk[0]) / 2.0))   # viagem por dentro, pontos de até 2 mm
            res[-1] += [(e[0] + (blk[0][0] - e[0]) * i / n, e[1] + (blk[0][1] - e[1]) * i / n) for i in range(1, n)]
            res[-1] += blk
        else:
            res.append(blk)
    return res


def fill_piece(poly, density):
    """Base cruzada (aberta) + preenchimento na densidade escolhida."""
    out = tatami_rows(poly.buffer(-0.35), 90, 1.6, 4.0)
    out += tatami_rows(poly.buffer(0.1), 0, density, 3.2)
    return out


def _mask_polys(m):
    cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    if hier is None:
        return out
    for i, c in enumerate(cs):
        if hier[0][i][3] != -1 or len(c) < 3:
            continue
        holes = []; j = hier[0][i][2]
        while j != -1:
            if len(cs[j]) >= 3:
                holes.append([(x / PX, y / PX) for x, y in cs[j][:, 0, :]])
            j = hier[0][j][0]
        p = Polygon([(x / PX, y / PX) for x, y in c[:, 0, :]], holes).buffer(0)
        if p.area > 0.05:
            out.append(p)
    return out


# ======================================================================
# 4) Monta tudo em ordem (esquerda -> direita)
# ======================================================================
class Piece:
    def __init__(self, kind, comp, start, end, runs, x):
        self.kind, self.comp, self.start, self.end, self.runs, self.x = kind, comp, start, end, runs, x


def _line_of(ids, pts):
    vals = [int(ids[min(ids.shape[0] - 1, int(y * PX)), min(ids.shape[1] - 1, int(x * PX))]) for x, y in pts]
    vals = [v for v in vals if v]
    return max(set(vals), key=vals.count) if vals else 1


def plan(mask, density, pull):
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    ncomp, lab = cv2.connectedComponents(mask)
    cols = build_columns(mask, dist, lab, density)
    # componentes com traço muito largo -> preenchimento; sem traço (pingo) -> preenchimento
    by_comp = {}
    for c in cols:
        by_comp.setdefault(c.comp, []).append(c)
    fill_comps = set()
    for k in range(1, ncomp):
        cs = by_comp.get(k, [])
        if not cs:
            fill_comps.add(k)
            continue
        widths = [2 * h for c in cs for h in c.h]
        if np.percentile(widths, 80) > 3.8:  # traço largo demais p/ ponto cheio
            fill_comps.add(k)
    pieces = []
    for c in cols:
        if c.comp not in fill_comps:
            pieces.append(("col", c))
    for k in fill_comps:
        m = (lab == k).astype(np.uint8)
        for poly in _mask_polys(m):
            if poly.area < 2.0:  # pingo/acento pequeno: garante tamanho mínimo
                r = math.sqrt(poly.area / math.pi)
                if r < 0.55:
                    poly = poly.buffer(0.55 - r)
                chains = tatami_rows(poly, 75, 0.2, 99)  # vai-e-vem bem fechado (tipo satin)
                chains = [[p for ch in chains for p in ch]]
            else:
                chains = fill_piece(poly, density)
            pieces.append(("fill", (k, chains)))
    return pieces, mask


def order_and_stitch(pieces, mask, ids=None, style=None):
    """Ordena as peças linha por linha, da esquerda para a direita."""
    style = style or {}
    if not pieces:
        return []
    if ids is None:
        return _order_line(list(pieces), style)
    lines = {}
    for kind, obj in pieces:
        pts = obj.c if kind == "col" else [p for ch in obj[1] for p in ch]
        lines.setdefault(_line_of(ids, pts[::5] or pts), []).append((kind, obj))
    seq = []
    for li in sorted(lines):
        seq += _order_line(lines[li], style)
    return seq


def _order_line(todo, style=None):
    style = style or {}

    def candidates(item, pos):
        kind, obj = item
        if kind == "col":
            c = obj
            if c.closed:
                i = min(range(len(c.c) - 1), key=lambda j: math.dist(pos, c.c[j]))
                yield c.rotate_to(i), c.c[i]
            else:
                yield c, c.c[0]
                yield c.reversed(), c.c[-1]
        else:
            k, chains = obj
            yield obj, chains[0][0]

    def xmin(item):
        kind, obj = item
        if kind == "col":
            return min(p[0] for p in obj.c)
        return min(p[0] for ch in obj[1] for p in ch)

    def comp_of(item):
        return item[1].comp if item[0] == "col" else item[1][0]

    # começa pelo ponto mais à esquerda
    first = min(todo, key=xmin)
    pos = (xmin(first) - 1, 0)
    seq = []
    cur_comp = None
    while todo:
        best = None
        for idx, item in enumerate(todo):
            for var, start in candidates(item, pos):
                d = math.dist(pos, start)
                back = max(0.0, pos[0] - start[0])               # penaliza voltar para a esquerda
                other = 0.0 if comp_of(item) == cur_comp else 12.0  # termina a letra antes de pular
                cost = d + 1.5 * back + other
                if best is None or cost < best[0]:
                    best = (cost, idx, item[0], var)
        _, idx, kind, var = best
        item = todo.pop(idx)
        cur_comp = comp_of(item)
        if kind == "col":
            pts = column_stitches(var, **style)
            seq.append(pts)
            pos = pts[-1]
        else:
            for ch in var[1]:
                seq.append(ch)
            pos = var[1][-1][-1]
    return seq


def _inside(mask, a, b):
    n = max(2, int(math.dist(a, b) / 0.3))
    for i in range(n + 1):
        x = a[0] + (b[0] - a[0]) * i / n; y = a[1] + (b[1] - a[1]) * i / n
        if not mask[min(mask.shape[0] - 1, max(0, int(y * PX))), min(mask.shape[1] - 1, max(0, int(x * PX)))]:
            return False
    return True


def to_pattern(seq, mask, color_hex, name="Linha"):
    """Converte os trechos em comandos de máquina (com nó, corte e viagem interna)."""
    pts_all = [p for r in seq for p in r]
    mx = min(p[0] for p in pts_all); my = min(p[1] for p in pts_all)
    T = lambda p: ((p[0] - mx) * 10, (p[1] - my) * 10)  # décimos de mm, origem no canto
    pat = pe.EmbPattern()
    t = pe.EmbThread(); t.color = int(color_hex.lstrip("#"), 16); t.description = name
    pat.add_thread(t)
    last = None
    prev_pt = None

    def stitch(p):
        pat.add_stitch_absolute(pe.STITCH, *p)

    def tie(a, b):  # nó: 3 pontinhos para frente e para trás
        dx, dy = b[0] - a[0], b[1] - a[1]; d = math.hypot(dx, dy) or 1
        ux, uy = dx / d * 4, dy / d * 4  # 0,4 mm
        stitch(a); stitch((a[0] + ux, a[1] + uy)); stitch(a); stitch((a[0] + ux, a[1] + uy)); stitch(a)

    for r in seq:
        R = [T(p) for p in r]
        # tira pontinhos curtos demais (< 0,3 mm), menos o último
        clean = [R[0]]
        for p in R[1:-1]:
            if math.dist(p, clean[-1]) >= 3:
                clean.append(p)
        clean.append(R[-1])
        R = clean
        if last is None:
            pat.add_stitch_absolute(pe.JUMP, *R[0])
            tie(R[0], R[1] if len(R) > 1 else R[0])
        else:
            d = math.dist(last, R[0])
            a_mm = (last[0] / 10 + mx, last[1] / 10 + my); b_mm = r[0]
            if d <= 10:                                   # até 1 mm: emenda direto
                stitch(R[0])
            elif d <= 70 and _inside(mask, a_mm, b_mm):   # viagem por dentro da letra
                n = int(math.ceil(d / 20))
                for i in range(1, n + 1):
                    stitch((last[0] + (R[0][0] - last[0]) * i / n, last[1] + (R[0][1] - last[1]) * i / n))
            else:                                         # pula: arremata, corta, pula
                tie(last, prev_pt or last)
                pat.add_stitch_absolute(pe.TRIM, *last)
                pat.add_stitch_absolute(pe.JUMP, *R[0])
                tie(R[0], R[1] if len(R) > 1 else R[0])
        for p in R[1:]:
            stitch(p)
        prev_pt = R[-2] if len(R) > 1 else prev_pt
        last = R[-1]
    tie(last, prev_pt or last)
    pat.add_stitch_absolute(pe.TRIM, *last)
    pat.add_stitch_absolute(pe.END, *last)
    return pat


# ======================================================================
# 5) API principal
# ======================================================================
def make(text, font="great_vibes", max_w=None, max_h=None, font_mm=None,
         stretch_x=100, stretch_y=100, spacing_mm=0.0, line_gap_mm=1.5,
         color="#6E9BC4", density=0.40, pull=0.12, min_w=1.2, bold=0.3):
    """Gera o bordado. Retorna dict com bytes do .pes, svg e ficha técnica."""
    if font not in FONTS:
        raise ValueError("Fonte desconhecida: %s" % font)
    if not text.strip():
        raise ValueError("Digite um texto.")
    density = min(max(float(density), 0.30), 0.60)
    kw = dict(stretch_x=stretch_x / 100.0, stretch_y=stretch_y / 100.0,
              spacing_mm=spacing_mm, line_gap_mm=line_gap_mm)
    # o ponto cheio (e o engrossar) deixam o desenho um pouco maior que a fonte
    fmm = fit_font_size(text, font, max_w, max_h, font_mm, margin=0.6 + 1.2 * max(0.0, float(bold)), **kw)
    mask, ids = render_mask(text, font, fmm, **kw)
    pieces, mask = plan(mask, density, pull)
    style = dict(pull=pull, min_w=max(0.6, float(min_w)), extra=max(0.0, float(bold)))
    seq = order_and_stitch(pieces, mask, ids, style)
    if not seq:
        raise ValueError("Nada para bordar.")
    pat = to_pattern(seq, mask, color, FONTS[font][2])
    buf = io.BytesIO()
    pe.write_pes(pat, buf, {"version": 6})
    data = buf.getvalue()
    info = analyze_pattern(pe.read_pes(io.BytesIO(data)), color)
    info.update({"font_mm": round(fmm, 2), "font": FONTS[font][2]})
    return {"pes": data, **info}


def analyze_pattern(p, color="#6E9BC4", max_px=760):
    st = p.stitches
    xs = [s[0] for s in st]; ys = [s[1] for s in st]
    w, h = (max(xs) - min(xs)) / 10, (max(ys) - min(ys)) / 10
    n = sum(1 for s in st if (s[2] & 0xFF) == pe.STITCH)
    trims = sum(1 for s in st if (s[2] & 0xFF) == pe.TRIM)
    sc = max_px / max(w, h, 1)
    W, H = w * sc + 20, h * sc + 20
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.0f %.0f" width="100%%">' % (W, H),
             '<rect width="100%" height="100%" fill="#f7f5f0"/>']
    d = []; prev = None
    for x, y, c in st:
        c &= 0xFF
        P = (10 + (x - min(xs)) / 10 * sc, 10 + (y - min(ys)) / 10 * sc)
        if c == pe.STITCH:
            d.append(("L" if prev else "M") + "%.1f,%.1f" % P)
            prev = P
        else:
            prev = None
    lw = max(0.6, 0.38 * sc)
    parts.append('<path d="%s" fill="none" stroke="%s" stroke-width="%.2f" stroke-linecap="round" '
                 'stroke-linejoin="round"/>' % ("".join(d), color, lw))
    parts.append("</svg>")
    return {"width_mm": round(w, 1), "height_mm": round(h, 1), "stitches": n, "trims": trims,
            "minutes": round(n / SPM + trims * 0.1, 1), "svg": "".join(parts)}


def preview_png(svg_info_pattern_bytes, path, color="#6E9BC4", px_mm=12):
    p = pe.read_pes(io.BytesIO(svg_info_pattern_bytes))
    st = p.stitches
    xs = [s[0] for s in st]; ys = [s[1] for s in st]
    W = int((max(xs) - min(xs)) / 10 * px_mm) + 40; H = int((max(ys) - min(ys)) / 10 * px_mm) + 40
    im = Image.new("RGB", (W, H), (247, 245, 240)); dr = ImageDraw.Draw(im)
    rgb = tuple(int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    prev = None
    for x, y, c in st:
        c &= 0xFF
        P = (20 + (x - min(xs)) / 10 * px_mm, 20 + (y - min(ys)) / 10 * px_mm)
        if c == pe.STITCH:
            if prev:
                dr.line([prev, P], fill=rgb, width=max(1, int(0.38 * px_mm)))
            prev = P
        else:
            prev = None
    im.save(path)


def main():
    ap = argparse.ArgumentParser(description="Gera letreiro bordado (.pes) a partir de texto.")
    ap.add_argument("texto", nargs="?", help='texto; use \\n para quebrar linha (ex.: "João\\nFrederico")')
    ap.add_argument("--fonte", default="great_vibes", help="chave da fonte (veja --fontes)")
    ap.add_argument("--largura", type=float, help="largura máxima em mm")
    ap.add_argument("--altura", type=float, help="altura máxima em mm")
    ap.add_argument("--tamanho-fonte", type=float, help="tamanho exato da fonte em mm (ignora largura/altura)")
    ap.add_argument("--esticar-h", type=float, default=100, help="esticar na horizontal, %% (100 = normal)")
    ap.add_argument("--esticar-v", type=float, default=100, help="esticar na vertical, %% (100 = normal)")
    ap.add_argument("--espaco", type=float, default=0.0, help="espaço extra entre letras, mm")
    ap.add_argument("--entre-linhas", type=float, default=1.5, help="espaço entre linhas, mm")
    ap.add_argument("--cor", default="#6E9BC4", help="cor da linha (hex)")
    ap.add_argument("--densidade", type=float, default=0.40, help="distância entre pontos, mm (0,30 fechado – 0,60 aberto)")
    ap.add_argument("--traco-minimo", type=float, default=1.2, help="largura mínima do traço, mm (padrão 1,2)")
    ap.add_argument("--engrossar", type=float, default=0.3, help="engrossa os traços, mm (0 = como a fonte)")
    ap.add_argument("--saida", default="letreiro.pes")
    ap.add_argument("--fontes", action="store_true", help="lista as fontes")
    a = ap.parse_args()
    if a.fontes or not a.texto:
        for k, (_, _, nome, desc) in FONTS.items():
            print(f"  {k:12s} {nome:18s} {desc}")
        return
    r = make(a.texto.replace("\\n", "\n"), a.fonte, a.largura, a.altura, a.tamanho_fonte,
             a.esticar_h, a.esticar_v, a.espaco, a.entre_linhas, a.cor, a.densidade,
             min_w=a.traco_minimo, bold=a.engrossar)
    with open(a.saida, "wb") as f:
        f.write(r["pes"])
    preview_png(r["pes"], os.path.splitext(a.saida)[0] + "_previa.png", a.cor)
    print(f"{a.saida}: {r['width_mm']} x {r['height_mm']} mm, {r['stitches']} pontos, "
          f"{r['trims']} cortes, ~{r['minutes']} min (fonte {r['font']} {r['font_mm']} mm)")


if __name__ == "__main__":
    main()
