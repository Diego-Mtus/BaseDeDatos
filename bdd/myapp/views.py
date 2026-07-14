from django.apps import apps
from django.contrib import messages
from django.db import transaction, connection
from django.core import signing
from django.db.models import Max, Sum
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from datetime import date, datetime, timedelta
from django.db import IntegrityError
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from .forms import AbonoCreditoForm, ClienteCreateForm, PedidoCreateForm, PedidoLineaFormSet, ProductoForm, LlegadaStockForm
from .models import (
    AbonoCredito,
    Cliente,
    ClienteEmpresa,
    ClientePersona,
    DocumentoTributario,
    EstadoCredito,
    Pedido,
    PedidoContieneProducto,
    Producto,
    ProveedorSuministraProducto,
    BodegaAlmacenaProducto,
    Proveedor
)


PK_TOKEN_SALT = "myapp.model-browser"


def proveedor_detail(request, rut):
    proveedor = get_object_or_404(Proveedor, rut=rut)
    # Aquí puedes agregar lógica adicional, como listar sus productos suministrados
    return render(request, "proveedor_detail.html", {"proveedor": proveedor})

def _cliente_nombre(cliente):
    try:
        persona = cliente.clientepersona
    except ObjectDoesNotExist:
        persona = None
    if persona:
        return f"{persona.nombre} {persona.apellido}"
    try:
        empresa = cliente.clienteempresa
    except ObjectDoesNotExist:
        empresa = None
    if empresa:
        return empresa.razon_social
    return cliente.rut


def _cliente_etiqueta(cliente):
    return f"{_cliente_nombre(cliente)} ({cliente.rut})"


def _cliente_estado_financiero(cliente, today=None):
    today = today or date.today()
    saldo = cliente.saldo_deudor or 0
    limite = cliente.limite_credito or 0
    fecha_limite = cliente.fecha_limite

    # 1. Si el cliente tiene un estado explícito de 'Bloqueado' (ej: por administración)
    if cliente.id_estado and cliente.id_estado.nombre_estado.lower() == "bloqueado":
        return "Bloqueado"

    # 2. Si el saldo deudor sobrepasa el límite de crédito autorizado, se Bloquea automáticamente
    if limite > 0 and saldo > limite:
        return "Bloqueado"

    # 3. LÓGICA INTERNA: Cerca del límite por muchos días
    # Definimos que estar "cerca del límite" es haber usado el 90% o más del cupo
    if limite > 0 and saldo >= (limite * 0.90):
        # Asumiendo que guardas la fecha de cuándo empezó la deuda o cuándo se modificó el saldo,
        # o usando la 'fecha_limite' como indicador de antigüedad de la cuenta corriente.
        # Por ejemplo, si pasaron más de 15 días desde que se le otorgó/venció el crédito:
        if fecha_limite:
            dias_antiguedad = (today - fecha_limite).days
            # Si lleva más de 7 días en esta situación de riesgo, pasa a Moroso de forma preventiva
            if dias_antiguedad > 7:
                return "Moroso"

    # 4. Si la fecha límite de pago estándar ya pasó y el cliente aún tiene deuda
    if saldo > 0 and fecha_limite and fecha_limite < today:
        return "Moroso"

    # 5. En cualquier otro caso, está Vigente
    return "Vigente"


def _cliente_resumen(cliente, today=None):
    today = today or date.today()
    estado_financiero = _cliente_estado_financiero(cliente, today=today)
    try:
        tipo = "Empresa" if cliente.clienteempresa else "Persona"
    except ObjectDoesNotExist:
        tipo = "Persona"
        
    # Identificar de forma auxiliar si está cerca del límite (90% o más consumido)
    saldo = cliente.saldo_deudor or 0
    limite = cliente.limite_credito or 0
    esta_cerca = False
    if limite > 0 and saldo >= (limite * 0.90) and saldo <= limite:
        esta_cerca = True

    return {
        "obj": cliente,
        "nombre": _cliente_nombre(cliente),
        "tipo": tipo,
        "estado_financiero": estado_financiero,
        "esta_cerca_limite": esta_cerca, # <-- Guardamos este indicador clave
        "dias_vencido": (today - cliente.fecha_limite).days if cliente.fecha_limite and cliente.fecha_limite < today else 0,
        "saldo_restante": (cliente.limite_credito or 0) - (cliente.saldo_deudor or 0),
    }

def _cliente_queryset():
    return Cliente.objects.select_related("id_estado").all().order_by("rut")


def _pedido_queryset():
    return Pedido.objects.select_related("rut_cliente", "id_empleado").all().order_by("-fecha_de_emision")


def _abono_queryset():
    return AbonoCredito.objects.select_related("rut_cliente", "id_empleado").all().order_by("-fecha")


def _pedido_summary(pedido):
    lineas = PedidoContieneProducto.objects.select_related("sku").filter(id_pedido=pedido)
    total_lineas = sum((linea.cantidad for linea in lineas), Decimal("0"))
    return {
        "obj": pedido,
        "cliente_nombre": _cliente_nombre(pedido.rut_cliente),
        "cliente_etiqueta": _cliente_etiqueta(pedido.rut_cliente),
        "pedido_etiqueta": _pedido_etiqueta(pedido),
        "es_credito": "Sí" if pedido.es_credito else "No",
        "estado_label": _pedido_estado_label(pedido.estado),
        "fecha_estimada": _pedido_fecha_estimada(pedido),
        "lineas": lineas,
        "total_unidades": total_lineas,
    }


def _abono_summary(abono):
    return {
        "obj": abono,
        "cliente_nombre": _cliente_nombre(abono.rut_cliente),
        "cliente_etiqueta": _cliente_etiqueta(abono.rut_cliente),
        "empleado_etiqueta": f"{abono.id_empleado.nombre} {abono.id_empleado.apellido} (ID {abono.id_empleado.id_empleado})",
        "monto": abono.monto,
        "fecha": abono.fecha,
        "id_empleado": abono.id_empleado,
    }


def _pedido_etiqueta(pedido):
    return f"{_cliente_nombre(pedido.rut_cliente)} ({pedido.rut_cliente.rut})"


def _pedido_estado_label(estado):
    # Convertimos a minúsculas y eliminamos espacios extra
    estado_lower = (estado or "").strip().lower()
    
    if estado_lower == "aprobado":
        return "Aprobado"
    if estado_lower == "pendiente":
        return "Pendiente"
    if estado_lower == "rechazado":
        return "Rechazado"
    if estado_lower == "terminado":
        return "Terminado"
        
    return "En proceso"


def _pedido_fecha_estimada(pedido):
    return pedido.fecha_de_emision + timedelta(days=2)


def _producto_stock_summary(producto):
    almacenamiento = BodegaAlmacenaProducto.objects.filter(sku=producto).first()
    lote_proveedor = ProveedorSuministraProducto.objects.select_related("rut_proveedor") \
        .filter(sku_producto=producto).order_by("-fecha").first()
    
    today = date.today()
    start_month = today.replace(day=1)
    vendido_mes = (
        PedidoContieneProducto.objects.filter(
            sku=producto,
            id_pedido__fecha_de_emision__date__gte=start_month,
            id_pedido__fecha_de_emision__date__lte=today,
        ).aggregate(total=Sum("cantidad")).get("total") or 0
    )
    
    # Preparamos los datos
    ubicacion = f"{almacenamiento.nombre_bodega} ({almacenamiento.ubicacion_bodega})" if almacenamiento else "No en bodega"
    proveedor = lote_proveedor.rut_proveedor.nombre if lote_proveedor else "Sin proveedor"
    
    return {
        "ubicacion": ubicacion,
        "proveedor": proveedor,
        # Clave 'origen' necesaria para tu lógica de conteo en productos_list
        "origen": f"{almacenamiento.nombre_bodega}" if almacenamiento else "Sin origen registrado",
        "stock_total": almacenamiento.cantidad if almacenamiento else 0,
        "vendido_mes": vendido_mes,
        "stock_disponible": (almacenamiento.cantidad if almacenamiento else 0) - vendido_mes,
        "fecha_vencimiento_cercana": lote_proveedor.fecha_vencimiento_lote if lote_proveedor else None,
    }

def _pedido_detalle(pedido):
    lineas = PedidoContieneProducto.objects.select_related("sku").filter(id_pedido=pedido)
    documento = DocumentoTributario.objects.select_related("id_empleado").filter(id_pedido=pedido).first()
    return {
        "obj": pedido,
        "cliente_nombre": _cliente_nombre(pedido.rut_cliente),
        "cliente_etiqueta": _cliente_etiqueta(pedido.rut_cliente),
        "pedido_etiqueta": _pedido_etiqueta(pedido),
        "estado_label": _pedido_estado_label(pedido.estado),
        "fecha_estimada": _pedido_fecha_estimada(pedido),
        "lineas": lineas,
        "documento": documento,
    }


def _dashboard_context():
    today = date.today()
    clientes = list(_cliente_queryset())
    pedidos = list(_pedido_queryset())
    abonos = list(_abono_queryset())
    cliente_resumenes = [_cliente_resumen(cliente, today=today) for cliente in clientes]
    
    morosos = [item for item in cliente_resumenes if item["estado_financiero"] == "Moroso"]
    bloqueados = [item for item in cliente_resumenes if item["estado_financiero"] == "Bloqueado"]
    
    # NUEVO: Filtramos los clientes cerca del límite para el dashboard
    cerca = [item for item in cliente_resumenes if item["esta_cerca_limite"] and item["estado_financiero"] not in ["Bloqueado", "Moroso"]]
    
    total_deuda = sum((cliente.saldo_deudor or 0) for cliente in clientes)
    total_limite = sum((cliente.limite_credito or 0) for cliente in clientes)
    total_pagado = sum((abono.monto or 0) for abono in abonos)
    return {
        "total_clientes": len(clientes),
        "total_pedidos": len(pedidos),
        "total_abonos": len(abonos),
        "total_deuda": total_deuda,
        "total_limite": total_limite,
        "total_pagado": total_pagado,
        "vencidos": morosos[:5],        
        "excedidos": bloqueados[:5],    
        "cerca_limite": cerca[:5],      # <-- PASAMOS LOS PRIMEROS 5 A LA PLANTILLA
        "recent_pedidos": [_pedido_summary(pedido) for pedido in pedidos[:5]],
        "recent_abonos": [_abono_summary(abono) for abono in abonos[:5]],
    }

def _estado_credito_inicial():
    estado = EstadoCredito.objects.filter(nombre_estado__iexact="Activo").first()
    if estado:
        return estado
    estado = EstadoCredito.objects.order_by("id_estado").first()
    if not estado:
        raise Http404("No existe un estado de crédito para asignar al cliente.")
    return estado


def _normalize_token_value(value):
    if isinstance(value, tuple):
        return {
            "__type__": "tuple",
            "items": [_normalize_token_value(item) for item in value],
        }
    if isinstance(value, list):
        return {
            "__type__": "list",
            "items": [_normalize_token_value(item) for item in value],
        }
    if isinstance(value, dict):
        return {
            "__type__": "dict",
            "items": {
                key: _normalize_token_value(item)
                for key, item in value.items()
            },
        }
    if isinstance(value, datetime):
        return {"__type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__type__": "date", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"__type__": "decimal", "value": str(value)}
    if isinstance(value, UUID):
        return {"__type__": "uuid", "value": str(value)}
    return value


def _restore_token_value(value):
    if isinstance(value, dict) and "__type__" in value:
        value_type = value["__type__"]
        if value_type == "tuple":
            return tuple(_restore_token_value(item) for item in value["items"])
        if value_type == "list":
            return [_restore_token_value(item) for item in value["items"]]
        if value_type == "dict":
            return {
                key: _restore_token_value(item)
                for key, item in value["items"].items()
            }
        if value_type == "datetime":
            return datetime.fromisoformat(value["value"])
        if value_type == "date":
            return date.fromisoformat(value["value"])
        if value_type == "decimal":
            return Decimal(value["value"])
        if value_type == "uuid":
            return UUID(value["value"])
    return value


def _get_browseable_model(model_name):
    try:
        return apps.get_model("myapp", model_name)
    except LookupError as exc:
        raise Http404("Model not found") from exc


def _encode_pk(pk_value):
    return signing.dumps(_normalize_token_value(pk_value), salt=PK_TOKEN_SALT)


def _decode_pk(token):
    return _restore_token_value(signing.loads(token, salt=PK_TOKEN_SALT))


def _model_fields(model):
    return [field for field in model._meta.concrete_fields]


def _model_rows(model):
    rows = []
    fields = _model_fields(model)
    for obj in model._default_manager.all():
        rows.append(
            {
                "object": obj,
                "token": _encode_pk(obj.pk),
                "values": [field.value_from_object(obj) for field in fields],
            }
        )
    return fields, rows


def home(request):
    return render(
        request,
        "dashboard.html",
        _dashboard_context(),
    )


def clientes_list(request):
    today = date.today()
    
    # 1. Capturar parámetros de la barra de filtros
    q_search = request.GET.get('q', '').strip()
    q_estado = request.GET.get('estado', '').strip()
    q_orden = request.GET.get('orden', 'nombre_asc')  # Por defecto

    # 2. Obtener todos los clientes base usando la optimización que ya tienes
    clientes_qs = _cliente_queryset()
    
    # Aplicar filtro de texto (Nombre detallado o RUT)
    # Como la consulta base trae objetos 'Cliente', primero preparamos sus resúmenes 
    # para poder evaluar los estados financieros calculados dinámicamente y los nombres.
    clientes_completos = []
    for cliente in clientes_qs:
        resumen = _cliente_resumen(cliente, today=today)
        
        # Filtrado por búsqueda de texto (RUT o Nombre calculado)
        if q_search:
            search_lower = q_search.lower()
            if search_lower not in resumen["nombre"].lower() and search_lower not in cliente.rut.lower():
                continue  # No calza con la búsqueda, saltar
                
        # Filtrado por Estado Financiero (Vigente, Moroso, Bloqueado)
        if q_estado:
            if resumen["estado_financiero"].lower() != q_estado.lower():
                continue  # No calza con el estado seleccionado, saltar
                
        clientes_completos.append(resumen)

    # 3. Aplicar Ordenamiento sobre la lista de Python
    if q_orden == 'saldo_desc':
        clientes_completos.sort(key=lambda x: x["obj"].saldo_deudor or 0, reverse=True)
    elif q_orden == 'saldo_asc':
        clientes_completos.sort(key=lambda x: x["obj"].saldo_deudor or 0)
    elif q_orden == 'nombre_desc':
        clientes_completos.sort(key=lambda x: x["nombre"], reverse=True)
    else:  # 'nombre_asc'
        clientes_completos.sort(key=lambda x: x["nombre"])

    return render(
        request,
        "clientes_list.html",
        {
            "clientes": clientes_completos,
            "today": today,
            "q_search": q_search,
            "q_estado": q_estado,
            "q_orden": q_orden,
        },
    )


def cliente_create(request):
    if request.method == "POST":
        form = ClienteCreateForm(request.POST)
        if form.is_valid():
            # El save() del formulario ahora guarda todo de forma atómica y segura en la BD
            cliente = form.save()
            messages.success(request, f"Cliente {cliente.rut} creado con éxito.")
            return redirect("clientes-list")
    else:
        form = ClienteCreateForm()

    return render(request, "cliente_form.html", {"form": form})

def cliente_detail(request, rut):
    cliente = get_object_or_404(Cliente.objects.select_related("id_estado"), pk=rut)
    today = date.today()
    pedidos = _pedido_queryset().filter(rut_cliente=cliente)
    abonos = _abono_queryset().filter(rut_cliente=cliente)
    try:
        persona = cliente.clientepersona
    except ObjectDoesNotExist:
        persona = None
    try:
        empresa = cliente.clienteempresa
    except ObjectDoesNotExist:
        empresa = None
    nombre = _cliente_nombre(cliente)
    resumen = _cliente_resumen(cliente, today=today)
    return render(
        request,
        "cliente_detail.html",
        {
            "cliente": cliente,
            "nombre": nombre,
            "persona": persona,
            "empresa": empresa,
            "resumen": resumen,
            "pedidos": [_pedido_summary(pedido) for pedido in pedidos],
            "abonos": abonos,
            "today": today,
        },
    )


def pedidos_list(request):
    pedidos = [_pedido_summary(pedido) for pedido in _pedido_queryset()]
    return render(
        request,
        "pedidos_list.html",
        {"pedidos": pedidos},
    )


def pedido_create(request):
    producto_precios = {producto.sku: int(producto.precio) for producto in Producto.objects.all()}
    if request.method == "POST":
        form = PedidoCreateForm(request.POST)
        formset = PedidoLineaFormSet(request.POST, prefix="lineas")
        if form.is_valid() and formset.is_valid():
            cliente = form.cleaned_data["rut_cliente"]
            empleado = form.cleaned_data["id_empleado"]
            es_credito = form.cleaned_data["es_credito"]
            estado = form.cleaned_data["estado"]

            lineas_validas = []
            total_decimal = Decimal("0")
            for line_form in formset:
                cleaned_data = getattr(line_form, "cleaned_data", {})
                sku = cleaned_data.get("sku")
                cantidad = cleaned_data.get("cantidad")
                if not sku and not cantidad:
                    continue
                subtotal = Decimal(str(sku.precio)) * cantidad
                total_decimal += subtotal
                lineas_validas.append((sku, cantidad))

            total_bruto = int(total_decimal.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            deuda_actual = cliente.saldo_deudor or 0
            if es_credito and cliente.limite_credito and (deuda_actual + total_bruto) > cliente.limite_credito:
                form.add_error(None, "El pedido supera el límite de crédito del cliente.")
            else:
                with transaction.atomic():
                    next_id = (Pedido.objects.aggregate(max_id=Max("id_pedido")).get("max_id") or 0) + 1
                    pedido = Pedido.objects.create(
                        id_pedido=next_id,
                        fecha_de_emision=datetime.now(),
                        estado=estado,
                        total_bruto=total_bruto,
                        es_credito=es_credito,
                        rut_cliente=cliente,
                        id_empleado=empleado,
                    )

                    for sku, cantidad in lineas_validas:
                        PedidoContieneProducto.objects.create(
                            id_pedido=pedido,
                            sku=sku,
                            cantidad=cantidad,
                        )

                    if es_credito:
                        cliente.saldo_deudor = deuda_actual + total_bruto
                        if not cliente.fecha_limite:
                            cliente.fecha_limite = date.today() + timedelta(days=30)
                        cliente.save(update_fields=["saldo_deudor", "fecha_limite"])

                messages.success(request, f"Pedido #{next_id} registrado correctamente.")
                return redirect("pedidos-list")
    else:
        form = PedidoCreateForm(initial={"estado": "En proceso"})
        formset = PedidoLineaFormSet(prefix="lineas")

    return render(
        request,
        "pedido_form.html",
        {
            "form": form,
            "formset": formset,
            "producto_precios": producto_precios,
        },
    )
def pedido_detail(request, id_pedido):
    pedido = get_object_or_404(Pedido.objects.select_related("rut_cliente", "id_empleado"), pk=id_pedido)
    return render(
        request,
        "pedido_detail.html",
        _pedido_detalle(pedido),
    )


def alertas_credito(request):
    today = date.today()
    clientes = [_cliente_resumen(cliente, today=today) for cliente in _cliente_queryset()]
    
    morosos = [item for item in clientes if item["estado_financiero"] == "Moroso"]
    bloqueados = [item for item in clientes if item["estado_financiero"] == "Bloqueado"]
    
    # NUEVO: Filtramos los que están cerca del límite y que no estén ya bloqueados/morosos
    cerca = [item for item in clientes if item["esta_cerca_limite"] and item["estado_financiero"] not in ["Bloqueado", "Moroso"]]
    
    return render(
        request,
        "alertas_credito.html",
        {
            "vencidos": morosos,       
            "excedidos": bloqueados,   
            "cerca_limite": cerca,      # <-- PASAMOS LA LISTA REAL A LA PLANTILLA
            "today": today,
        },
    )

def reportes(request):
    today = date.today()
    clientes = list(_cliente_queryset())
    pedidos = list(_pedido_queryset())
    abonos = list(_abono_queryset())
    creditos = [pedido for pedido in pedidos if pedido.es_credito]
    credito_total = sum((pedido.total_bruto or 0) for pedido in creditos)
    abonos_total = sum((abono.monto or 0) for abono in abonos)
    deuda_total = sum((cliente.saldo_deudor or 0) for cliente in clientes)
    return render(
        request,
        "reportes.html",
        {
            "today": today,
            "total_clientes": len(clientes),
            "total_pedidos": len(pedidos),
            "total_abonos": len(abonos),
            "credito_total": credito_total,
            "abonos_total": abonos_total,
            "deuda_total": deuda_total,
            "creditos": [_pedido_summary(pedido) for pedido in creditos[:10]],
            "abonos": [_abono_summary(abono) for abono in abonos[:10]],
        },
    )


def abonos_list(request):
    form = AbonoCreditoForm(request.POST or None)
    empleados = list(form.fields["id_empleado"].queryset)
    clientes = list(form.fields["rut_cliente"].queryset)
    saved = False
    created_abono = None

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            abono = form.save(commit=False)
            next_id = (AbonoCredito.objects.aggregate(max_id=Max("id_abono")).get("max_id") or 0) + 1
            abono.id_abono = next_id
            abono.fecha = datetime.now()
            abono.save()

            cliente = abono.rut_cliente
            cliente.saldo_deudor = max((cliente.saldo_deudor or 0) - (abono.monto or 0), 0)
            if cliente.saldo_deudor <= 0 and cliente.fecha_limite and cliente.fecha_limite < date.today():
                cliente.fecha_limite = date.today()
            cliente.save(update_fields=["saldo_deudor", "fecha_limite"])

            saved = True
            created_abono = abono
            form = AbonoCreditoForm()

    return render(
        request,
        "abonos.html",
        {
            "form": form,
            "abonos": [_abono_summary(abono) for abono in _abono_queryset()[:20]],
            "saved": saved,
            "created_abono": created_abono,
            "empleados": empleados,
            "clientes": clientes,
        },
    )


def model_list(request, model_name):
    model = _get_browseable_model(model_name)
    fields, rows = _model_rows(model)
    return render(
        request,
        "model_list.html",
        {
            "model_name": model._meta.model_name,
            "verbose_name": model._meta.verbose_name,
            "verbose_name_plural": model._meta.verbose_name_plural,
            "db_table": model._meta.db_table,
            "fields": fields,
            "rows": rows,
        },
    )


def model_detail(request, model_name, token):
    model = _get_browseable_model(model_name)
    pk_value = _decode_pk(token)
    obj = get_object_or_404(model, pk=pk_value)
    fields = _model_fields(model)
    values = [(field, field.value_from_object(obj)) for field in fields]
    return render(
        request,
        "model_detail.html",
        {
            "model_name": model._meta.model_name,
            "verbose_name": model._meta.verbose_name,
            "db_table": model._meta.db_table,
            "object": obj,
            "fields": fields,
            "values": values,
        },
    )


def productos_list(request):
    lotes_productos = []
    
    # 1. Capturar parámetros de filtrado desde la URL (request.GET)
    q_search = request.GET.get('q', '').strip()
    q_proveedor = request.GET.get('proveedor', '').strip()
    q_categoria = request.GET.get('categoria', '').strip() # <-- CAPTURAMOS LA CATEGORÍA
    q_orden = request.GET.get('orden', 'fecha_llegada_desc') # Criterio por defecto
    ocultar_agotados = request.GET.get('ocultar_agotados') == 'true' # <-- NUEVO

    # 2. Construir la consulta base de llegadas
    from django.db.models import F, Q
    llegadas_qs = ProveedorSuministraProducto.objects.select_related("sku_producto", "rut_proveedor").all()
    
    # Aplicar filtro de búsqueda por texto (Nombre del producto o SKU)
    if q_search:
        llegadas_qs = llegadas_qs.filter(
            Q(sku_producto__nombre__icontains=q_search) | 
            Q(sku_producto__sku__icontains=q_search)
        )
        
    # Aplicar filtro por Proveedor (RUT)
    if q_proveedor:
        llegadas_qs = llegadas_qs.filter(rut_proveedor__rut=q_proveedor)
        
    # Aplicar filtro por Categoría (id_categoria) si viene en los parámetros
    if q_categoria:
        llegadas_qs = llegadas_qs.filter(sku_producto__categorias__id_categoria=q_categoria)
        
    # Ordenamos internamente por vencimiento de forma estricta para que el FEFO consuma lo correcto
    llegadas = llegadas_qs.order_by(F("fecha_vencimiento_lote").asc(nulls_last=True), "fecha")
    
    # 3. Obtenemos las ventas consolidadas de este mes
    today = date.today()
    start_month = today.replace(day=1)
    
    ventas_qs = PedidoContieneProducto.objects.filter(
        id_pedido__fecha_de_emision__date__gte=start_month,
        id_pedido__fecha_de_emision__date__lte=today,
    ).values("sku").annotate(total=Sum("cantidad"))
    
    ventas_por_sku = {str(v["sku"]).strip(): (v["total"] or 0) for v in ventas_qs}

    # 4. Aplicamos el Algoritmo FEFO secuencial
    for llegada in llegadas:
        producto = llegada.sku_producto
        
        # Leemos la ubicación guardada directamente en el lote
        if llegada.nombre_bodega and llegada.ubicacion_bodega:
            ubicacion = f"{llegada.nombre_bodega} ({llegada.ubicacion_bodega})"
            origen = llegada.nombre_bodega
        else:
            ubicacion = "No asignado en bodega"
            origen = "Sin origen registrado"
        
        # ELIMINAMOS LA RESTA MATEMÁTICA DOBLE DE VENTAS.
        # El stock disponible es exactamente la cantidad que queda registrada en el lote de la base de datos.
        stock_disponible = llegada.cantidad or 0

        if ocultar_agotados and stock_disponible <= 0:
            continue  # Saltar este lote si está agotado y se pidió ocultarlos

        lotes_productos.append({
            "obj": producto,
            "ubicacion": ubicacion,
            "origen": origen,
            "proveedor": llegada.rut_proveedor, # El objeto completo que arreglamos antes
            "stock_total": llegada.cantidad or 0,
            "stock_disponible": stock_disponible,
            "fecha_vencimiento_cercana": llegada.fecha_vencimiento_lote,
            "fecha_llegada": llegada.fecha,
            "cantidad_lote": llegada.cantidad or 0,
        })
    
    # 5. ORDENAMIENTO DE CARA AL USUARIO (Python side)
    if q_orden == 'fecha_llegada_asc':
        lotes_productos.sort(key=lambda x: x["fecha_llegada"])
    elif q_orden == 'fecha_venc_asc':
        lotes_productos.sort(key=lambda x: x["fecha_vencimiento_cercana"] or date(9999, 12, 31))
    elif q_orden == 'fecha_venc_desc':
        lotes_productos.sort(key=lambda x: x["fecha_vencimiento_cercana"] or date(1900, 1, 1), reverse=True)
    else: 
        lotes_productos.sort(key=lambda x: x["fecha_llegada"], reverse=True)
    
    # Traer listas maestras para los select del HTML
    from .models import Proveedor, Categoria
    proveedores = Proveedor.objects.all().order_by('nombre')
    categorias = Categoria.objects.all().order_by('nombre') # <-- TRAEMOS LAS CATEGORÍAS
    
    total_productos = len(lotes_productos)
    con_stock = sum(1 for p in lotes_productos if p["stock_disponible"] > 0)
    sin_origen = sum(1 for p in lotes_productos if p["origen"] == "Sin origen registrado")
    
    return render(request, "producto_stock.html", {
        "productos": lotes_productos,
        "proveedores": proveedores,
        "categorias": categorias, # <-- PASAMOS LAS CATEGORÍAS AL CONTEXTO
        "total_productos": total_productos,
        "con_stock": con_stock,
        "sin_origen": sin_origen,
        "q_search": q_search,
        "q_proveedor": q_proveedor,
        "q_categoria": q_categoria, # <-- PASAMOS EL FILTRO ACTIVO
        "q_orden": q_orden,
        "ocultar_agotados": ocultar_agotados,
    })

def producto_create(request):
    # Capturamos de dónde viene el usuario para saber a dónde regresarlo
    origen = request.GET.get('from', 'stock')
    
    if request.method == "POST":
        form = ProductoForm(request.POST)
        if form.is_valid():
            # Guarda el producto y sus categorías (Relación Many-to-Many)
            producto = form.save() 
            
            messages.success(request, f"Producto '{producto.nombre}' registrado exitosamente en el catálogo maestro.")
            
            # Redirección dinámica según de dónde provino
            if origen == 'catalogo':
                return redirect("productos-catalogo")
            return redirect("stock-list")
    else:
        form = ProductoForm()
        
    return render(request, "producto_form.html", {"form": form, "mode": "create"})

def productos_detail(request, sku):
    producto = get_object_or_404(Producto, pk=sku)
    origen = request.GET.get('from', 'stock')
    
    if request.method == "POST":
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            producto = form.save()
            messages.success(request, f"Producto '{producto.nombre}' actualizado correctamente.")
            if origen == 'catalogo':
                return redirect("productos-catalogo")
            return redirect("stock-list")
    else:
        form = ProductoForm(instance=producto)
        
    # ELIMINADO: resumen = _producto_stock_summary(producto) <-- Ya no es necesario procesarlo
    
    return render(request, "producto_form.html", {
        "form": form, 
        "mode": "edit"
    })

@transaction.atomic
def ingresar_llegada_stock(request):
    if request.method == "POST":
        form = LlegadaStockForm(request.POST)
        if form.is_valid():
            producto = form.cleaned_data["producto"]
            proveedor = form.cleaned_data["proveedor"]
            cantidad = int(form.cleaned_data["cantidad"]) # Tu modelo usa IntegerField para cantidad
            fecha_llegada = form.cleaned_data["fecha_llegada"]
            fecha_venc = form.cleaned_data["fecha_vencimiento"]
            
            # SEPARACIÓN DE LA BODEGA COMPUESTA
            bodega_compuesta = form.cleaned_data["bodega"]  # String "nombre|ubicacion"
            nombre_b, ubicacion_b = bodega_compuesta.split('|')
            
            sku_str = producto.sku
            rut_str = proveedor.rut

            # 1. UPSERT DIRECTO EN BODEGA_ALMACENA_PRODUCTO
            # Si se topa con el unique_together, ejecuta la suma de la cantidad.
            with connection.cursor() as cursor:
                # 1. UPSERT en bodega_almacena_producto (Sigue igual)
                cursor.execute("""
                    INSERT INTO bodega_almacena_producto (nombre_bodega, ubicacion_bodega, sku, cantidad)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (nombre_bodega, ubicacion_bodega, sku) 
                    DO UPDATE SET cantidad = bodega_almacena_producto.cantidad + EXCLUDED.cantidad;
                """, [nombre_b, ubicacion_b, sku_str, cantidad])
                
                # 2. INSERT en proveedor_suministra_producto (¡NUEVO: Guardamos la bodega aquí también!)
                cursor.execute("""
                    INSERT INTO proveedor_suministra_producto (rut_proveedor, sku_producto, fecha, fecha_vencimiento_lote, cantidad, nombre_bodega, ubicacion_bodega)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (rut_proveedor, sku_producto, fecha)
                    DO UPDATE SET cantidad = proveedor_suministra_producto.cantidad + EXCLUDED.cantidad,
                                fecha_vencimiento_lote = EXCLUDED.fecha_vencimiento_lote,
                                nombre_bodega = EXCLUDED.nombre_bodega,
                                ubicacion_bodega = EXCLUDED.ubicacion_bodega;
                """, [rut_str, sku_str, fecha_llegada, fecha_venc, cantidad, nombre_b, ubicacion_b])
            
            messages.success(
                request, 
                f"Llegada de stock procesada con éxito. Se ingresaron {cantidad} unidades al catálogo."
            )
            return redirect("stock-list")
    else:
        form = LlegadaStockForm()
        
    return render(request, "llegada_stock_form.html", {"form": form})

def productos_catalogo_list(request):
    # 1. Obtener todos los productos registrados con sus categorías
    productos_qs = Producto.objects.prefetch_related('categorias').all().order_by('nombre')
    
    # 2. Capturar parámetros desde la URL
    q_search = request.GET.get('q', '').strip()
    q_categoria = request.GET.get('categoria', '').strip() # <-- CAPTURAMOS LA CATEGORÍA

    # Filtrado por texto (Nombre o SKU)
    if q_search:
        from django.db.models import Q
        productos_qs = productos_qs.filter(
            Q(nombre__icontains=q_search) | Q(sku__icontains=q_search)
        )
        
    # Filtrado por Categoría (NUEVO)
    if q_categoria:
        productos_qs = productos_qs.filter(categorias__id_categoria=q_categoria)
    
    # 3. Traer la lista maestra de categorías para el selector
    from .models import Categoria
    categorias = Categoria.objects.all().order_by('nombre')
        
    return render(request, 'productos_catalogo.html', {
        'productos': productos_qs,
        'categorias': categorias, # <-- ENVIAMOS LAS CATEGORÍAS
        'q_search': q_search,
        'q_categoria': q_categoria, # <-- ENVIAMOS EL FILTRO ACTIVO
    })

def procesar_ventas_del_dia(request):
    """Vista que lista los pedidos pendientes para que el usuario elija cuál aprobar."""
    pedidos = Pedido.objects.filter(estado="pendiente").prefetch_related(
        'pedidocontieneproducto_set__sku'
    )
    return render(request, "procesar_ventas.html", {"pedidos": pedidos})

@transaction.atomic
def aprobar_pedido(request, pedido_id):
    """Vista que procesa un solo pedido, descuenta stock FEFO de lotes y de su respectiva bodega."""
    if request.method == "POST":
        pedido = get_object_or_404(Pedido, pk=pedido_id)
        
        if pedido.estado == "aprobado":
            messages.warning(request, "Este pedido ya había sido procesado.")
            return redirect("procesar-ventas")

        lineas = pedido.pedidocontieneproducto_set.all()
        
        for linea in lineas:
            # Buscamos lotes con stock disponibles ordenados por FEFO
            lotes = ProveedorSuministraProducto.objects.filter(
                sku_producto=linea.sku, cantidad__gt=0
            ).order_by('fecha_vencimiento_lote')
            
            restante = linea.cantidad
            
            total_disponible = sum(l.cantidad for l in lotes)
            if total_disponible < restante:
                messages.error(request, f"Error: Stock insuficiente para {linea.sku.nombre}. Necesita {restante}, disponible {total_disponible}.")
                return redirect("procesar-ventas")

            # Aplicar descuento FEFO
            for lote in lotes:
                if restante <= 0: 
                    break
                
                # Cantidad que vamos a restar en este paso
                cantidad_a_descontar = min(lote.cantidad, restante)
                
                # -------------------------------------------------------------
                # DESCUENTO EN BODEGAALMACENAPRODUCTO DE FORMA ESPECÍFICA
                # -------------------------------------------------------------
                # Buscamos la fila de la bodega que corresponde a este lote
                almacenamiento = BodegaAlmacenaProducto.objects.filter(
                    sku=linea.sku,
                    nombre_bodega=lote.nombre_bodega,       # Usamos la bodega guardada en el lote
                    ubicacion_bodega=lote.ubicacion_bodega
                ).first()
                
                if almacenamiento:
                    almacenamiento.cantidad -= cantidad_a_descontar
                    if almacenamiento.cantidad <= 0:
                        almacenamiento.delete()  # Se elimina de la bodega si queda en 0
                    else:
                        almacenamiento.save(update_fields=['cantidad'])
                # -------------------------------------------------------------

                # Descuento en el lote
                if lote.cantidad > restante:
                    lote.cantidad -= restante
                    lote.save(update_fields=['cantidad'])
                    restante = 0
                else:
                    restance_temp = lote.cantidad
                    restante -= restance_temp
                    lote.delete() # Se elimina el lote si llega a 0
        
        pedido.estado = "aprobado"
        pedido.save()
        
        messages.success(request, f"Pedido #{pedido.id_pedido} procesado correctamente. ¡Sincronizado en lotes y bodegas!")
    
    return redirect("procesar-ventas")