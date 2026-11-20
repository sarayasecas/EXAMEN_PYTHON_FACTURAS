#!/usr/bin/env python3
"""Convierte tickets .txt en un script SQL. Uso: python build_insert_from_tickets.py facturas/"""
import argparse, re, sys, unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

TOL = Decimal("0.01")
NUM = r"(?P<valor>-?\d+[.,]\d{2})\s*€?\s*$"
RE_RAYA = re.compile(r"^\s*-{10,}\s*$")
RE_CIF = re.compile(r"CIF:\s*(?P<cif>[A-Z0-9]+)\s+Tel:\s*(?P<tel>[\d\s]+)", re.I)
RE_FECHA = re.compile(r"^Fecha:\s*(?P<fecha>\d{2}/\d{2}/\d{4})\s+Hora:\s*(?P<hora>\d{2}:\d{2})\s*$", re.I)
RE_CAJERO = re.compile(r"^Cajero:\s*(?P<codigo>\d+)\s*-\s*(?P<nombre>.+?)\s*$", re.I)
RE_TICKET = re.compile(r"^Ticket:\s*(?P<numero>\d+)\s*$", re.I)
RE_CAB_LINEAS = re.compile(r"^\s*CANT\s+DESCRIPCI", re.I)
RE_PRODUCTO = re.compile(r"^\s*(?P<cant>\S+)\s+(?P<desc>.+?)\s+(?P<importe>-?\d+[.,]\d{2})\s*€?\s*$")
RE_NUMERO = re.compile(r"^\d+(?:[.,]\d+)?$")
RE_SUBTOTAL = re.compile(r"^SUBTOTAL\s+" + NUM, re.I)
RE_IVA = re.compile(r"^IVA\s*\(\s*(?P<pct>\d+(?:[.,]\d+)?)\s*%\s*\)\s+" + NUM, re.I)
RE_TOTAL = re.compile(r"^TOTAL A PAGAR\s+" + NUM, re.I)
RE_PAGO = re.compile(r"^FORMA DE PAGO:\s*(?P<metodo>.+?)\s*$", re.I)
RE_AUT = re.compile(r"^Autorizaci[oó]n:\s*(?P<codigo>\w+)\s*$", re.I)


class TicketError(Exception):
    pass


@dataclass
class Linea:
    num: int
    desc: str
    cant: Decimal
    importe: Decimal

    @property
    def precio(self):
        return (self.importe / self.cant).quantize(TOL, ROUND_HALF_UP)


@dataclass
class Ticket:
    archivo: str
    nombre: str = ""
    direccion: str = ""
    ciudad: str = ""
    cif: str = ""
    tel: str = ""
    fecha: str = ""
    hora: str = ""
    cajero: str = ""
    cajero_nombre: str = ""
    numero: str = ""
    lineas: list = field(default_factory=list)
    subtotal: Decimal = None
    iva_pct: Decimal = None
    iva: Decimal = None
    total: Decimal = None
    metodo: str = ""
    autorizacion: str = None
    avisos: list = field(default_factory=list)


def dec(s):
    return Decimal(s.replace(",", "."))


def norm(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip().casefold()


def q(v):
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def leer(ruta):
    try:
        return ruta.read_text(encoding="utf-8-sig").splitlines(), []
    except UnicodeDecodeError:
        return ruta.read_text(encoding="cp1252").splitlines(), ["el archivo no está en UTF-8; se ha leído como Windows-1252"]


SIGUIENTE = {"CABECERA": "DATOS", "ENCABEZADO": "LINEAS", "LINEAS": "TOTALES", "PAGO": "PIE"}


def parse_ticket(ruta):
    lineas, avisos = leer(ruta)
    t = Ticket(ruta.name, avisos=avisos)
    if not any(l.strip() for l in lineas):
        raise TicketError("archivo vacío")
    estado, cabecera = "CABECERA", []
    for n, linea in enumerate((l.strip() for l in lineas), 1):
        if RE_RAYA.match(linea):
            estado = SIGUIENTE.get(estado, estado)
            continue
        if not linea or estado == "PIE":
            continue
        if estado == "CABECERA":
            if m := RE_CIF.search(linea):
                t.cif, t.tel = m["cif"].upper(), re.sub(r"\s+", "", m["tel"])
            else:
                cabecera.append(linea)
        elif estado == "DATOS":
            if m := RE_FECHA.match(linea):
                try:
                    f = datetime.strptime(f"{m['fecha']} {m['hora']}", "%d/%m/%Y %H:%M")
                except ValueError:
                    raise TicketError(f"línea {n}: fecha u hora imposible '{m['fecha']} {m['hora']}'") from None
                t.fecha, t.hora = f.strftime("%Y-%m-%d"), f.strftime("%H:%M:%S")
            elif m := RE_CAJERO.match(linea):
                t.cajero, t.cajero_nombre = m["codigo"], m["nombre"]
            elif m := RE_TICKET.match(linea):
                t.numero = m["numero"]
            elif RE_CAB_LINEAS.match(linea):
                estado = "ENCABEZADO"
            else:
                raise TicketError(f"línea {n}: dato de cabecera no reconocido: '{linea}'")
        elif estado == "ENCABEZADO":
            raise TicketError(f"línea {n}: se esperaba una raya tras el encabezado de productos")
        elif estado == "LINEAS":
            m = RE_PRODUCTO.match(linea)
            if not m:
                raise TicketError(f"línea {n}: línea de producto con formato incorrecto: '{linea}'")
            if not RE_NUMERO.match(m["cant"]):
                raise TicketError(f"línea {n}: la cantidad '{m['cant']}' del producto '{m['desc']}' no es numérica")
            cant, importe = dec(m["cant"]), dec(m["importe"])
            if cant <= 0:
                raise TicketError(f"línea {n}: la cantidad del producto '{m['desc']}' debe ser mayor que 0")
            if importe < 0:
                raise TicketError(f"línea {n}: importe negativo en '{m['desc']}'")
            t.lineas.append(Linea(len(t.lineas) + 1, m["desc"].strip(), cant, importe))
        elif estado == "TOTALES":
            if m := RE_SUBTOTAL.match(linea):
                t.subtotal = dec(m["valor"])
            elif m := RE_IVA.match(linea):
                t.iva_pct, t.iva = dec(m["pct"]), dec(m["valor"])
            elif m := RE_TOTAL.match(linea):
                t.total = dec(m["valor"])
            elif m := RE_PAGO.match(linea):
                t.metodo, estado = m["metodo"].upper(), "PAGO"
            else:
                raise TicketError(f"línea {n}: línea de totales no reconocida: '{linea}'")
        elif estado == "PAGO":
            if not (m := RE_AUT.match(linea)):
                raise TicketError(f"línea {n}: línea de pago no reconocida: '{linea}'")
            t.autorizacion = m["codigo"]
    if cabecera:
        t.nombre = cabecera[0]
    if len(cabecera) > 1:
        direccion, _, ciudad = cabecera[1].rpartition(" - ")
        t.direccion, t.ciudad = direccion or cabecera[1], ciudad if direccion else ""
    validar(t)
    return t


def validar(t):
    obligatorios = {"nombre de la sucursal": t.nombre, "CIF de la sucursal": t.cif, "fecha": t.fecha,
                    "cajero": t.cajero, "número de ticket": t.numero, "SUBTOTAL": t.subtotal, "IVA": t.iva,
                    "TOTAL A PAGAR": t.total, "FORMA DE PAGO": t.metodo}
    faltan = [k for k, v in obligatorios.items() if v in ("", None)]
    if faltan:
        raise TicketError("formato incorrecto, faltan datos: " + ", ".join(faltan))
    if not t.lineas:
        raise TicketError("formato incorrecto: el ticket no tiene líneas de producto")
    suma = sum(l.importe for l in t.lineas)
    if abs(suma - t.subtotal) > TOL:
        raise TicketError(f"la suma de las líneas ({suma}) no coincide con el SUBTOTAL ({t.subtotal})")
    iva = (t.subtotal * t.iva_pct / 100).quantize(TOL, ROUND_HALF_UP)
    if abs(iva - t.iva) > TOL:
        raise TicketError(f"el IVA ({t.iva}) no corresponde al {t.iva_pct}% del subtotal ({iva})")
    if abs(t.subtotal + t.iva - t.total) > TOL:
        raise TicketError(f"SUBTOTAL + IVA ({t.subtotal + t.iva}) no coincide con el TOTAL ({t.total})")
    vistos = set()
    for l in t.lineas:
        if norm(l.desc) in vistos:
            t.avisos.append(f"el producto '{l.desc}' aparece en varias líneas")
        vistos.add(norm(l.desc))


class Catalogo:
    def __init__(self):
        self.sucursales, self.empleados, self.productos, self.metodos, self.tickets = {}, {}, {}, {}, {}
        self.dup = {"empleado": 0, "producto": 0, "sucursal": 0}

    def comprobar(self, t):
        if t.numero in self.tickets:
            raise TicketError(f"número de ticket {t.numero} repetido (ya está en {self.tickets[t.numero].archivo})")
        previo = self.empleados.get(t.cajero)
        if previo is not None and norm(previo) != norm(t.cajero_nombre):
            raise TicketError(f"código de cajero {t.cajero} repetido con otro nombre: "
                              f"'{t.cajero_nombre}' (ya registrado como '{previo}')")
        suc = self.sucursales.get(t.cif)
        if suc is not None and norm(suc["nombre"]) != norm(t.nombre):
            raise TicketError(f"CIF {t.cif} repetido con otro nombre de sucursal: "
                              f"'{t.nombre}' (ya registrado como '{suc['nombre']}')")

    def agregar(self, t):
        if t.cif in self.sucursales:
            self.dup["sucursal"] += 1
        else:
            self.sucursales[t.cif] = {"id": len(self.sucursales) + 1, "nombre": t.nombre,
                                      "direccion": t.direccion, "ciudad": t.ciudad, "tel": t.tel}
        if t.cajero in self.empleados:
            self.dup["empleado"] += 1
        else:
            self.empleados[t.cajero] = t.cajero_nombre
        for l in t.lineas:
            clave = norm(l.desc)
            if clave in self.productos:
                self.dup["producto"] += 1
            else:
                self.productos[clave] = {"id": len(self.productos) + 1, "desc": l.desc,
                                         "unidad": "kg" if "(kg)" in clave else "ud"}
        self.metodos.setdefault(t.metodo, len(self.metodos) + 1)
        self.tickets[t.numero] = t


DDL = """\
DROP TABLE IF EXISTS pago;
DROP TABLE IF EXISTS ticket_linea;
DROP TABLE IF EXISTS ticket;
DROP TABLE IF EXISTS metodo_pago;
DROP TABLE IF EXISTS producto;
DROP TABLE IF EXISTS empleado;
DROP TABLE IF EXISTS sucursal;

CREATE TABLE sucursal (id_sucursal INT PRIMARY KEY, nombre VARCHAR(100) NOT NULL, direccion VARCHAR(150),
    ciudad VARCHAR(60), cif VARCHAR(15) NOT NULL UNIQUE, telefono VARCHAR(20));
CREATE TABLE empleado (codigo_empleado VARCHAR(10) PRIMARY KEY, nombre VARCHAR(100) NOT NULL);
CREATE TABLE producto (id_producto INT PRIMARY KEY, descripcion VARCHAR(100) NOT NULL UNIQUE,
    unidad_medida VARCHAR(5) NOT NULL);
CREATE TABLE metodo_pago (id_metodo_pago INT PRIMARY KEY, nombre VARCHAR(30) NOT NULL UNIQUE);
CREATE TABLE ticket (numero_ticket VARCHAR(20) PRIMARY KEY, fecha DATE NOT NULL, hora TIME NOT NULL,
    id_sucursal INT NOT NULL, codigo_empleado VARCHAR(10) NOT NULL, subtotal DECIMAL(10,2) NOT NULL,
    porcentaje_iva DECIMAL(5,2) NOT NULL, iva DECIMAL(10,2) NOT NULL, total DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (id_sucursal) REFERENCES sucursal (id_sucursal),
    FOREIGN KEY (codigo_empleado) REFERENCES empleado (codigo_empleado));
CREATE TABLE ticket_linea (numero_ticket VARCHAR(20) NOT NULL, num_linea INT NOT NULL, id_producto INT NOT NULL,
    cantidad DECIMAL(10,3) NOT NULL, precio_unitario DECIMAL(10,2) NOT NULL, importe DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (numero_ticket, num_linea),
    FOREIGN KEY (numero_ticket) REFERENCES ticket (numero_ticket),
    FOREIGN KEY (id_producto) REFERENCES producto (id_producto));
CREATE TABLE pago (id_pago INT PRIMARY KEY, numero_ticket VARCHAR(20) NOT NULL UNIQUE, id_metodo_pago INT NOT NULL,
    importe DECIMAL(10,2) NOT NULL, autorizacion VARCHAR(20),
    FOREIGN KEY (numero_ticket) REFERENCES ticket (numero_ticket),
    FOREIGN KEY (id_metodo_pago) REFERENCES metodo_pago (id_metodo_pago));
"""


def insert(tabla, columnas, filas):
    if not filas:
        return f"-- (sin filas para {tabla})\n"
    valores = ",\n".join("    (" + ", ".join(map(str, f)) + ")" for f in filas)
    return f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES\n{valores};\n"


def generar_sql(cat, ddl=True):
    tks = sorted(cat.tickets.values(), key=lambda t: t.numero)
    s, pid = cat.sucursales, lambda d: cat.productos[norm(d)]["id"]
    partes = [f"-- insertUnderlineTickets.sql generado el {datetime.now():%d/%m/%Y %H:%M:%S}",
              f"-- Tickets: {len(tks)} | Empleados: {len(cat.empleados)} | "
              f"Productos: {len(cat.productos)} | Sucursales: {len(s)}\n"]
    if ddl:
        partes.append(DDL)
    partes += ["BEGIN;\n",
        insert("sucursal", ["id_sucursal", "nombre", "direccion", "ciudad", "cif", "telefono"],
               [[v["id"], q(v["nombre"]), q(v["direccion"]), q(v["ciudad"]), q(c), q(v["tel"])] for c, v in s.items()]),
        insert("empleado", ["codigo_empleado", "nombre"], [[q(c), q(n)] for c, n in sorted(cat.empleados.items())]),
        insert("producto", ["id_producto", "descripcion", "unidad_medida"],
               [[p["id"], q(p["desc"]), q(p["unidad"])] for p in cat.productos.values()]),
        insert("metodo_pago", ["id_metodo_pago", "nombre"], [[i, q(n)] for n, i in cat.metodos.items()]),
        insert("ticket", ["numero_ticket", "fecha", "hora", "id_sucursal", "codigo_empleado",
                          "subtotal", "porcentaje_iva", "iva", "total"],
               [[q(t.numero), q(t.fecha), q(t.hora), s[t.cif]["id"], q(t.cajero),
                 t.subtotal, t.iva_pct, t.iva, t.total] for t in tks]),
        insert("ticket_linea", ["numero_ticket", "num_linea", "id_producto", "cantidad", "precio_unitario", "importe"],
               [[q(t.numero), l.num, pid(l.desc), l.cant, l.precio, l.importe] for t in tks for l in t.lineas]),
        insert("pago", ["id_pago", "numero_ticket", "id_metodo_pago", "importe", "autorizacion"],
               [[i, q(t.numero), cat.metodos[t.metodo], t.total, q(t.autorizacion)] for i, t in enumerate(tks, 1)]),
        "COMMIT;\n"]
    return "\n".join(partes)


def procesar_carpeta(carpeta):
    if not carpeta.is_dir():
        raise FileNotFoundError(f"la carpeta '{carpeta}' no existe o no es un directorio")
    archivos = sorted(p for p in carpeta.iterdir() if p.suffix.lower() == ".txt" and p.is_file())
    if not archivos:
        raise FileNotFoundError(f"la carpeta '{carpeta}' no contiene archivos .txt")
    cat, ok, malos, avisos = Catalogo(), [], [], []
    for ruta in archivos:
        try:
            t = parse_ticket(ruta)
            cat.comprobar(t)
        except TicketError as e:
            malos.append((ruta.name, str(e)))
            continue
        except OSError as e:
            malos.append((ruta.name, f"no se pudo leer el archivo: {e.strerror}"))
            continue
        cat.agregar(t)
        ok.append(ruta.name)
        avisos += [(ruta.name, a) for a in t.avisos]
    return cat, ok, malos, avisos


def main(argv=None):
    p = argparse.ArgumentParser(description="Genera un script SQL a partir de tickets .txt.")
    p.add_argument("carpeta", type=Path)
    p.add_argument("-o", "--salida", type=Path, default=Path("insertUnderlineTickets.sql"))
    p.add_argument("--log", type=Path, default=Path("errores_tickets.log"))
    p.add_argument("--estricto", action="store_true", help="si hay errores, no genera el SQL")
    p.add_argument("--solo-inserts", action="store_true", help="sin CREATE TABLE")
    a = p.parse_args(argv)
    for flujo in (sys.stdout, sys.stderr):
        flujo.reconfigure(encoding="utf-8", errors="replace")
    try:
        cat, ok, malos, avisos = procesar_carpeta(a.carpeta)
        generar = bool(ok) and not (a.estricto and malos)
        if generar:
            a.salida.write_text(generar_sql(cat, not a.solo_inserts), encoding="utf-8")
        d = cat.dup
        log = ["=" * 70, f"LOG DE PROCESAMIENTO DE FACTURAS - {datetime.now():%d/%m/%Y %H:%M:%S}",
               f"Carpeta: {a.carpeta.resolve()}", "=" * 70,
               f"Facturas leídas:     {len(ok) + len(malos)}", f"Facturas procesadas: {len(ok)}",
               f"Facturas rechazadas: {len(malos)}", f"SQL generado:        {'sí' if generar else 'NO'}",
               "", "FACTURAS NO PROCESADAS", "-" * 70,
               *([f"[ERROR] {f}: {m}" for f, m in malos] or ["(ninguna)"]),
               "", "AVISOS", "-" * 70, *([f"[AVISO] {f}: {m}" for f, m in avisos] or ["(ninguno)"]),
               "", "DUPLICADOS EVITADOS (reutilizados en vez de insertarse otra vez)", "-" * 70,
               f"Empleados: {d['empleado']}  |  Productos: {d['producto']}  |  Sucursales: {d['sucursal']}", ""]
        a.log.write_text("\n".join(log), encoding="utf-8")
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except PermissionError as e:
        print(f"ERROR: sin permisos para escribir '{e.filename}'", file=sys.stderr)
        return 2
    print(f"Facturas leídas: {len(ok) + len(malos)}  |  procesadas: {len(ok)}  |  rechazadas: {len(malos)}")
    for f, m in malos:
        print(f"  [ERROR] {f}: {m}", file=sys.stderr)
    for f, m in avisos:
        print(f"  [AVISO] {f}: {m}")
    if generar:
        print(f"SQL generado: {a.salida}  ({len(cat.tickets)} tickets, "
              f"{len(cat.empleados)} empleados, {len(cat.productos)} productos)")
    else:
        print("Modo estricto: hay facturas con errores, NO se ha generado el SQL." if malos and a.estricto
              else "No hay ninguna factura válida: NO se ha generado el SQL.", file=sys.stderr)
    print(f"Log: {a.log}")
    return 2 if not generar else 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
