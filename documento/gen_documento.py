"""Genera documento.html (y, con Edge, documento.pdf) a partir de los archivos reales del proyecto.

Uso:  python documento/gen_documento.py
Lee: facturas/, insertUnderlineTickets.sql, errores_tickets.log, pruebas_errores/salida_pruebas.log
y vuelve a ejecutar el script para capturar su salida real por consola.
"""
import html
import re
import subprocess
import sys
from pathlib import Path

NOMBRE = "Saray Rodríguez"
ASIGNATURA = "Examen de Python · Minería de datos de facturas"

RAIZ = Path(__file__).resolve().parent.parent
DOC = Path(__file__).resolve().parent
e = html.escape


def ejecutar(*args):
    """Ejecuta el script y devuelve (comando, salida en orden de consola, código)."""
    cmd = [sys.executable, "build_insert_from_tickets.py", *args]
    r = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
    # En una consola real el resumen (stdout) sale antes que los errores (stderr).
    out = r.stdout.splitlines()
    err = r.stderr.splitlines()
    lineas = out[:1] + err + out[1:]
    return "python build_insert_from_tickets.py " + " ".join(args), lineas, r.returncode


def terminal(cmd, lineas, code):
    """Bloque con aspecto de terminal de PowerShell."""
    cuerpo = []
    for l in lineas:
        cls = "err" if "[ERROR]" in l else ("ok" if l.startswith(("SQL generado", "Log:")) else "")
        cuerpo.append(f'<span class="{cls}">{e(l)}</span>')
    return f"""
<div class="term">
  <div class="term-bar"><span></span><span></span><span></span><b>Windows PowerShell</b></div>
  <pre><span class="ps">PS C:\\Users\\saray\\EXAMEN_PYTHON_FACTURAS&gt;</span> {e(cmd)}
{chr(10).join(cuerpo)}
<span class="ps">PS C:\\Users\\saray\\EXAMEN_PYTHON_FACTURAS&gt;</span> $LASTEXITCODE
{code}</pre>
</div>"""


def extracto_sql(sql: str) -> str:
    """Vista parcial del .sql: cabecera, un CREATE TABLE y las primeras filas de cada INSERT."""
    lineas = sql.splitlines()
    res, i = [], 0
    res += lineas[:5] + ["", "-- (...) DROP TABLE / CREATE TABLE de las 7 tablas (...)", ""]
    # CREATE TABLE ticket completo
    ini = next(n for n, l in enumerate(lineas) if l.startswith("CREATE TABLE ticket ("))
    fin = next(n for n in range(ini, len(lineas)) if lineas[n].startswith(");"))
    res += lineas[ini:fin + 1] + ["", "-- (...)", ""]
    ini = next(n for n, l in enumerate(lineas) if l == "BEGIN;")
    i = ini
    while i < len(lineas):
        l = lineas[i]
        res.append(l)
        if l.startswith("INSERT INTO"):
            filas = []
            j = i + 1
            while j < len(lineas) and lineas[j].startswith("    ("):
                filas.append(lineas[j]); j += 1
            res += filas[:3]
            if len(filas) > 3:
                res.append(f"    -- (... {len(filas) - 3} filas más ...)")
            i = j
            continue
        i += 1
    return "\n".join(res)


def resaltar_sql(texto: str) -> str:
    salida = []
    for linea in texto.split("\n"):
        t = e(linea)
        if linea.lstrip().startswith("--"):
            salida.append(f'<span class="c">{t}</span>')
            continue
        for kw in ["INSERT INTO", "VALUES", "CREATE TABLE", "PRIMARY KEY", "FOREIGN KEY",
                   "REFERENCES", "NOT NULL", "UNIQUE", "BEGIN;", "COMMIT;"]:
            t = re.sub(rf"(?<![\w>])({re.escape(kw)})", r'<span class="k">\1</span>', t)
        t = re.sub(r"(&#x27;[^&]*?&#x27;)", r'<span class="s">\1</span>', t)
        salida.append(t)
    return "\n".join(salida)


def main():
    sql = (RAIZ / "insertUnderlineTickets.sql").read_text(encoding="utf-8")
    factura = (RAIZ / "facturas" / "factura_002.txt").read_text(encoding="utf-8")
    # filas reales del ticket 20010002 en el SQL
    filas_002 = [l.strip() for l in sql.splitlines() if "'20010002'" in l]
    run_ok = ejecutar("facturas/")
    run_err = ejecutar("pruebas_errores/", "-o", "pruebas_errores/salida_pruebas.sql",
                       "--log", "pruebas_errores/salida_pruebas.log")
    log_err = (RAIZ / "pruebas_errores" / "salida_pruebas.log").read_text(encoding="utf-8")
    sql = (RAIZ / "insertUnderlineTickets.sql").read_text(encoding="utf-8")  # releer (nuevo timestamp)

    n_lineas = sum(1 for l in sql.splitlines() if re.match(r"^\s+\('\d{8}', \d+, \d+,", l))

    manual = f"""
<p class="small">Cabecera: <code>Fecha 12/09/2025 18:26</code>, <code>Cajero 033 - Laura García</code>, <code>Ticket 20010002</code>.
Pago en EFECTIVO (sin autorización).</p>
<pre class="code sql">{resaltar_sql(chr(10).join([
"-- sucursal y metodo_pago: ya existen (id 1 y 2), no se repiten",
"-- empleado 033 Laura García: se inserta solo la primera vez que aparece",
"INSERT INTO empleado (codigo_empleado, nombre) VALUES ('033', 'Laura García');",
"",
"-- ticket (cabecera)",
"INSERT INTO ticket (numero_ticket, fecha, hora, id_sucursal, codigo_empleado,",
"                    subtotal, porcentaje_iva, iva, total) VALUES",
"    " + filas_002[0].rstrip(',') + ";",
"",
"-- ticket_linea: una fila por producto (id_producto del catálogo, sin duplicar)",
"INSERT INTO ticket_linea (numero_ticket, num_linea, id_producto, cantidad,",
"                          precio_unitario, importe) VALUES",
*["    " + f for f in filas_002[1:-1]],
"",
"-- pago",
"INSERT INTO pago (id_pago, numero_ticket, id_metodo_pago, importe, autorizacion) VALUES",
"    " + filas_002[-1].rstrip(',') + ";",
]).replace("),\n\n-- pago", ");\n\n-- pago"))}</pre>"""

    html_doc = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Documento · Facturas a SQL</title>
<style>
@page {{ size: A4; margin: 14mm 15mm 16mm; }}
:root {{ --navy:#1f3a5f; --blue:#2f6db3; --soft:#eef3fa; --ink:#1d2733; --mut:#5a6878; --red:#b33a3a; --green:#2e8b57; }}
* {{ box-sizing: border-box; }}
body {{ font-family: "Segoe UI", Arial, sans-serif; color: var(--ink); font-size: 10.5pt; line-height: 1.45; margin: 0; background:#fff; }}
h1 {{ font-size: 24pt; margin: 0 0 4px; color:#fff; }}
h2 {{ font-size: 14.5pt; color: var(--navy); border-bottom: 2px solid var(--blue); padding-bottom: 4px; margin: 22px 0 10px; break-after: avoid; }}
h2 .n {{ display:inline-block; background: var(--blue); color:#fff; font-size: 11pt; width: 24px; text-align:center; margin-right:8px; border-radius:3px; }}
h3 {{ font-size: 11.5pt; color: var(--blue); margin: 14px 0 6px; break-after: avoid; }}
p {{ margin: 6px 0; }}
.small {{ font-size: 9.5pt; color: var(--mut); }}
.portada {{ background: var(--navy); color:#fff; padding: 22px 26px; border-radius: 4px; border-bottom: 5px solid var(--blue); }}
.portada .kicker {{ font-size: 9pt; font-weight:700; letter-spacing:.06em; color:#a9c6ea; }}
.portada .sub {{ color:#d6e2f2; font-size: 11pt; }}
.meta {{ display:flex; gap:8px; margin: 10px 0 4px; }}
.meta div {{ flex:1; background: var(--soft); padding: 8px 10px; border-radius: 3px; text-align:center; }}
.meta b {{ display:block; font-size: 16pt; color: var(--blue); }}
.meta span {{ font-size: 8.5pt; color: var(--mut); }}
table {{ border-collapse: collapse; width: 100%; font-size: 9.5pt; margin: 6px 0; break-inside: avoid; }}
th {{ background: var(--navy); color:#fff; text-align:left; padding: 6px 8px; }}
td {{ padding: 5px 8px; border-bottom: 1px solid #dde4ee; vertical-align: top; }}
tr:nth-child(even) td {{ background: #f6f9fc; }}
code {{ font-family: Consolas, monospace; font-size: 9pt; background: var(--soft); padding: 0 3px; border-radius: 2px; }}
pre {{ font-family: Consolas, monospace; font-size: 8.2pt; line-height: 1.38; margin: 6px 0; white-space: pre-wrap; word-break: break-word; }}
pre.code {{ background: #f6f8fb; border: 1px solid #dde4ee; border-left: 4px solid var(--blue); padding: 8px 10px; }}
pre.ticket {{ background:#fffdf6; border:1px dashed #c9b98a; padding: 8px 8px; font-size: 7.1pt; white-space: pre; overflow: hidden; }}
.duo pre.code {{ font-size: 7.4pt; }}
.sql .k {{ color:#7a2ea8; font-weight:700; }} .sql .s {{ color:#1a7f37; }} .sql .c {{ color:#7b8794; font-style: italic; }}
.duo {{ display:grid; grid-template-columns: 0.82fr 1.18fr; gap: 12px; align-items:start; break-inside: avoid; }}
.figura {{ break-inside: avoid; margin: 8px 0; }}
.figura img {{ width:100%; border:1px solid #dde4ee; border-radius:3px; }}
.figura .cap {{ font-size: 8.5pt; color: var(--mut); text-align:center; margin-top: 3px; }}
.flow {{ display:flex; gap:6px; margin: 8px 0; break-inside: avoid; }}
.flow div {{ flex:1; color:#fff; padding: 8px; border-radius: 3px; font-size: 9pt; text-align:center; }}
.flow b {{ display:block; font-size: 10pt; }}
.box {{ background: var(--soft); border-left: 4px solid var(--blue); padding: 8px 12px; margin: 8px 0; break-inside: avoid; }}
.box.warn {{ background:#fff7e6; border-color:#d99a00; }}
.term {{ background:#012456; border-radius: 6px; overflow:hidden; margin: 8px 0; break-inside: avoid; box-shadow: 0 1px 3px rgba(0,0,0,.25); }}
.term-bar {{ background:#e9edf2; padding: 5px 10px; font-size: 8.5pt; color:#333; display:flex; gap:5px; align-items:center; }}
.term-bar span {{ width:9px; height:9px; border-radius:50%; background:#c4cbd4; display:inline-block; }}
.term-bar b {{ margin-left: 8px; font-weight:600; }}
.term pre {{ color:#eeedf0; padding: 8px 12px; margin:0; font-size: 8pt; }}
.term .ps {{ color:#f0e68c; }} .term .err {{ color:#ff8b8b; }} .term .ok {{ color:#8fe3a8; }}
.pb {{ break-before: page; }}
.fn td:first-child {{ font-family: Consolas, monospace; white-space: nowrap; color: var(--navy); font-weight: 600; }}
</style></head><body>

<div class="portada">
  <div class="kicker">{e(ASIGNATURA.upper())}</div>
  <h1>De tickets .txt a SQL</h1>
  <div class="sub">Documentación del script <b>build_insert_from_tickets.py</b> · Alumno/a: {e(NOMBRE)}</div>
</div>

<div class="meta">
  <div><b>20</b><span>facturas .txt procesadas</span></div>
  <div><b>7</b><span>tablas (6 mínimas + 1 extra)</span></div>
  <div><b>{n_lineas}</b><span>líneas de ticket insertadas</span></div>
  <div><b>8</b><span>validaciones implementadas</span></div>
  <div><b>+1</b><span>log de errores (extra)</span></div>
</div>

<h2><span class="n">1</span>Objetivo</h2>
<p>El objetivo es automatizar la carga de 20 tickets de supermercado en una base de datos relacional. El script
<code>build_insert_from_tickets.py</code> lee todos los <code>.txt</code> de una carpeta, extrae sus datos (tienda,
fecha, cajero, número de ticket, productos, subtotal, IVA, total y forma de pago), los valida y genera
<code>insertUnderlineTickets.sql</code>, un script listo para importar en un gestor de bases de datos. Sin insertar dos veces el mismo cajero ni el mismo producto,
y dejando en un log las facturas que no se han podido procesar y el motivo.</p>
<div class="box"><b>Ejecución:</b> <code>python build_insert_from_tickets.py facturas/</code><br>
<span class="small">Opciones: <code>-o</code> archivo SQL de salida · <code>--log</code> archivo de log ·
<code>--estricto</code> no generar el SQL si hay errores · <code>--solo-inserts</code> sin CREATE TABLE.
Requiere Python 3.10 o superior; solo usa la biblioteca estándar.</span></div>

<h2><span class="n">2</span>Entregables</h2>
<table>
<tr><th style="width:34%">Archivo</th><th>Contenido</th></tr>
<tr><td><code>facturas/</code></td><td>Las 20 facturas originales (<code>factura_001.txt</code> … <code>factura_020.txt</code>).</td></tr>
<tr><td><code>build_insert_from_tickets.py</code></td><td>Script en Python (solo biblioteca estándar, sin dependencias externas).</td></tr>
<tr><td><code>insertUnderlineTickets.sql</code></td><td>Script generado: <code>CREATE TABLE</code> + <code>INSERT</code> de las 7 tablas dentro de una transacción.</td></tr>
<tr><td><code>errores_tickets.log</code></td><td>Log de facturas no procesadas y su motivo (extra para el 10).</td></tr>
<tr><td><code>diagrama/diagrama_bd.png / .pdf</code></td><td>Diagrama entidad-relación del modelo.</td></tr>
<tr><td><code>pruebas_errores/</code></td><td>Las 20 facturas + 8 de prueba (7 con errores provocados y 1 con un producto escrito en mayúsculas), para demostrar las validaciones.</td></tr>
</table>

<h2 class="pb"><span class="n">3</span>Modelo de base de datos</h2>
<p>Analizando los tickets se identifican las entidades que se repiten entre facturas (tienda, cajero, producto,
forma de pago) y las que son propias de cada factura (cabecera, líneas y pago). Las primeras se separan en tablas de
catálogo para no guardar el mismo dato varias veces (normalización), y las segundas las referencian mediante claves foráneas.</p>
<div class="figura"><img src="../diagrama/diagrama_bd.png" alt="Diagrama entidad-relación"><div class="cap">Figura 1 · Diagrama entidad-relación (notación pata de gallo)</div></div>

<table style="break-inside:auto">
<tr><th style="width:17%">Tabla</th><th style="width:28%">Clave</th><th>Decisión de diseño</th></tr>
<tr><td><b>sucursal</b></td><td>PK <code>id_sucursal</code> · UQ <code>cif</code></td><td>Datos de la cabecera del ticket. El CIF identifica la tienda y es único; la dirección se separa en dirección y ciudad.</td></tr>
<tr><td><b>empleado</b></td><td>PK <code>codigo_empleado</code></td><td>Se usa el código del cajero que ya trae el ticket (clave natural), así no puede repetirse.</td></tr>
<tr><td><b>producto</b></td><td>PK <code>id_producto</code> · UQ <code>descripcion</code></td><td>Catálogo sin descripciones repetidas. <code>unidad_medida</code> distingue productos a granel (kg) de unidades.</td></tr>
<tr><td><b>ticket</b></td><td>PK <code>numero_ticket</code> · FK sucursal, empleado</td><td>Cabecera: fecha, hora, subtotal, % de IVA, IVA y total.</td></tr>
<tr><td><b>ticket_linea</b></td><td>PK (<code>numero_ticket</code>, <code>num_linea</code>) · FK producto</td><td>Una fila por producto comprado. Guarda cantidad (<code>DECIMAL(10,3)</code> por los kg), precio unitario e importe.
El precio va en la línea y no en el producto porque puede cambiar entre tickets (en los productos a granel varía un céntimo por redondeo).</td></tr>
<tr><td><b>pago</b></td><td>PK <code>id_pago</code> · UQ <code>numero_ticket</code></td><td>Importe pagado y nº de autorización (solo con tarjeta; <code>NULL</code> en efectivo). Relación 1:1 con ticket.</td></tr>
<tr><td><b>metodo_pago</b> <span class="small">(extra)</span></td><td>PK <code>id_metodo_pago</code> · UQ <code>nombre</code></td><td>Tabla añadida: TARJETA / EFECTIVO se guardan una sola vez en lugar de repetirse como texto en cada pago.</td></tr>
</table>

<h2><span class="n">4</span>Paso de una factura a SQL (a mano)</h2>
<p>Antes de programar se tradujo una factura a mano para entender qué dato va a cada tabla. Ejemplo con <code>factura_002.txt</code>:</p>
<div class="duo">
<pre class="ticket">{e(factura)}</pre>
<div>{manual}</div>
</div>
<p class="small">El precio unitario no viene en el ticket: se calcula como importe ÷ cantidad (p. ej. 0.62 € ÷ 0.500 kg = 1.24 €/kg).</p>

<h2><span class="n">5</span>Lógica del programa</h2>
<div class="flow">
  <div style="background:#1f3a5f"><b>ENTRADA</b>facturas/*.txt</div>
  <div style="background:#2f6db3"><b>EXTRAER</b>parse_ticket()</div>
  <div style="background:#2f6db3"><b>TRANSFORMAR</b>validar + Catalogo</div>
  <div style="background:#2e8b57"><b>CARGAR</b>.sql + .log</div>
</div>
<h3>Extraer: lectura línea por línea con una máquina de estados</h3>
<p>Cada factura se lee línea por línea. El programa lleva un <b>estado</b> que indica en qué parte del ticket está, y
<b>cada raya separadora <code>------</code> lo hace avanzar</b> a la sección siguiente:</p>
<p style="text-align:center"><code>CABECERA</code> → <code>DATOS</code> → <code>ENCABEZADO_LINEAS</code> → <code>LINEAS</code> → <code>TOTALES</code> → <code>PAGO</code> → <code>PIE</code></p>
<p>En cada estado solo se aceptan las líneas que tocan, reconocidas con <b>expresiones regulares</b>
(p. ej. <code>^Cajero:\\s*(?P&lt;codigo&gt;\\d+)\\s*-\\s*(?P&lt;nombre&gt;.+)</code>). Una línea inesperada se rechaza
indicando su número. La cantidad de cada producto se captura como texto para poder comprobar después si es numérica y dar un mensaje claro.</p>

<h3>Transformar: validación y control de duplicados</h3>
<p>La clase <code>Catalogo</code> acumula las entidades únicas usando diccionarios: cajeros por código, productos por
descripción normalizada (sin distinguir mayúsculas ni espacios), sucursales por CIF y tickets por número. Si un dato ya
existe se <b>reutiliza su id</b> en lugar de insertarlo otra vez. Una factura con errores se rechaza <b>entera</b>
(no se carga nada de ella) y el programa continúa con las demás.</p>

<h3>Cargar: generación del SQL y del log</h3>
<p>Se escriben primero los <code>CREATE TABLE</code> y después los <code>INSERT</code> en orden de dependencias
(primero las tablas referenciadas). Para optimizar, cada tabla usa <b>un único INSERT con varias filas</b> y todo va dentro
de <code>BEGIN; … COMMIT;</code>. Los textos se escapan (<code>'</code> → <code>''</code>) y los importes usan
<code>Decimal</code> para evitar errores de redondeo de los <code>float</code>.</p>

<table class="fn">
<tr><th style="width:32%">Función</th><th>Qué hace</th></tr>
<tr><td>main()</td><td>Lee los argumentos (<code>carpeta</code>, <code>-o</code>, <code>--log</code>, <code>--estricto</code>, <code>--solo-inserts</code>) y controla los errores fatales.</td></tr>
<tr><td>generar_sql_para_carpeta()</td><td>Proceso completo: procesa la carpeta, escribe el .sql y el log, muestra el resumen y devuelve el código de salida.</td></tr>
<tr><td>procesar_carpeta()</td><td>Recorre los .txt en orden, llama a <code>parse_ticket()</code> y al catálogo, y separa facturas válidas y rechazadas.</td></tr>
<tr><td>parse_ticket()</td><td>Máquina de estados que extrae los datos de una factura.</td></tr>
<tr><td>validar_ticket()</td><td>Comprueba que no falten datos y que los importes cuadren.</td></tr>
<tr><td>Catalogo.comprobar_conflictos() / agregar()</td><td>Detecta duplicados contra lo ya cargado y registra las entidades nuevas sin repetir.</td></tr>
<tr><td>generar_sql() / insert_multifila()</td><td>Construyen el texto del script SQL.</td></tr>
<tr><td>escribir_log()</td><td>Escribe el log con las facturas rechazadas, los avisos y los duplicados evitados.</td></tr>
</table>

<h2 class="pb"><span class="n">6</span>Validaciones aplicadas</h2>
<table>
<tr><th style="width:27%">Validación</th><th style="width:38%">Cómo se detecta</th><th>Resultado</th></tr>
<tr><td><b>Archivo vacío</b></td><td>Ninguna línea con contenido.</td><td>Se rechaza: «archivo vacío».</td></tr>
<tr><td><b>Formato incorrecto</b></td><td>Línea no reconocida en su sección, o faltan datos obligatorios (fecha, cajero, nº ticket, totales, forma de pago, líneas).</td><td>Se rechaza indicando la línea o los datos que faltan.</td></tr>
<tr><td><b>Cantidad no numérica</b></td><td>La cantidad no cumple <code>^\\d+([.,]\\d+)?$</code> o es ≤ 0.</td><td>Se rechaza: «la cantidad 'tres' del producto … no es numérica».</td></tr>
<tr><td><b>Cajero repetido</b></td><td>Diccionario por código. Mismo código y nombre → se reutiliza. Mismo código con otro nombre → conflicto.</td><td>Sin duplicados en <code>empleado</code>; el conflicto se rechaza.</td></tr>
<tr><td><b>Producto duplicado</b></td><td>Descripción normalizada (minúsculas y espacios): «CAFÉ&nbsp; MOLIDO 250G» = «Café Molido 250g».</td><td>Se reutiliza el <code>id_producto</code> existente.</td></tr>
<tr><td><b>Ticket repetido</b></td><td>Número de ticket ya cargado.</td><td>Se rechaza indicando en qué archivo estaba.</td></tr>
<tr><td><b>Importes que no cuadran</b></td><td>Suma de líneas ≠ subtotal, IVA ≠ % del subtotal o subtotal + IVA ≠ total (tolerancia 0.01 €).</td><td>Se rechaza mostrando ambos valores.</td></tr>
<tr><td><b>Fecha imposible</b></td><td><code>datetime.strptime</code> falla (p. ej. 31/02/2025).</td><td>Se rechaza indicando la línea.</td></tr>
</table>

<div class="box warn"><b>Facturas con errores: dos modos.</b> El enunciado pide no generar el SQL si hay errores, y el extra pide
un log con las facturas que no se pudieron procesar. Por eso hay dos modos:
<b>por defecto</b> se descartan las facturas con errores (quedan en el log) y se genera el SQL con las válidas;
con <code>--estricto</code>, si hay cualquier error <b>no se genera el SQL</b>.
Códigos de salida: <code>0</code> todo correcto · <code>1</code> hubo facturas rechazadas · <code>2</code> no se generó el SQL.</div>

<h2><span class="n">7</span>Ejecución del script</h2>
<h3>7.1 Con las 20 facturas del examen</h3>
{terminal(*run_ok)}
<h3>7.2 Con las facturas de prueba (las 20 originales + 7 con errores provocados + 1 caso de duplicado)</h3>
{terminal(*run_err)}
<p class="small">La factura <code>factura_907_ok_producto_en_mayusculas.txt</code> sí se procesa: su producto «CAFÉ&nbsp; MOLIDO 250G»
se reconoce como el ya existente y el catálogo sigue teniendo 20 productos.</p>

<h3>7.3 Log generado (extra para el 10)</h3>
<pre class="code">{e(log_err)}</pre>

<h2 class="pb"><span class="n">8</span>Vista parcial de insertUnderlineTickets.sql</h2>
<pre class="code sql">{resaltar_sql(extracto_sql(sql))}</pre>
<p class="small">El script se ha importado en SQLite con las claves foráneas activadas: se cargan 1 sucursal, 7 empleados, 20 productos,
2 métodos de pago, 20 tickets, {n_lineas} líneas y 20 pagos, sin ninguna violación de integridad. Las sentencias usan SQL estándar
(compatible con MySQL/MariaDB, PostgreSQL y SQLite).</p>

</body></html>"""
    (DOC / "documento.html").write_text(html_doc, encoding="utf-8")
    print("documento.html generado")


if __name__ == "__main__":
    main()
