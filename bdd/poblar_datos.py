import os
import django
import random
from datetime import date, timedelta

# Configurar el entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bdd.settings') # Ajusta 'bdd.settings' si tu proyecto se llama diferente
django.setup()

from faker import Faker
import myapp.models as models_mod # Importación del módulo para limpieza dinámica segura
from myapp.models import (
    Proveedor, Producto, BodegaAlmacenaProducto, ProveedorSuministraProducto,
    EstadoCredito, Cliente, ClientePersona, ClienteEmpresa, Pedido, PedidoContieneProducto,
    Rol, Empleado, Bodega
)

fake = Faker('es_CL') # Configurado para generar nombres y datos lógicos chilenos

def generar_rut_valido(es_empresa=False):
    """Genera un RUT chileno sintáctico válido con su dígito verificador real."""
    if es_empresa:
        cuerpo = random.randint(76000000, 99999999)
    else:
        cuerpo = random.randint(10000000, 25000000)
    
    # Calcular digito verificador (Mod 11)
    suma = 0
    multiplicador = 2
    temp_cuerpo = cuerpo
    while temp_cuerpo > 0:
        suma += (temp_cuerpo % 10) * multiplicador
        temp_cuerpo //= 10
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    
    resto = 11 - (suma % 11)
    if resto == 11:
        dv = '0'
    elif resto == 10:
        dv = 'K'
    else:
        dv = str(resto)
        
    cuerpo_str = f"{cuerpo}"
    return f"{cuerpo_str[:-6]}.{cuerpo_str[-6:-3]}.{cuerpo_str[-3:]}-{dv}"

def limpiar_base_de_datos():
    print("Limpiando base de datos existente...")
    # Orden seguro inverso de dependencias para evitar conflictos de Foreign Key en Postgres
    modelos_en_orden = [
        "AbonoCredito", "DespachoTransportista", "Despacho", "DocumentoTributario",
        "PedidoContieneProducto", "Pedido", "ClientePersona", "ClienteEmpresa", "Cliente",
        "ProveedorSuministraProducto", "BodegaAlmacenaProducto", "CategoriaCategorizaProducto",
        "Categoria", "Bodega", "Producto", "Proveedor", "Empleado", "Rol", "EstadoCredito",
        "Transportista", "BitacoraLog"
    ]
    
    for nombre_modelo in modelos_en_orden:
        try:
            modelo = getattr(models_mod, nombre_modelo)
            modelo.objects.all().delete()
            print(f"  - Tabla de {nombre_modelo} vaciada.")
        except AttributeError:
            pass
        except Exception as e:
            print(f"  - Error limpiando {nombre_modelo}: {e}")
    print("Base de datos limpia.")

def crear_estados_credito():
    print("Creando estados de crédito...")
    # Los 3 estados solicitados
    estados = [
        (1, "Vigente", "Al día en sus cuentas, crédito disponible"),
        (2, "Moroso", "Superó la fecha límite de pago de su crédito"),
        (3, "Bloqueado", "No se permite venta a crédito por deuda vencida")
    ]
    objs = []
    for id_est, nombre, desc in estados:
        obj = EstadoCredito.objects.create(
            id_estado=id_est,
            nombre_estado=nombre,
            descripcion=desc
        )
        objs.append(obj)
    return objs

def crear_roles_y_empleados():
    print("Creando roles y trabajadores...")
    # Creamos los 3 roles solicitados
    rol_admin = Rol.objects.create(id_rol=1, nombre="Administrador")
    rol_vendedor = Rol.objects.create(id_rol=2, nombre="Vendedor")
    rol_inventario = Rol.objects.create(id_rol=3, nombre="Inventario")
    
    # Lista de exactamente 8 trabajadores distribuidos en los roles
    roles_por_trabajador = [
        (1, "Carlos", "Araya", rol_admin),
        (2, "María", "González", rol_admin),
        (3, "Juan", "Pérez", rol_vendedor),
        (4, "Camila", "Muñoz", rol_vendedor),
        (5, "Roberto", "Díaz", rol_vendedor),
        (6, "Sofía", "Soto", rol_vendedor),
        (7, "Andrés", "Silva", rol_inventario),
        (8, "Patricia", "Vergara", rol_inventario),
    ]
    
    empleados = []
    for id_emp, nombre, apellido, rol in roles_por_trabajador:
        # Fono de 9 dígitos para cumplir con la restricción 'chk_fono_empleado_valido'
        fono = random.randint(910000000, 999999999)
        emp = Empleado.objects.create(
            id_empleado=id_emp,
            nombre=nombre,
            apellido=apellido,
            fono_contacto=fono,
            id_rol=rol
        )
        empleados.append(emp)
    return empleados

def crear_bodegas():
    print("Creando bodegas...")
    # Ubicaciones limitadas estrictamente a un máximo de 15 caracteres
    bodegas_datos = [
        ("Bodega Central", "Sector A-1"),
        ("Bodega Norte", "Pasillo B-4"),
        ("Cámara de Frío 1", "Zona Fria") # Cambiado "Zona Refrigerada" (16) a "Zona Fria" (9) para cumplir con varchar(15)
    ]
    bodegas_creadas = []
    for nom, ubi in bodegas_datos:
        b = Bodega.objects.create(
            nombre_bodega=nom,
            ubicacion_bodega=ubi
        )
        bodegas_creadas.append(b)
    return bodegas_creadas

def crear_proveedores():
    print("Creando proveedores...")
    proveedores = []
    for _ in range(4):
        rut = generar_rut_valido(es_empresa=True)
        # Fono de 9 dígitos para cumplir con la restricción 'chk_fono_proveedor_valido'
        fono = random.randint(910000000, 999999999)
        p = Proveedor.objects.create(
            rut=rut,
            nombre=fake.company()[:30],
            fono_contacto=fono,
            email=fake.company_email()[:100]
        )
        proveedores.append(p)
    return proveedores

def crear_productos():
    print("Creando 50 productos maestros (Carnes y Abarrotes)...")
    nombres_productos = [
        # === CARNES (Vacuno, Cerdo, Pollo, Embutidos) ===
        ("Lomo Vetado Vacuno (kg)", 12990, True),
        ("Lomo Liso Vacuno (kg)", 11990, True),
        ("Posta Negra Vacuno (kg)", 8490, True),
        ("Posta Rosada Vacuno (kg)", 8690, True),
        ("Asado de Tira Vacuno (kg)", 9990, True),
        ("Huachalomo Vacuno (kg)", 7290, True),
        ("Abastero Vacuno (kg)", 7490, True),
        ("Sobregiro Vacuno (kg)", 7190, True),
        ("Carne Molida Vacuno 10% Grasa (500g)", 4990, False),
        ("Pulpa de Cerdo sin Hueso (kg)", 5990, True),
        ("Costillar de Cerdo (kg)", 7990, True),
        ("Chuleta de Centro de Cerdo (kg)", 4890, True),
        ("Pechuga de Pollo Entera (kg)", 3990, True),
        ("Trutro Entero de Pollo (kg)", 2990, True),
        ("Filetillo de Pechuga de Pollo (1kg)", 5490, False),
        ("Alas de Pollo (kg)", 2490, True),
        ("Longaniza Artesanal de Chillán (kg)", 7990, True),
        ("Chorizillo Parrillero (pack 10 un)", 4590, False),
        ("Prietas con Nuez (kg)", 4290, True),
        ("Trutro de Pavo (kg)", 3490, True),
        ("Malaya de Cerdo (kg)", 8990, True),
        ("Plateada de Vacuno (kg)", 8990, True),
        ("Punta de Ganso Vacuno (kg)", 12990, True),
        ("Punta Picana Vacuno (kg)", 11490, True),
        ("Hamburguesas Caseras de Vacuno (4 un)", 3990, False),
        
        # === ABARROTES, CONDIMENTOS Y PARRILLA ===
        ("Carbón Vegetal de Espino Premium 3kg", 3490, False),
        ("Carbón Vegetal de Espino Premium 5kg", 5490, False),
        ("Sal Lobos Parrillera Gruesa 1kg", 990, False),
        ("Sal Parrillera con Especias 500g", 1490, False),
        ("Arroz Grado 1 (1kg)", 1490, False),
        ("Tallarines N° 5 (400g)", 890, False),
        ("Aceite de Maravilla 1L", 2890, False),
        ("Aceite de Oliva Extra Virgen 500ml", 4990, False),
        ("Salsa de Tomates Italiana (200g)", 450, False),
        ("Mayonesa Receta Casera (800g)", 3490, False),
        ("Ketchup Tradicional (500g)", 1990, False),
        ("Mostaza Antigua con Semillas (250g)", 1890, False),
        ("Ají en Crema Chileno de la Casa 250g", 1290, False),
        ("Salsa Chimichurri Envasada 200g", 2190, False),
        ("Orégano Entero Seco (100g)", 990, False),
        ("Ajo en Polvo (100g)", 890, False),
        ("Pimienta Negra Molida (100g)", 1490, False),
        ("Comino Molido (100g)", 990, False),
        ("Merkén Tradicional Araucano (100g)", 1590, False),
        ("Bebida Coca-Cola Original 1.5L", 1890, False),
        ("Bebida Fanta Naranja 1.5L", 1690, False),
        ("Jugo en Polvo Sabor Durazno", 250, False),
        ("Puré de Papas Instantáneo (125g)", 950, False),
        ("Papas Fritas de Tarro Rústicas 150g", 1890, False),
        ("Aceitunas Rellenas con Pimentón 300g", 1790, False)
    ]
    productos = []
    for i, (nombre, precio, es_granel) in enumerate(nombres_productos, start=1001):
        p = Producto.objects.create(
            sku=f"PROD-{i}",
            nombre=nombre[:60],
            precio=precio,
            es_granel=es_granel
        )
        productos.append(p)
    return productos

def crear_bodegas_y_lotes(productos, proveedores, bodegas):
    print("Poblando stock en bodegas y lotes...")
    for prod in productos:
        # Si el producto es carne fresca, preferir mandarla a la "Cámara de Frío 1" (el último elemento)
        if any(keyword in prod.nombre for keyword in ["Vacuno", "Cerdo", "Pollo", "Pavo", "Artesanal", "Chorizillo", "Prietas"]):
            bodega_elegida = bodegas[2] # Cámara de Frío
        else:
            bodega_elegida = random.choice(bodegas[:2]) # Bodega Central o Norte
            
        cant_lote = random.randint(30, 100)
        
        # 1. Registrar stock en bodega
        BodegaAlmacenaProducto.objects.create(
            nombre_bodega=bodega_elegida.nombre_bodega,
            ubicacion_bodega=bodega_elegida.ubicacion_bodega,
            sku=prod,
            cantidad=cant_lote
        )
        
        # 2. Crear lote de proveedor
        fecha_llegada = date.today() - timedelta(days=random.randint(1, 5))
        fecha_venc = fecha_llegada + timedelta(days=random.randint(7, 30))
        
        ProveedorSuministraProducto.objects.create(
            rut_proveedor=random.choice(proveedores),
            sku_producto=prod,
            fecha=fecha_llegada,
            fecha_vencimiento_lote=fecha_venc,
            cantidad=cant_lote,
            nombre_bodega=bodega_elegida.nombre_bodega,
            ubicacion_bodega=bodega_elegida.ubicacion_bodega
        )

def crear_clientes(estados):
    print("Creando clientes (Personas y Empresas)...")
    clientes = []
    estado_vigente = estados[0]  # Asociados inicialmente a "Vigente"

    # Generar 4 Clientes Persona
    for _ in range(4):
        rut = generar_rut_valido(es_empresa=False)
        fono = random.randint(910000000, 999999999)
        c = Cliente.objects.create(
            rut=rut,
            fono_contacto=fono,
            email=fake.email()[:100],
            limite_credito=random.choice([200000, 400000, 600000]),
            saldo_deudor=0,
            fecha_limite=date.today() + timedelta(days=30),
            id_estado=estado_vigente
        )
        ClientePersona.objects.create(
            rut=c,
            nombre=fake.first_name()[:50],
            apellido=fake.last_name()[:50]
        )
        clientes.append(c)

    # Generar 3 Clientes Empresa
    for _ in range(3):
        rut = generar_rut_valido(es_empresa=True)
        fono = random.randint(910000000, 999999999)
        c = Cliente.objects.create(
            rut=rut,
            fono_contacto=fono,
            email=fake.company_email()[:100],
            limite_credito=1200000,
            saldo_deudor=0,
            fecha_limite=date.today() + timedelta(days=30),
            id_estado=estado_vigente
        )
        # Slicing inteligente de razón social para que no supere los 100 caracteres
        razon_social_sintetica = (fake.company()[:90] + " S.A.")
        ClienteEmpresa.objects.create(
            rut=c,
            razon_social=razon_social_sintetica,
            giro="Minimarket y Distribución"
        )
        clientes.append(c)
        
    return clientes

def crear_pedidos_de_prueba(clientes, productos, empleados):
    print("Creando pedidos de prueba para el módulo de ventas...")
    # Filtramos los trabajadores con rol Vendedor (id_rol = 2)
    vendedores = [emp for emp in empleados if emp.id_rol.id_rol == 2]
    
    for i in range(1, 5):
        cliente = random.choice(clientes)
        vendedor_asignado = random.choice(vendedores)
        
        pedido = Pedido.objects.create(
            id_pedido=i,
            fecha_de_emision=date.today(),
            estado="pendiente", 
            total_bruto=1, 
            es_credito=random.choice([True, False]),
            rut_cliente=cliente,
            id_empleado=vendedor_asignado
        )
        
        # Elige de 1 a 3 productos aleatorios para simular compras mixtas de carnes y abarrotes
        productos_pedido = random.sample(productos, k=random.randint(1, 3))
        total_acumulado = 0
        
        for prod in productos_pedido:
            cant = random.randint(1, 4) if not prod.es_granel else round(random.uniform(0.5, 3.0), 3)
            PedidoContieneProducto.objects.create(
                id_pedido=pedido,
                sku=prod,
                cantidad=cant
            )
            total_acumulado += int(prod.precio * cant)
            
        pedido.total_bruto = total_acumulado
        pedido.save(update_fields=['total_bruto'])

def principal():
    print("=== INICIANDO GENERACIÓN DE DATOS SINTÉTICOS ===")
    limpiar_base_de_datos()
    estados = crear_estados_credito()
    empleados = crear_roles_y_empleados()
    bodegas = crear_bodegas()
    proveedores = crear_proveedores()
    productos = crear_productos()
    crear_bodegas_y_lotes(productos, proveedores, bodegas)
    clientes = crear_clientes(estados)
    crear_pedidos_de_prueba(clientes, productos, empleados)
    print("=== PROCESO FINALIZADO EXITOSAMENTE ===")

if __name__ == '__main__':
    principal()