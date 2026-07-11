from django.db import models

# ==========================================
# 1. MODELOS DE CONFIGURACIÓN Y ROLES
# ==========================================

class Rol(models.Model):
    id_rol = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=30)

    class Meta:
        db_table = 'rol'

    def __str__(self):
        return self.nombre


class EstadoCredito(models.Model):
    id_estado = models.IntegerField(primary_key=True)
    nombre_estado = models.CharField(max_length=30)
    descripcion = models.CharField(max_length=60, blank=True, null=True)

    class Meta:
        db_table = 'estado_credito'

    def __str__(self):
        return self.nombre_estado


# ==========================================
# 2. MODELOS DE ENTIDADES (CLIENTES Y EMPLEADOS)
# ==========================================

class Cliente(models.Model):
    rut = models.CharField(primary_key=True, max_length=12)
    fono_contacto = models.IntegerField(blank=True, null=True)
    email = models.CharField(max_length=100, blank=True, null=True)
    limite_credito = models.IntegerField()
    saldo_deudor = models.IntegerField()
    fecha_limite = models.DateField(blank=True, null=True)
    id_estado = models.ForeignKey(EstadoCredito, models.PROTECT, db_column='id_estado')

    class Meta:
        db_table = 'cliente'

    def __str__(self):
        return f"RUT: {self.rut} - Saldo: ${self.saldo_deudor}"


class ClientePersona(models.Model):
    # Relación uno a uno que actúa como Clave Primaria compartida
    rut = models.OneToOneField(Cliente, models.CASCADE, db_column='rut', primary_key=True)
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)

    class Meta:
        db_table = 'cliente_persona'

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.rut_id})"


class ClienteEmpresa(models.Model):
    rut = models.OneToOneField(Cliente, models.CASCADE, db_column='rut', primary_key=True)
    razon_social = models.CharField(max_length=100)
    giro = models.CharField(max_length=100)

    class Meta:
        db_table = 'cliente_empresa'

    def __str__(self):
        return f"{self.razon_social} ({self.rut_id})"


class Empleado(models.Model):
    id_empleado = models.IntegerField(primary_key=True)
    fono_contacto = models.IntegerField()
    nombre = models.CharField(max_length=30)
    apellido = models.CharField(max_length=30)
    id_rol = models.ForeignKey(Rol, models.PROTECT, db_column='id_rol')

    class Meta:
        db_table = 'empleado'

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


# ==========================================
# 3. MODELOS DE PRODUCTOS Y CATEGORÍAS
# ==========================================

class Categoria(models.Model):
    id_categoria = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=30)

    class Meta:
        db_table = 'categoria'

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    sku = models.CharField(primary_key=True, max_length=50)
    nombre = models.CharField(max_length=60)
    precio = models.IntegerField()
    es_granel = models.BooleanField()
    categorias = models.ManyToManyField(
        Categoria, 
        through='CategoriaCategorizaProducto', 
        related_name='productos', 
        blank=True
    )

    class Meta:
        db_table = 'producto'

    def __str__(self):
        return f"{self.nombre} ({self.sku})"


class CategoriaCategorizaProducto(models.Model):
    # Simulación de clave compuesta usando unique_together
    id_categoria = models.ForeignKey(Categoria, models.CASCADE, db_column='id_categoria', primary_key=True)
    sku = models.ForeignKey(Producto, models.CASCADE, db_column='sku')

    class Meta:
        db_table = 'categoria_categoriza_producto'
        unique_together = (('id_categoria', 'sku'),)


# ==========================================
# 4. MODELOS DE OPERACIONES (PEDIDOS Y CRÉDITOS)
# ==========================================

class Pedido(models.Model):
    id_pedido = models.IntegerField(primary_key=True)
    fecha_de_emision = models.DateTimeField()
    estado = models.CharField(max_length=20)
    total_bruto = models.IntegerField()
    es_credito = models.BooleanField()
    rut_cliente = models.ForeignKey(Cliente, models.PROTECT, db_column='rut_cliente')
    id_empleado = models.ForeignKey(Empleado, models.PROTECT, db_column='id_empleado')

    class Meta:
        db_table = 'pedido'

    def __str__(self):
        return f"Pedido N° {self.id_pedido} - {self.rut_cliente.rut}"


class PedidoContieneProducto(models.Model):
    id_pedido = models.ForeignKey(Pedido, models.CASCADE, db_column='id_pedido', primary_key=True)
    sku = models.ForeignKey(Producto, models.PROTECT, db_column='sku')
    cantidad = models.DecimalField(max_digits=10, decimal_places=3)

    class Meta:
        db_table = 'pedido_contiene_producto'
        unique_together = (('id_pedido', 'sku'),)


class AbonoCredito(models.Model):
    id_abono = models.IntegerField(primary_key=True)
    monto = models.IntegerField()
    fecha = models.DateTimeField()
    metodo_pago = models.CharField(max_length=20)
    rut_cliente = models.ForeignKey(Cliente, models.PROTECT, db_column='rut_cliente')
    id_empleado = models.ForeignKey(Empleado, models.PROTECT, db_column='id_empleado')

    class Meta:
        db_table = 'abono_credito'

    def __str__(self):
        return f"Abono N° {self.id_abono} - Cliente: {self.rut_cliente_id} (${self.monto})"


class DocumentoTributario(models.Model):
    id_documento = models.IntegerField(primary_key=True)
    tipo_documento = models.CharField(max_length=15)
    folio = models.IntegerField()
    fecha_emision = models.DateField()
    id_pedido = models.OneToOneField(Pedido, models.PROTECT, db_column='id_pedido')
    id_empleado = models.ForeignKey(Empleado, models.PROTECT, db_column='id_empleado')

    class Meta:
        db_table = 'documento_tributario'

    def __str__(self):
        return f"{self.tipo_documento.upper()} Folio: {self.folio}"


# ==========================================
# 5. MODELOS DE BODEGA Y PROVEEDORES
# ==========================================

class Bodega(models.Model):
    nombre_bodega = models.CharField(max_length=30, primary_key=True)
    ubicacion_bodega = models.CharField(max_length=15)

    class Meta:
        db_table = 'bodega'
        unique_together = (('nombre_bodega', 'ubicacion_bodega'),)

    def __str__(self):
        return f"{self.nombre_bodega} ({self.ubicacion_bodega})"


class BodegaAlmacenaProducto(models.Model):
    nombre_bodega = models.CharField(max_length=30, primary_key=True)
    ubicacion_bodega = models.CharField(max_length=15)
    sku = models.ForeignKey(Producto, models.CASCADE, db_column='sku')
    cantidad = models.IntegerField()

    class Meta:
        db_table = 'bodega_almacena_producto'
        unique_together = (('nombre_bodega', 'ubicacion_bodega', 'sku'),)


class Proveedor(models.Model):
    rut = models.CharField(primary_key=True, max_length=12)
    nombre = models.CharField(max_length=30)
    fono_contacto = models.IntegerField()
    email = models.CharField(max_length=100)

    class Meta:
        db_table = 'proveedor'

    def __str__(self):
        return self.nombre


class ProveedorSuministraProducto(models.Model):
    rut_proveedor = models.ForeignKey(Proveedor, models.CASCADE, db_column='rut_proveedor', primary_key=True)
    sku_producto = models.ForeignKey(Producto, models.CASCADE, db_column='sku_producto')
    fecha = models.DateField()
    fecha_vencimiento_lote = models.DateField()
    cantidad = models.IntegerField()

    class Meta:
        db_table = 'proveedor_suministra_producto'
        unique_together = (('rut_proveedor', 'sku_producto', 'fecha'),)


# ==========================================
# 6. MODELOS DE LOGÍSTICA Y AUDITORÍA
# ==========================================

class Transportista(models.Model):
    id_transportista = models.IntegerField(primary_key=True)
    nombre_chofer = models.CharField(max_length=30)
    fono_contacto = models.IntegerField()

    class Meta:
        db_table = 'transportista'

    def __str__(self):
        return self.nombre_chofer


class Despacho(models.Model):
    id_despacho = models.IntegerField(primary_key=True)
    direccion_entrega = models.CharField(max_length=150)
    fecha_salida = models.DateTimeField(blank=True, null=True)
    estado_entrega = models.CharField(max_length=20)
    id_pedido = models.OneToOneField(Pedido, models.CASCADE, db_column='id_pedido')

    class Meta:
        db_table = 'despacho'


class DespachoTransportista(models.Model):
    id_despacho = models.OneToOneField(Despacho, models.CASCADE, db_column='id_despacho', primary_key=True)
    id_transportista = models.ForeignKey(Transportista, models.PROTECT, db_column='id_transportista')
    patente_vehiculo = models.CharField(max_length=6)

    class Meta:
        db_table = 'despacho_transportista'


class BitacoraLog(models.Model):
    id_log = models.IntegerField(primary_key=True)
    usuario = models.CharField(max_length=60)
    fecha = models.DateTimeField()
    accion = models.CharField(max_length=10)
    campo_modificado = models.CharField(max_length=50, blank=True, null=True)
    valor_antiguo = models.CharField(max_length=160, blank=True, null=True)
    valor_nuevo = models.CharField(max_length=160, blank=True, null=True)

    class Meta:
        db_table = 'bitacora_log'

    def __str__(self):
        return f"{self.usuario} - {self.accion} - {self.fecha}"