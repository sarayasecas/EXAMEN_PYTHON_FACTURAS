"""Genera el diagrama entidad-relación (SVG + HTML) del modelo de facturas."""
import sys
from pathlib import Path

OUT = Path(sys.argv[1])

W_BOX, H_HEAD, H_ROW = 360, 40, 28
NAVY, BLUE, LINE, PKC, FKC = "#1f3a5f", "#2f6db3", "#2f6db3", "#c98a00", "#2f6db3"

# tabla -> (x, y, [(columna, tipo, marca)])  marca: PK, FK, PK/FK, UQ, FK/UQ, ""
T = {
    "sucursal": (40, 110, [
        ("id_sucursal", "INT", "PK"), ("nombre", "VARCHAR(100)", ""),
        ("direccion", "VARCHAR(150)", ""), ("ciudad", "VARCHAR(60)", ""),
        ("cif", "VARCHAR(15)", "UQ"), ("telefono", "VARCHAR(20)", "")]),
    "empleado": (40, 520, [
        ("codigo_empleado", "VARCHAR(10)", "PK"), ("nombre", "VARCHAR(100)", "")]),
    "ticket": (540, 150, [
        ("numero_ticket", "VARCHAR(20)", "PK"), ("fecha", "DATE", ""), ("hora", "TIME", ""),
        ("id_sucursal", "INT", "FK"), ("codigo_empleado", "VARCHAR(10)", "FK"),
        ("subtotal", "DECIMAL(10,2)", ""), ("porcentaje_iva", "DECIMAL(5,2)", ""),
        ("iva", "DECIMAL(10,2)", ""), ("total", "DECIMAL(10,2)", "")]),
    "ticket_linea": (540, 560, [
        ("numero_ticket", "VARCHAR(20)", "PK/FK"), ("num_linea", "INT", "PK"),
        ("id_producto", "INT", "FK"), ("cantidad", "DECIMAL(10,3)", ""),
        ("precio_unitario", "DECIMAL(10,2)", ""), ("importe", "DECIMAL(10,2)", "")]),
    "metodo_pago": (1040, 110, [
        ("id_metodo_pago", "INT", "PK"), ("nombre", "VARCHAR(30)", "UQ")]),
    "pago": (1040, 300, [
        ("id_pago", "INT", "PK"), ("numero_ticket", "VARCHAR(20)", "FK/UQ"),
        ("id_metodo_pago", "INT", "FK"), ("importe", "DECIMAL(10,2)", ""),
        ("autorizacion", "VARCHAR(20)", "")]),
    "producto": (1040, 600, [
        ("id_producto", "INT", "PK"), ("descripcion", "VARCHAR(100)", "UQ"),
        ("unidad_medida", "VARCHAR(5)", "")]),
}
EXTRA = {"metodo_pago"}  # tabla añadida además de las mínimas

def row_y(t, col):
    x, y, cols = T[t]
    i = [c[0] for c in cols].index(col)
    return y + H_HEAD + H_ROW * i + H_ROW / 2

def box_h(t):
    return H_HEAD + H_ROW * len(T[t][2])

svg = []
def add(s): svg.append(s)

# ---- marcadores de cardinalidad (dibujados a mano) ----
def one(x, y, d):
    """Dos barras ("uno y solo uno"). d = dirección hacia fuera de la caja (+1/-1) en x."""
    for k in (10, 17):
        add(f'<line x1="{x+d*k}" y1="{y-8}" x2="{x+d*k}" y2="{y+8}" stroke="{LINE}" stroke-width="2"/>')

def many(x, y, d):
    """Pata de gallo ("uno o muchos")."""
    tip = x + d * 16
    for dy in (-9, 0, 9):
        add(f'<line x1="{tip}" y1="{y}" x2="{x}" y2="{y+dy}" stroke="{LINE}" stroke-width="2"/>')
    add(f'<line x1="{x+d*21}" y1="{y-8}" x2="{x+d*21}" y2="{y+8}" stroke="{LINE}" stroke-width="2"/>')

def one_v(x, y, d):
    for k in (10, 17):
        add(f'<line x1="{x-8}" y1="{y+d*k}" x2="{x+8}" y2="{y+d*k}" stroke="{LINE}" stroke-width="2"/>')

def many_v(x, y, d):
    tip = y + d * 16
    for dx in (-9, 0, 9):
        add(f'<line x1="{x}" y1="{tip}" x2="{x+dx}" y2="{y}" stroke="{LINE}" stroke-width="2"/>')
    add(f'<line x1="{x-8}" y1="{y+d*21}" x2="{x+8}" y2="{y+d*21}" stroke="{LINE}" stroke-width="2"/>')

def label(x, y, text):
    w = 8 * len(text) + 14
    add(f'<rect x="{x-w/2}" y="{y-11}" width="{w}" height="22" rx="11" fill="#fff" stroke="{LINE}" stroke-width="1.2"/>')
    add(f'<text x="{x}" y="{y+4.5}" text-anchor="middle" font-size="12.5" font-weight="700" fill="{BLUE}">{text}</text>')

def rel_h(p, pc, c, cc, ex, card="1 : N"):
    """Relación horizontal en codo: padre(derecha) -> hijo(izquierda) o al revés."""
    px, _, _ = T[p]; cx, _, _ = T[c]
    py, cy = row_y(p, pc), row_y(c, cc)
    if px < cx:
        x1, x2, d1, d2 = px + W_BOX, cx, 1, -1
    else:
        x1, x2, d1, d2 = px, cx + W_BOX, -1, 1
    add(f'<path d="M{x1},{py} H{ex} V{cy} H{x2}" fill="none" stroke="{LINE}" stroke-width="2"/>')
    one(x1, py, d1)
    (one if card == "1 : 1" else many)(x2, cy, d2)
    label(ex, (py + cy) / 2, card)

def rel_v(p, c, card="1 : N"):
    """Relación vertical recta entre dos cajas de la misma columna (padre arriba)."""
    px, py, _ = T[p]; _, cy, _ = T[c]
    x = px + W_BOX / 2
    y1, y2 = py + box_h(p), cy
    add(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{LINE}" stroke-width="2"/>')
    one_v(x, y1, 1)
    many_v(x, y2, -1)
    label(x, (y1 + y2) / 2, card)

# ---- relaciones (se dibujan antes que las cajas) ----
rel_h("sucursal", "id_sucursal", "ticket", "id_sucursal", 460)
rel_h("empleado", "codigo_empleado", "ticket", "codigo_empleado", 480)
rel_v("ticket", "ticket_linea")
rel_h("ticket", "numero_ticket", "pago", "numero_ticket", 960, "1 : 1")
rel_v("metodo_pago", "pago")
rel_h("producto", "id_producto", "ticket_linea", "id_producto", 980)

# ---- cajas ----
for name, (x, y, cols) in T.items():
    h = box_h(name)
    head = BLUE if name in EXTRA else NAVY
    add(f'<rect x="{x+3}" y="{y+4}" width="{W_BOX}" height="{h}" rx="8" fill="#000" opacity="0.07"/>')
    add(f'<rect x="{x}" y="{y}" width="{W_BOX}" height="{h}" rx="8" fill="#fff" stroke="{head}" stroke-width="1.5"/>')
    add(f'<path d="M{x},{y+H_HEAD} V{y+8} a8,8 0 0 1 8,-8 H{x+W_BOX-8} a8,8 0 0 1 8,8 V{y+H_HEAD} Z" fill="{head}"/>')
    add(f'<text x="{x+16}" y="{y+26}" font-size="16" font-weight="700" fill="#fff" font-family="Consolas, monospace">{name}</text>')
    if name in EXTRA:
        add(f'<text x="{x+W_BOX-14}" y="{y+25}" text-anchor="end" font-size="11" font-weight="700" fill="#d6e6fa">TABLA EXTRA</text>')
    for i, (col, typ, mark) in enumerate(cols):
        ry = y + H_HEAD + H_ROW * i
        if i % 2:
            add(f'<rect x="{x+1}" y="{ry}" width="{W_BOX-2}" height="{H_ROW}" fill="#f2f6fb"/>')
        tx = ry + 19
        if mark:
            color = PKC if mark.startswith("PK") else (FKC if mark.startswith("FK") else "#6b7a8c")
            add(f'<text x="{x+14}" y="{tx}" font-size="11" font-weight="700" fill="{color}">{mark}</text>')
        weight = "700" if "PK" in mark else "400"
        add(f'<text x="{x+68}" y="{tx}" font-size="14" font-weight="{weight}" fill="#1d2733" font-family="Consolas, monospace">{col}</text>')
        add(f'<text x="{x+W_BOX-14}" y="{tx}" text-anchor="end" font-size="12.5" fill="#6b7a8c" font-family="Consolas, monospace">{typ}</text>')

W, H = 1440, 940
# ---- título y leyenda ----
title = (f'<text x="40" y="48" font-size="26" font-weight="700" fill="{NAVY}">Modelo de datos · Facturas a SQL</text>'
         f'<text x="40" y="76" font-size="14" fill="#55657a">Diagrama entidad-relación de la base de datos que carga insertUnderlineTickets.sql</text>')
lx, ly = 40, 830
legend = [
    f'<rect x="{lx-10}" y="{ly-24}" width="{W-60}" height="96" rx="8" fill="#f2f6fb"/>',
    f'<text x="{lx}" y="{ly}" font-size="13" font-weight="700" fill="{NAVY}">LEYENDA</text>',
    f'<text x="{lx}" y="{ly+26}" font-size="12.5" fill="#1d2733"><tspan font-weight="700" fill="{PKC}">PK</tspan> clave primaria   '
    f'<tspan font-weight="700" fill="{FKC}">FK</tspan> clave foránea   '
    f'<tspan font-weight="700" fill="#6b7a8c">UQ</tspan> valor único (evita duplicados: CIF, descripción de producto, método de pago, un pago por ticket)</text>',
]
# muestras de notación pata de gallo
sx = lx + 840
legend.append(f'<line x1="{sx}" y1="{ly+22}" x2="{sx+70}" y2="{ly+22}" stroke="{LINE}" stroke-width="2"/>')
svg_backup = svg; svg = []
one(sx, ly + 22, 1); many(sx + 70, ly + 22, -1)
legend += svg; svg = svg_backup
legend.append(f'<text x="{sx+86}" y="{ly+27}" font-size="12.5" fill="#1d2733">uno a muchos (1 : N)</text>')
legend.append(f'<text x="{lx}" y="{ly+52}" font-size="12.5" fill="#1d2733">'
              f'Cabecera azul claro = tabla añadida además de las 6 mínimas.  Precio unitario guardado en cada línea (los precios a granel varían por redondeo).</text>')

body = "\n".join([title] + svg + legend)
svg_doc = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="Segoe UI, Arial, sans-serif"><rect width="{W}" height="{H}" fill="#ffffff"/>{body}</svg>')
(OUT / "diagrama_bd.svg").write_text(svg_doc, encoding="utf-8")
html = (f'<!doctype html><html><head><meta charset="utf-8"><style>'
        f'@page{{size:{W}px {H}px;margin:0}}html,body{{margin:0;padding:0;background:#fff}}svg{{display:block}}'
        f'</style></head><body>{svg_doc}</body></html>')
(OUT / "diagrama_bd.html").write_text(html, encoding="utf-8")
print("ok")
