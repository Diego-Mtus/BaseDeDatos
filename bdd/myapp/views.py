from django.apps import apps
from django.contrib import messages
from django.db import transaction
from django.core import signing
from django.db.models import Max, Sum
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from datetime import date, datetime, timedelta
from django.db import IntegrityError
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from .forms import AbonoCreditoForm, ClienteCreateForm, PedidoCreateForm, PedidoLineaFormSet, ProductoForm
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
    BodegaAlmacenaProducto
)


PK_TOKEN_SALT = "myapp.model-browser"


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

    if saldo <= 0:
        return "Sin deuda"
    if fecha_limite and fecha_limite < today:
        return "Vencido"
    if limite and saldo >= limite:
        return "Excedido"
    if limite and saldo >= limite * Decimal("0.8"):
        return "Cerca del límite"
    return "Activo"


def _cliente_resumen(cliente, today=None):
    today = today or date.today()
    estado_financiero = _cliente_estado_financiero(cliente, today=today)
    try:
        tipo = "Empresa" if cliente.clienteempresa else "Persona"
    except ObjectDoesNotExist:
        tipo = "Persona"
    return {
        "obj": cliente,
        "nombre": _cliente_nombre(cliente),
        "tipo": tipo,
        "estado_financiero": estado_financiero,
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
    estado_lower = (estado or "").lower()
    if estado_lower == "terminado":
        return "Terminado"
    if estado_lower == "rechazado":
        return "Rechazado"
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
    vencidos = [item for item in cliente_resumenes if item["estado_financiero"] == "Vencido"]
    cerca_limite = [item for item in cliente_resumenes if item["estado_financiero"] == "Cerca del límite"]
    excedidos = [item for item in cliente_resumenes if item["estado_financiero"] == "Excedido"]
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
        "vencidos": vencidos[:5],
        "cerca_limite": cerca_limite[:5],
        "excedidos": excedidos[:5],
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
    clientes = [_cliente_resumen(cliente, today=today) for cliente in _cliente_queryset()]
    return render(
        request,
        "clientes_list.html",
        {
            "clientes": clientes,
            "today": today,
        },
    )


def cliente_create(request):
    if request.method == "POST":
        form = ClienteCreateForm(request.POST)
        if form.is_valid():
            rut = form.cleaned_data["rut"].strip()
            tipo_cliente = form.cleaned_data["tipo_cliente"]

            if Cliente.objects.filter(pk=rut).exists():
                form.add_error("rut", "Ya existe un cliente con este RUT.")
            else:
                with transaction.atomic():
                    cliente = Cliente.objects.create(
                        rut=rut,
                        fono_contacto=form.cleaned_data["fono_contacto"],
                        email=form.cleaned_data["email"],
                        limite_credito=form.cleaned_data["limite_credito"],
                        saldo_deudor=0,
                        fecha_limite=form.cleaned_data["fecha_limite"],
                        id_estado=_estado_credito_inicial(),
                    )
                    if tipo_cliente == ClienteCreateForm.TIPO_PERSONA:
                        ClientePersona.objects.create(
                            rut=cliente,
                            nombre=form.cleaned_data["nombre"],
                            apellido=form.cleaned_data["apellido"],
                        )
                    else:
                        ClienteEmpresa.objects.create(
                            rut=cliente,
                            razon_social=form.cleaned_data["razon_social"],
                            giro=form.cleaned_data["giro"],
                        )
                messages.success(request, "Cliente creado correctamente.")
                return redirect("clientes-list")
    else:
        form = ClienteCreateForm()

    return render(
        request,
        "cliente_form.html",
        {
            "form": form,
        },
    )


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
    vencidos = [item for item in clientes if item["estado_financiero"] == "Vencido"]
    cerca_limite = [item for item in clientes if item["estado_financiero"] == "Cerca del límite"]
    excedidos = [item for item in clientes if item["estado_financiero"] == "Excedido"]
    return render(
        request,
        "alertas_credito.html",
        {
            "vencidos": vencidos,
            "cerca_limite": cerca_limite,
            "excedidos": excedidos,
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
    productos = []
    for producto in Producto.objects.prefetch_related("categorias").all().order_by("nombre"):
        resumen = _producto_stock_summary(producto)
        productos.append({
            "obj": producto,
            **resumen,
        })
    
    total_productos = len(productos)
    con_stock = sum(1 for p in productos if p["stock_disponible"] > 0)
    
    # Esta es la línea que fallaba, ahora ya existe la clave 'origen'
    sin_origen = sum(1 for p in productos if p["origen"] == "Sin origen registrado")
    
    return render(request, "producto_stock.html", {
        "productos": productos,
        "total_productos": total_productos,
        "con_stock": con_stock,
        "sin_origen": sin_origen,
    })

def producto_create(request):
    if request.method == "POST":
        form = ProductoForm(request.POST)
        if form.is_valid():
            # 1. Guardamos el producto base en la base de datos
            producto = form.save(commit=False)
            producto.save()
            form.save_m2m()  # Guarda las categorías
            
            # 2. Recuperamos los datos de la bodega desde el ChoiceField
            bodega_compuesta = form.cleaned_data.get("id_bodega")  # Trae "Nombre|Ubicacion"
            cantidad_inicial = form.cleaned_data.get("cantidad_stock")
            
            if bodega_compuesta and cantidad_inicial is not None:
                # Separamos el nombre y la ubicación de la bodega
                nombre_b, ubicacion_b = bodega_compuesta.split('|')
                
                # 3. Creamos el registro en la tabla con los nombres de campos exactos de tu modelo
                BodegaAlmacenaProducto.objects.create(
                    nombre_bodega=nombre_b,        # Campo CharField PK de tu modelo
                    ubicacion_bodega=ubicacion_b,  # Campo CharField de tu modelo
                    sku=producto,                  # Objeto Producto (Django se encarga del db_column='sku')
                    cantidad=int(cantidad_inicial) # Convertimos a entero ya que tu modelo usa IntegerField()
                )
            
            messages.success(request, "Producto creado e inventario inicial asignado correctamente.")
            return redirect("productos-list")
    else:
        form = ProductoForm()

    return render(request, "producto_form.html", {"form": form, "mode": "create"})
def productos_detail(request, sku):
    producto = get_object_or_404(Producto, pk=sku)
    if request.method == "POST":
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            producto = form.save(commit=False)
            producto.save()
            form.save_m2m()  # El mismo método aquí para las ediciones
            messages.success(request, "Producto actualizado correctamente.")
            return redirect("productos-list")
    else:
        form = ProductoForm(instance=producto)

    resumen = _producto_stock_summary(producto)
    return render(request, "producto_form.html", {"form": form, "mode": "edit", "resumen": resumen})