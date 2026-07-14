--
-- PostgreSQL database dump
--

\restrict 2vh32p7vSmzANyRzROv3dG943JLq0udbVeMkL3tZKNPGS5aJD3PyPsoVvQYXVGQ

-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

-- Started on 2026-07-11 12:18:39

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 254 (class 1255 OID 16407)
-- Name: validar_email(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.validar_email(email text) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $_$
DECLARE
    email_limpio TEXT;
BEGIN
    -- permite null
    IF email IS NULL THEN
        RETURN TRUE;
    END IF;

    -- limpiar string
    email_limpio := LOWER(TRIM(email));

    -- aplicar expresión regular para emails
    IF email_limpio ~ '^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$' THEN
        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$_$;


ALTER FUNCTION public.validar_email(email text) OWNER TO postgres;

--
-- TOC entry 253 (class 1255 OID 16401)
-- Name: validar_fono(bigint); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.validar_fono(fono bigint) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $$
BEGIN
    -- permite null
    IF fono IS NULL THEN
        RETURN TRUE;
    END IF;

    -- validar que el número tiene 9 dígitos 
    IF fono >= 100000000 AND fono <= 999999999 THEN
        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$$;


ALTER FUNCTION public.validar_fono(fono bigint) OWNER TO postgres;

--
-- TOC entry 252 (class 1255 OID 16400)
-- Name: validar_patente(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.validar_patente(patente text) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $_$
DECLARE
    patente_limpia TEXT;
BEGIN
    -- limpiar string
    patente_limpia := UPPER(REGEXP_REPLACE(patente, '[^A-Z0-9]', '', 'g'));
    
    -- debe tener 6 caract
    IF LENGTH(patente_limpia) <> 6 THEN
        RETURN FALSE;
    END IF;

    -- antiguo: 2 letras (A-Z) + 4 num (0-9)
    -- nuevo: 4 letras (menos vocales, M, N, Ñ, O, Q) + 2 num (0-9)
    IF patente_limpia ~ '^[A-Z]{2}[0-9]{4}$' OR 
       patente_limpia ~ '^[BCDFGHJKLPRSTVWXYZ]{4}[0-9]{2}$' THEN
        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$_$;


ALTER FUNCTION public.validar_patente(patente text) OWNER TO postgres;

--
-- TOC entry 251 (class 1255 OID 16399)
-- Name: validar_rut(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.validar_rut(rut_completo text) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE
    rut_limpio TEXT;
    cuerpo INT;
    dv_ingresado CHAR(1);
    suma INT := 0;
    multiplicador INT := 2;
    resto INT;
    dv_esperado CHAR(1);
    i INT;
BEGIN
    -- limpiar el string
    rut_limpio := UPPER(REGEXP_REPLACE(rut_completo, '[^\dkK]', '', 'g'));
    
    -- ej: 12345678K o 9123456K
    IF LENGTH(rut_limpio) < 8 OR LENGTH(rut_limpio) > 9 THEN
        RETURN FALSE;
    END IF;
    
    -- separar dv
    dv_ingresado := RIGHT(rut_limpio, 1);
    cuerpo := CAST(LEFT(rut_limpio, LENGTH(rut_limpio) - 1) AS INT);
    
    -- algoritmo mod11
    i := LENGTH(CAST(cuerpo AS TEXT));
    WHILE cuerpo > 0 LOOP
        suma := suma + (cuerpo % 10) * multiplicador;
        cuerpo := cuerpo / 10;
        multiplicador := multiplicador + 1;
        IF multiplicador > 7 THEN
            multiplicador := 2;
        END IF;
    END LOOP;
    
    resto := 11 - (suma % 11);
    
    -- determinar cuál debería ser el dv
    IF resto = 11 THEN
        dv_esperado := '0';
    ELSIF resto = 10 THEN
        dv_esperado := 'K';
    ELSE
        dv_esperado := CAST(resto AS CHAR(1));
    END IF;
    
    RETURN (dv_ingresado = dv_esperado);
EXCEPTION
    WHEN OTHERS THEN
        RETURN FALSE;
END;
$$;


ALTER FUNCTION public.validar_rut(rut_completo text) OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 225 (class 1259 OID 16476)
-- Name: abono_credito; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.abono_credito (
    id_abono integer NOT NULL,
    monto integer NOT NULL,
    fecha timestamp without time zone NOT NULL,
    metodo_pago character varying(20) NOT NULL,
    rut_cliente character varying(12) NOT NULL,
    id_empleado integer NOT NULL,
    CONSTRAINT chk_metodo_pago CHECK (((metodo_pago)::text = ANY ((ARRAY['efectivo'::character varying, 'debito'::character varying, 'transferencia'::character varying, 'credito'::character varying])::text[]))),
    CONSTRAINT chk_monto_abono CHECK ((monto > 0))
);


ALTER TABLE public.abono_credito OWNER TO postgres;

--
-- TOC entry 234 (class 1259 OID 16616)
-- Name: bitacora_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bitacora_log (
    id_log integer NOT NULL,
    usuario character varying(60) NOT NULL,
    fecha timestamp without time zone NOT NULL,
    accion character varying(10) NOT NULL,
    campo_modificado character varying(50),
    valor_antiguo character varying(160),
    valor_nuevo character varying(160),
    CONSTRAINT chk_accion_log CHECK (((accion)::text = ANY ((ARRAY['INSERT'::character varying, 'UPDATE'::character varying, 'DELETE'::character varying])::text[])))
);


ALTER TABLE public.bitacora_log OWNER TO postgres;

--
-- TOC entry 233 (class 1259 OID 16609)
-- Name: bodega; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bodega (
    nombre_bodega character varying(30) NOT NULL,
    ubicacion_bodega character varying(15) NOT NULL
);


ALTER TABLE public.bodega OWNER TO postgres;

--
-- TOC entry 239 (class 1259 OID 16696)
-- Name: bodega_almacena_producto; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bodega_almacena_producto (
    nombre_bodega character varying(30) NOT NULL,
    ubicacion_bodega character varying(15) NOT NULL,
    sku character varying(50) NOT NULL,
    cantidad integer NOT NULL,
    CONSTRAINT chk_cantidad_bap CHECK ((cantidad > 0))
);


ALTER TABLE public.bodega_almacena_producto OWNER TO postgres;

--
-- TOC entry 231 (class 1259 OID 16592)
-- Name: categoria; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.categoria (
    id_categoria integer NOT NULL,
    nombre character varying(30) NOT NULL
);


ALTER TABLE public.categoria OWNER TO postgres;

--
-- TOC entry 237 (class 1259 OID 16657)
-- Name: categoria_categoriza_producto; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.categoria_categoriza_producto (
    id_categoria integer NOT NULL,
    sku character varying(50) NOT NULL
);


ALTER TABLE public.categoria_categoriza_producto OWNER TO postgres;

--
-- TOC entry 220 (class 1259 OID 16408)
-- Name: cliente; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cliente (
    rut character varying(12) NOT NULL,
    fono_contacto integer,
    email character varying(100),
    limite_credito integer NOT NULL,
    saldo_deudor integer NOT NULL,
    fecha_limite date,
    id_estado integer NOT NULL,
    CONSTRAINT chk_email_cliente_valido CHECK ((public.validar_email((email)::text) = true)),
    CONSTRAINT chk_fono_cliente_valido CHECK ((public.validar_fono((fono_contacto)::bigint) = true)),
    CONSTRAINT chk_limite_credito CHECK ((limite_credito >= 0)),
    CONSTRAINT chk_rut_cliente_valido CHECK ((public.validar_rut((rut)::text) = true)),
    CONSTRAINT chk_saldo_deudor CHECK ((saldo_deudor >= 0))
);


ALTER TABLE public.cliente OWNER TO postgres;

--
-- TOC entry 222 (class 1259 OID 16440)
-- Name: cliente_empresa; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cliente_empresa (
    rut character varying(12) NOT NULL,
    razon_social character varying(100) NOT NULL,
    giro character varying(100) NOT NULL
);


ALTER TABLE public.cliente_empresa OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 16427)
-- Name: cliente_persona; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cliente_persona (
    rut character varying(12) NOT NULL,
    nombre character varying(50) NOT NULL,
    apellido character varying(50) NOT NULL
);


ALTER TABLE public.cliente_persona OWNER TO postgres;

--
-- TOC entry 228 (class 1259 OID 16547)
-- Name: despacho; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.despacho (
    id_despacho integer NOT NULL,
    direccion_entrega character varying(150) NOT NULL,
    fecha_salida timestamp without time zone,
    estado_entrega character varying(20) NOT NULL,
    id_pedido integer NOT NULL,
    CONSTRAINT chk_estado_entrega CHECK (((estado_entrega)::text = ANY ((ARRAY['en preparacion'::character varying, 'en camino'::character varying, 'entregado'::character varying])::text[])))
);


ALTER TABLE public.despacho OWNER TO postgres;

--
-- TOC entry 230 (class 1259 OID 16573)
-- Name: despacho_transportista; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.despacho_transportista (
    id_despacho integer NOT NULL,
    id_transportista integer NOT NULL,
    patente_vehiculo character varying(6) NOT NULL,
    CONSTRAINT chk_patente_valida CHECK ((public.validar_patente((patente_vehiculo)::text) = true))
);


ALTER TABLE public.despacho_transportista OWNER TO postgres;

--
-- TOC entry 227 (class 1259 OID 16523)
-- Name: documento_tributario; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.documento_tributario (
    id_documento integer NOT NULL,
    tipo_documento character varying(15) NOT NULL,
    folio integer NOT NULL,
    fecha_emision date NOT NULL,
    id_pedido integer NOT NULL,
    id_empleado integer NOT NULL,
    CONSTRAINT chk_tipo_documento CHECK (((tipo_documento)::text = ANY ((ARRAY['boleta'::character varying, 'factura'::character varying])::text[])))
);


ALTER TABLE public.documento_tributario OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 16460)
-- Name: empleado; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.empleado (
    id_empleado integer NOT NULL,
    fono_contacto integer NOT NULL,
    nombre character varying(30) NOT NULL,
    apellido character varying(30) NOT NULL,
    id_rol integer NOT NULL,
    CONSTRAINT chk_fono_empleado_valido CHECK ((public.validar_fono((fono_contacto)::bigint) = true))
);


ALTER TABLE public.empleado OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 16389)
-- Name: estado_credito; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.estado_credito (
    id_estado integer NOT NULL,
    nombre_estado character varying(30) NOT NULL,
    descripcion character varying(60)
);


ALTER TABLE public.estado_credito OWNER TO postgres;

--
-- TOC entry 226 (class 1259 OID 16499)
-- Name: pedido; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.pedido (
    id_pedido integer NOT NULL,
    fecha_de_emision timestamp without time zone NOT NULL,
    estado character varying(20) NOT NULL,
    total_bruto integer NOT NULL,
    es_credito boolean NOT NULL,
    rut_cliente character varying(12) NOT NULL,
    id_empleado integer NOT NULL,
    CONSTRAINT chk_estado_pedido CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'aprobado'::character varying, 'anulado'::character varying])::text[]))),
    CONSTRAINT chk_total_bruto CHECK ((total_bruto > 0))
);


ALTER TABLE public.pedido OWNER TO postgres;

--
-- TOC entry 236 (class 1259 OID 16638)
-- Name: pedido_contiene_producto; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.pedido_contiene_producto (
    id_pedido integer NOT NULL,
    sku character varying(50) NOT NULL,
    cantidad numeric(10,3) NOT NULL,
    CONSTRAINT chk_cantidad_pcp CHECK ((cantidad > (0)::numeric))
);


ALTER TABLE public.pedido_contiene_producto OWNER TO postgres;

--
-- TOC entry 232 (class 1259 OID 16599)
-- Name: producto; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.producto (
    sku character varying(50) NOT NULL,
    nombre character varying(60) NOT NULL,
    precio integer NOT NULL,
    es_granel boolean NOT NULL,
    CONSTRAINT chk_precio_prod CHECK ((precio > 0))
);


ALTER TABLE public.producto OWNER TO postgres;

--
-- TOC entry 235 (class 1259 OID 16626)
-- Name: proveedor; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.proveedor (
    rut character varying(12) NOT NULL,
    nombre character varying(30) NOT NULL,
    fono_contacto integer NOT NULL,
    email character varying(100) NOT NULL,
    CONSTRAINT chk_email_proveedor_valido CHECK ((public.validar_email((email)::text) = true)),
    CONSTRAINT chk_fono_proveedor_valido CHECK ((public.validar_fono((fono_contacto)::bigint) = true)),
    CONSTRAINT chk_rut_proveedor_valido CHECK ((public.validar_rut((rut)::text) = true))
);


ALTER TABLE public.proveedor OWNER TO postgres;

--
-- TOC entry 238 (class 1259 OID 16674)
-- Name: proveedor_suministra_producto; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.proveedor_suministra_producto (
    rut_proveedor character varying(12) NOT NULL,
    sku_producto character varying(50) NOT NULL,
    fecha date NOT NULL,
    fecha_vencimiento_lote date NOT NULL,
    cantidad integer NOT NULL,
    CONSTRAINT chk_cantidad_psp CHECK ((cantidad > 0)),
    CONSTRAINT chk_fechas_psp CHECK ((fecha_vencimiento_lote > fecha))
);


ALTER TABLE public.proveedor_suministra_producto OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 16453)
-- Name: rol; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.rol (
    id_rol integer NOT NULL,
    nombre character varying(30) NOT NULL
);


ALTER TABLE public.rol OWNER TO postgres;

--
-- TOC entry 229 (class 1259 OID 16564)
-- Name: transportista; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.transportista (
    id_transportista integer NOT NULL,
    nombre_chofer character varying(30) NOT NULL,
    fono_contacto integer NOT NULL,
    CONSTRAINT chk_fono_transportista_valido CHECK ((public.validar_fono((fono_contacto)::bigint) = true))
);


ALTER TABLE public.transportista OWNER TO postgres;

--
-- TOC entry 5182 (class 0 OID 16476)
-- Dependencies: 225
-- Data for Name: abono_credito; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.abono_credito (id_abono, monto, fecha, metodo_pago, rut_cliente, id_empleado) FROM stdin;
1	150000	2026-05-15 10:00:00	transferencia	17.456.789-1	4
2	50000	2026-05-28 17:30:00	efectivo	15.654.321-7	4
\.


--
-- TOC entry 5191 (class 0 OID 16616)
-- Dependencies: 234
-- Data for Name: bitacora_log; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.bitacora_log (id_log, usuario, fecha, accion, campo_modificado, valor_antiguo, valor_nuevo) FROM stdin;
\.


--
-- TOC entry 5190 (class 0 OID 16609)
-- Dependencies: 233
-- Data for Name: bodega; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.bodega (nombre_bodega, ubicacion_bodega) FROM stdin;
frigorifico_1	seccion_a
frigorifico_1	seccion_b
frigorifico_2	seccion_a
central	pasillo_1
central	pasillo_2
abarrotes	estante_1
abarrotes	estante_2
\.


--
-- TOC entry 5196 (class 0 OID 16696)
-- Dependencies: 239
-- Data for Name: bodega_almacena_producto; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.bodega_almacena_producto (nombre_bodega, ubicacion_bodega, sku, cantidad) FROM stdin;
frigorifico_1	seccion_a	PROD-CAR-001	150
frigorifico_1	seccion_a	PROD-CAR-002	80
frigorifico_1	seccion_b	PROD-CAR-003	300
frigorifico_2	seccion_a	PROD-CAR-004	200
frigorifico_2	seccion_a	PROD-CAR-005	120
frigorifico_1	seccion_b	PROD-CAR-006	400
frigorifico_1	seccion_a	PROD-CAR-007	500
frigorifico_1	seccion_b	PROD-CEC-001	90
frigorifico_2	seccion_a	PROD-CEC-002	60
abarrotes	estante_1	PROD-ABA-001	1000
abarrotes	estante_1	PROD-ABA-002	600
abarrotes	estante_2	PROD-ABA-003	800
abarrotes	estante_1	PROD-ABA-004	300
abarrotes	estante_2	PROD-ABA-005	1500
abarrotes	estante_2	PROD-ABA-006	1200
frigorifico_2	seccion_a	PROD-LAC-001	110
abarrotes	estante_1	PROD-LAC-002	900
frigorifico_1	seccion_b	PROD-CAR-008	250
abarrotes	estante_2	PROD-ABA-007	700
abarrotes	estante_1	PROD-CEC-003	150
\.


--
-- TOC entry 5188 (class 0 OID 16592)
-- Dependencies: 231
-- Data for Name: categoria; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.categoria (id_categoria, nombre) FROM stdin;
1	vacuno
2	cerdo
3	ave
4	abarrotes
5	embutidos
6	lacteos
\.


--
-- TOC entry 5194 (class 0 OID 16657)
-- Dependencies: 237
-- Data for Name: categoria_categoriza_producto; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.categoria_categoriza_producto (id_categoria, sku) FROM stdin;
1	PROD-CAR-001
1	PROD-CAR-002
1	PROD-CAR-003
1	PROD-CAR-008
2	PROD-CAR-004
2	PROD-CAR-005
3	PROD-CAR-006
3	PROD-CAR-007
5	PROD-CEC-001
5	PROD-CEC-002
5	PROD-CEC-003
4	PROD-ABA-001
4	PROD-ABA-002
4	PROD-ABA-003
4	PROD-ABA-004
4	PROD-ABA-005
4	PROD-ABA-006
4	PROD-ABA-007
6	PROD-LAC-001
6	PROD-LAC-002
\.


--
-- TOC entry 5177 (class 0 OID 16408)
-- Dependencies: 220
-- Data for Name: cliente; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cliente (rut, fono_contacto, email, limite_credito, saldo_deudor, fecha_limite, id_estado) FROM stdin;
15.654.321-7	991112223	luis.gomez@email.com	500000	120000	2026-07-15	1
16.789.123-3	992223334	carmen.reyes@email.com	300000	0	\N	1
17.456.789-1	993334445	contacto@minimarketpedro.cl	1500000	450000	2026-06-30	1
18.123.456-3	994445556	jose.araya@email.com	200000	50000	2026-06-25	1
76.456.123-6	995556667	adquisiciones@empanadasbiobio.cl	2000000	850000	2026-07-01	1
14.321.987-9	996667778	marta.lopez@email.com	400000	0	\N	1
19.876.543-0	997778889	diego.munoz@email.com	100000	15000	2026-06-20	1
12.987.654-9	998889990	raul.castro@email.com	300000	280000	2026-05-01	2
77.111.222-6	999990001	pagos@restorantconcepcion.cl	2500000	2500000	2026-04-15	2
10.234.567-3	992224446	andres.bello@email.com	50000	65000	2026-05-20	3
13.456.789-9	993335557	elena.g@email.com	600000	0	\N	1
15.111.222-6	994446668	felipe.m@email.com	300000	90000	2026-07-10	1
79.888.777-7	995557779	info@sandwicheriacentro.cl	1200000	300000	2026-06-28	1
20.123.987-7	996668880	javier.p@email.com	200000	0	\N	1
11.765.432-K	991113335	sofia.vergara@email.com	20000	0	2026-05-10	1
\.


--
-- TOC entry 5179 (class 0 OID 16440)
-- Dependencies: 222
-- Data for Name: cliente_empresa; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cliente_empresa (rut, razon_social, giro) FROM stdin;
17.456.789-1	Comercial Pedro Almacenes Limitada	Minimarket
76.456.123-6	Sociedad de Alimentos Biobío SpA	Elaboración de Empanadas y Masas
77.111.222-6	Gastronomía y Turismo Concepción S.A.	Restaurantes y Hotelería
79.888.777-7	Sandwichería El Centro Limitada	Comida Rápida
\.


--
-- TOC entry 5178 (class 0 OID 16427)
-- Dependencies: 221
-- Data for Name: cliente_persona; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cliente_persona (rut, nombre, apellido) FROM stdin;
15.654.321-7	Luis	Gómez
16.789.123-3	Carmen	Reyes
18.123.456-3	José	Araya
14.321.987-9	Marta	López
19.876.543-0	Diego	Muñoz
12.987.654-9	Raúl	Castro
11.765.432-K	Sofía	Vergara
10.234.567-3	Andrés	Bello
13.456.789-9	Elena	Gutiérrez
15.111.222-6	Felipe	Maldonado
20.123.987-7	Javier	Pinto
\.


--
-- TOC entry 5185 (class 0 OID 16547)
-- Dependencies: 228
-- Data for Name: despacho; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.despacho (id_despacho, direccion_entrega, fecha_salida, estado_entrega, id_pedido) FROM stdin;
1	O’Higgins 450, Concepción	2026-05-02 14:00:00	entregado	1
2	Av. Paicaví 2300, Concepción	2026-05-10 16:00:00	entregado	2
3	Barros Arana 890, Concepción	2026-04-01 15:00:00	entregado	5
4	Colón 455, Talcahuano	\N	en preparacion	4
\.


--
-- TOC entry 5187 (class 0 OID 16573)
-- Dependencies: 230
-- Data for Name: despacho_transportista; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.despacho_transportista (id_despacho, id_transportista, patente_vehiculo) FROM stdin;
1	1	BBCC12
2	2	CHDL45
3	1	BBCC12
\.


--
-- TOC entry 5184 (class 0 OID 16523)
-- Dependencies: 227
-- Data for Name: documento_tributario; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.documento_tributario (id_documento, tipo_documento, folio, fecha_emision, id_pedido, id_empleado) FROM stdin;
1	factura	5001	2026-05-02	1	4
2	factura	5002	2026-05-10	2	4
3	boleta	12001	2026-05-25	3	4
4	factura	5003	2026-04-01	5	4
5	factura	5004	2026-04-15	6	4
6	boleta	12002	2026-05-05	7	4
7	factura	5005	2026-05-20	8	4
8	boleta	12003	2026-06-02	9	4
9	boleta	12004	2026-06-02	10	4
\.


--
-- TOC entry 5181 (class 0 OID 16460)
-- Dependencies: 224
-- Data for Name: empleado; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.empleado (id_empleado, fono_contacto, nombre, apellido, id_rol) FROM stdin;
1	987654321	Juan	Pérez	1
2	912345678	María	González	2
3	923456789	Pedro	Soto	2
4	934567890	Ana	Silva	3
5	945678901	Carlos	Martínez	4
6	956789012	Luisa	Fuentes	4
\.


--
-- TOC entry 5176 (class 0 OID 16389)
-- Dependencies: 219
-- Data for Name: estado_credito; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.estado_credito (id_estado, nombre_estado, descripcion) FROM stdin;
1	vigente	Cliente al día con capacidad de compra a crédito
2	bloqueado	Cliente suspendido temporalmente por administración
3	moroso	Cliente con deudas fuera del plazo límite
\.


--
-- TOC entry 5183 (class 0 OID 16499)
-- Dependencies: 226
-- Data for Name: pedido; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.pedido (id_pedido, fecha_de_emision, estado, total_bruto, es_credito, rut_cliente, id_empleado) FROM stdin;
1	2026-05-02 10:00:00	aprobado	150000	t	17.456.789-1	2
2	2026-05-10 11:30:00	aprobado	230000	t	17.456.789-1	3
3	2026-05-25 09:15:00	aprobado	70000	f	17.456.789-1	2
4	2026-06-01 16:00:00	pendiente	450000	t	17.456.789-1	3
5	2026-04-01 12:00:00	aprobado	1200000	t	77.111.222-6	2
6	2026-04-15 14:00:00	aprobado	1300000	t	77.111.222-6	2
7	2026-05-05 15:30:00	aprobado	85000	f	15.654.321-7	2
8	2026-05-20 10:45:00	aprobado	120000	t	15.654.321-7	3
9	2026-06-02 11:00:00	aprobado	25500	f	16.789.123-3	2
10	2026-06-02 11:20:00	aprobado	41200	f	18.123.456-3	3
11	2026-06-03 09:00:00	aprobado	115000	t	76.456.123-6	2
12	2026-06-03 13:10:00	anulado	95000	f	14.321.987-9	2
13	2026-06-04 17:00:00	aprobado	15000	t	19.876.543-0	3
14	2026-06-05 10:00:00	aprobado	280000	t	12.987.654-9	2
15	2026-06-05 12:00:00	aprobado	65000	t	10.234.567-3	3
16	2026-06-06 14:30:00	aprobado	90000	t	15.111.222-6	2
17	2026-06-06 15:00:00	aprobado	300000	t	79.888.777-7	2
18	2026-06-06 16:15:00	aprobado	55400	f	20.123.987-7	3
19	2026-06-07 10:30:00	aprobado	32000	f	16.789.123-3	2
20	2026-06-07 11:00:00	aprobado	14500	f	13.456.789-9	3
21	2026-06-07 12:45:00	aprobado	74000	t	76.456.123-6	2
22	2026-06-07 16:00:00	pendiente	110000	t	17.456.789-1	3
23	2026-06-08 09:15:00	aprobado	22500	f	18.123.456-3	2
24	2026-06-08 10:00:00	aprobado	18900	f	14.321.987-9	3
25	2026-06-08 11:15:00	aprobado	53000	f	20.123.987-7	2
\.


--
-- TOC entry 5193 (class 0 OID 16638)
-- Dependencies: 236
-- Data for Name: pedido_contiene_producto; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.pedido_contiene_producto (id_pedido, sku, cantidad) FROM stdin;
1	PROD-CAR-001	10.500
1	PROD-ABA-001	5.000
2	PROD-CAR-002	12.000
2	PROD-CAR-005	5.500
2	PROD-ABA-002	10.000
3	PROD-CEC-001	5.000
3	PROD-ABA-003	12.000
3	PROD-ABA-006	20.000
4	PROD-CAR-001	25.000
4	PROD-CAR-003	15.000
5	PROD-CAR-002	50.000
5	PROD-CAR-003	40.000
5	PROD-LAC-001	15.000
6	PROD-CAR-001	60.000
6	PROD-CAR-006	80.000
7	PROD-CAR-003	5.000
7	PROD-ABA-001	10.000
7	PROD-ABA-002	5.000
8	PROD-CAR-002	6.000
8	PROD-CEC-002	3.500
9	PROD-CAR-008	3.000
9	PROD-ABA-005	6.000
9	PROD-ABA-006	4.000
10	PROD-CAR-006	5.000
10	PROD-ABA-007	8.000
11	PROD-CAR-004	15.000
11	PROD-CEC-001	4.000
12	PROD-CAR-002	5.000
12	PROD-LAC-001	2.000
13	PROD-ABA-001	4.000
13	PROD-ABA-002	3.000
13	PROD-ABA-005	4.000
14	PROD-CAR-001	18.000
14	PROD-CAR-005	10.000
15	PROD-CAR-003	5.000
15	PROD-LAC-001	2.000
16	PROD-CAR-002	4.000
16	PROD-CEC-003	10.000
17	PROD-CAR-001	15.000
17	PROD-CAR-007	30.000
17	PROD-ABA-003	10.000
18	PROD-CAR-008	4.000
18	PROD-ABA-001	10.000
18	PROD-LAC-002	12.000
19	PROD-CAR-004	4.500
19	PROD-ABA-002	4.000
20	PROD-CEC-002	1.200
20	PROD-ABA-005	3.000
21	PROD-CAR-006	10.000
21	PROD-ABA-003	20.000
22	PROD-CAR-002	6.500
22	PROD-LAC-001	2.000
23	PROD-CAR-008	3.000
23	PROD-ABA-007	5.000
24	PROD-CAR-007	4.000
24	PROD-LAC-002	6.000
25	PROD-CAR-001	3.000
25	PROD-CEC-001	2.000
25	PROD-ABA-001	2.000
\.


--
-- TOC entry 5189 (class 0 OID 16599)
-- Dependencies: 232
-- Data for Name: producto; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.producto (sku, nombre, precio, es_granel) FROM stdin;
PROD-CAR-001	Asiento de Vacuno Premium (Kg)	11990	t
PROD-CAR-002	Lomo Vetado Vacuno (Kg)	14590	t
PROD-CAR-003	Posta Rosada Vacuno (Kg)	8990	t
PROD-CAR-004	Pulpa de Cerdo deshuesada (Kg)	5490	t
PROD-CAR-005	Costillar de Cerdo (Kg)	6990	t
PROD-CAR-006	Pechuga de Pollo deshuesada (Kg)	4890	t
PROD-CAR-007	Trutro Entero de Pollo (Kg)	2990	t
PROD-CEC-001	Longaniza Tradicional Chillán (Kg)	7490	t
PROD-CEC-002	Jamón Colonial Receta del Abuelo (Kg)	9290	t
PROD-ABA-001	Arroz Grado 1 Tucapel 1Kg	1450	f
PROD-ABA-002	Aceite Vegetal Belmont 1L	1990	f
PROD-ABA-003	Harina Collico con Polvos 1Kg	1250	f
PROD-ABA-004	Sal Lobos Mesa 1Kg	650	f
PROD-ABA-005	Tallarines Lucchetti N°5 400g	890	f
PROD-ABA-006	Salsa de Tomate Carozzi 200g	550	f
PROD-LAC-001	Queso Mantecoso Fundo Los Alerces (Kg)	9890	t
PROD-LAC-002	Leche Entera Colun 1L	1100	f
PROD-CAR-008	Carne Molida Vacuno 400g	3990	f
PROD-ABA-007	Azúcar Iansa 1Kg	1390	f
PROD-CEC-003	Salamini PF (Unidad)	2490	f
\.


--
-- TOC entry 5192 (class 0 OID 16626)
-- Dependencies: 235
-- Data for Name: proveedor; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.proveedor (rut, nombre, fono_contacto, email) FROM stdin;
76.123.456-0	Distribuidora Carnes del Sur	955511122	contacto@carnesdelsur.cl
96.987.654-K	Abarrotes Concepción S.A.	955533344	ventas@abarrotesconcepcion.cl
88.444.555-8	Cecinas Chillán SpA	944455566	pedidos@cecinaschillan.cl
\.


--
-- TOC entry 5195 (class 0 OID 16674)
-- Dependencies: 238
-- Data for Name: proveedor_suministra_producto; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.proveedor_suministra_producto (rut_proveedor, sku_producto, fecha, fecha_vencimiento_lote, cantidad) FROM stdin;
76.123.456-0	PROD-CAR-001	2026-05-01	2026-06-30	200
76.123.456-0	PROD-CAR-002	2026-05-01	2026-06-25	100
96.987.654-K	PROD-ABA-001	2026-04-10	2027-04-10	1200
96.987.654-K	PROD-ABA-002	2026-04-10	2026-12-10	700
88.444.555-8	PROD-CEC-001	2026-05-10	2026-07-10	150
\.


--
-- TOC entry 5180 (class 0 OID 16453)
-- Dependencies: 223
-- Data for Name: rol; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.rol (id_rol, nombre) FROM stdin;
1	administrador
2	vendedor
3	cajero
4	bodeguero
\.


--
-- TOC entry 5186 (class 0 OID 16564)
-- Dependencies: 229
-- Data for Name: transportista; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.transportista (id_transportista, nombre_chofer, fono_contacto) FROM stdin;
1	Roberto Muñoz	967890123
2	Jorge Tapia	978901234
3	Miguel Alamos	989012345
\.


--
-- TOC entry 4975 (class 2606 OID 16488)
-- Name: abono_credito pk_abono_credito; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.abono_credito
    ADD CONSTRAINT pk_abono_credito PRIMARY KEY (id_abono);


--
-- TOC entry 4997 (class 2606 OID 16625)
-- Name: bitacora_log pk_bitacora_log; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bitacora_log
    ADD CONSTRAINT pk_bitacora_log PRIMARY KEY (id_log);


--
-- TOC entry 4995 (class 2606 OID 16615)
-- Name: bodega pk_bodega; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bodega
    ADD CONSTRAINT pk_bodega PRIMARY KEY (nombre_bodega, ubicacion_bodega);


--
-- TOC entry 4991 (class 2606 OID 16598)
-- Name: categoria pk_categoria; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categoria
    ADD CONSTRAINT pk_categoria PRIMARY KEY (id_categoria);


--
-- TOC entry 4965 (class 2606 OID 16421)
-- Name: cliente pk_cliente; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente
    ADD CONSTRAINT pk_cliente PRIMARY KEY (rut);


--
-- TOC entry 4969 (class 2606 OID 16447)
-- Name: cliente_empresa pk_cliente_empresa; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_empresa
    ADD CONSTRAINT pk_cliente_empresa PRIMARY KEY (rut);


--
-- TOC entry 4967 (class 2606 OID 16434)
-- Name: cliente_persona pk_cliente_persona; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_persona
    ADD CONSTRAINT pk_cliente_persona PRIMARY KEY (rut);


--
-- TOC entry 4983 (class 2606 OID 16556)
-- Name: despacho pk_despacho; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.despacho
    ADD CONSTRAINT pk_despacho PRIMARY KEY (id_despacho);


--
-- TOC entry 4989 (class 2606 OID 16581)
-- Name: despacho_transportista pk_despacho_transportista; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.despacho_transportista
    ADD CONSTRAINT pk_despacho_transportista PRIMARY KEY (id_despacho);


--
-- TOC entry 4979 (class 2606 OID 16534)
-- Name: documento_tributario pk_documento_tributario; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documento_tributario
    ADD CONSTRAINT pk_documento_tributario PRIMARY KEY (id_documento);


--
-- TOC entry 4973 (class 2606 OID 16470)
-- Name: empleado pk_empleado; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.empleado
    ADD CONSTRAINT pk_empleado PRIMARY KEY (id_empleado);


--
-- TOC entry 4963 (class 2606 OID 16395)
-- Name: estado_credito pk_estado_credito; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estado_credito
    ADD CONSTRAINT pk_estado_credito PRIMARY KEY (id_estado);


--
-- TOC entry 4977 (class 2606 OID 16512)
-- Name: pedido pk_pedido; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pedido
    ADD CONSTRAINT pk_pedido PRIMARY KEY (id_pedido);


--
-- TOC entry 5001 (class 2606 OID 16646)
-- Name: pedido_contiene_producto pk_pedido_contiene_producto; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pedido_contiene_producto
    ADD CONSTRAINT pk_pedido_contiene_producto PRIMARY KEY (id_pedido, sku);


--
-- TOC entry 4993 (class 2606 OID 16608)
-- Name: producto pk_producto; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.producto
    ADD CONSTRAINT pk_producto PRIMARY KEY (sku);


--
-- TOC entry 5007 (class 2606 OID 16705)
-- Name: bodega_almacena_producto pk_producto_almacena; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bodega_almacena_producto
    ADD CONSTRAINT pk_producto_almacena PRIMARY KEY (nombre_bodega, ubicacion_bodega, sku);


--
-- TOC entry 5003 (class 2606 OID 16663)
-- Name: categoria_categoriza_producto pk_producto_categoriza; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categoria_categoriza_producto
    ADD CONSTRAINT pk_producto_categoriza PRIMARY KEY (id_categoria, sku);


--
-- TOC entry 4999 (class 2606 OID 16637)
-- Name: proveedor pk_proveedor; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.proveedor
    ADD CONSTRAINT pk_proveedor PRIMARY KEY (rut);


--
-- TOC entry 5005 (class 2606 OID 16685)
-- Name: proveedor_suministra_producto pk_proveedor_suministra; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.proveedor_suministra_producto
    ADD CONSTRAINT pk_proveedor_suministra PRIMARY KEY (rut_proveedor, sku_producto, fecha);


--
-- TOC entry 4971 (class 2606 OID 16459)
-- Name: rol pk_rol; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.rol
    ADD CONSTRAINT pk_rol PRIMARY KEY (id_rol);


--
-- TOC entry 4987 (class 2606 OID 16572)
-- Name: transportista pk_transportista; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transportista
    ADD CONSTRAINT pk_transportista PRIMARY KEY (id_transportista);


--
-- TOC entry 4985 (class 2606 OID 16558)
-- Name: despacho uq_despacho_pedido; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.despacho
    ADD CONSTRAINT uq_despacho_pedido UNIQUE (id_pedido);


--
-- TOC entry 4981 (class 2606 OID 16536)
-- Name: documento_tributario uq_documento_pedido; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documento_tributario
    ADD CONSTRAINT uq_documento_pedido UNIQUE (id_pedido);


--
-- TOC entry 5012 (class 2606 OID 16489)
-- Name: abono_credito fk_abono_cliente; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.abono_credito
    ADD CONSTRAINT fk_abono_cliente FOREIGN KEY (rut_cliente) REFERENCES public.cliente(rut);


--
-- TOC entry 5013 (class 2606 OID 16494)
-- Name: abono_credito fk_abono_empleado; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.abono_credito
    ADD CONSTRAINT fk_abono_empleado FOREIGN KEY (id_empleado) REFERENCES public.empleado(id_empleado);


--
-- TOC entry 5027 (class 2606 OID 16711)
-- Name: bodega_almacena_producto fk_bap_bodega; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bodega_almacena_producto
    ADD CONSTRAINT fk_bap_bodega FOREIGN KEY (nombre_bodega, ubicacion_bodega) REFERENCES public.bodega(nombre_bodega, ubicacion_bodega);


--
-- TOC entry 5028 (class 2606 OID 16706)
-- Name: bodega_almacena_producto fk_bap_producto; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bodega_almacena_producto
    ADD CONSTRAINT fk_bap_producto FOREIGN KEY (sku) REFERENCES public.producto(sku);


--
-- TOC entry 5023 (class 2606 OID 16669)
-- Name: categoria_categoriza_producto fk_ccp_categoria; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categoria_categoriza_producto
    ADD CONSTRAINT fk_ccp_categoria FOREIGN KEY (id_categoria) REFERENCES public.categoria(id_categoria);


--
-- TOC entry 5024 (class 2606 OID 16664)
-- Name: categoria_categoriza_producto fk_ccp_producto; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categoria_categoriza_producto
    ADD CONSTRAINT fk_ccp_producto FOREIGN KEY (sku) REFERENCES public.producto(sku);


--
-- TOC entry 5010 (class 2606 OID 16448)
-- Name: cliente_empresa fk_cliente_empresa_cliente; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_empresa
    ADD CONSTRAINT fk_cliente_empresa_cliente FOREIGN KEY (rut) REFERENCES public.cliente(rut) ON DELETE CASCADE;


--
-- TOC entry 5008 (class 2606 OID 16422)
-- Name: cliente fk_cliente_estado; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente
    ADD CONSTRAINT fk_cliente_estado FOREIGN KEY (id_estado) REFERENCES public.estado_credito(id_estado);


--
-- TOC entry 5009 (class 2606 OID 16435)
-- Name: cliente_persona fk_cliente_persona_cliente; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_persona
    ADD CONSTRAINT fk_cliente_persona_cliente FOREIGN KEY (rut) REFERENCES public.cliente(rut) ON DELETE CASCADE;


--
-- TOC entry 5018 (class 2606 OID 16559)
-- Name: despacho fk_despacho_pedido; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.despacho
    ADD CONSTRAINT fk_despacho_pedido FOREIGN KEY (id_pedido) REFERENCES public.pedido(id_pedido);


--
-- TOC entry 5016 (class 2606 OID 16542)
-- Name: documento_tributario fk_documento_empleado; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documento_tributario
    ADD CONSTRAINT fk_documento_empleado FOREIGN KEY (id_empleado) REFERENCES public.empleado(id_empleado);


--
-- TOC entry 5017 (class 2606 OID 16537)
-- Name: documento_tributario fk_documento_pedido; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documento_tributario
    ADD CONSTRAINT fk_documento_pedido FOREIGN KEY (id_pedido) REFERENCES public.pedido(id_pedido);


--
-- TOC entry 5019 (class 2606 OID 16582)
-- Name: despacho_transportista fk_dt_despacho; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.despacho_transportista
    ADD CONSTRAINT fk_dt_despacho FOREIGN KEY (id_despacho) REFERENCES public.despacho(id_despacho);


--
-- TOC entry 5020 (class 2606 OID 16587)
-- Name: despacho_transportista fk_dt_transportista; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.despacho_transportista
    ADD CONSTRAINT fk_dt_transportista FOREIGN KEY (id_transportista) REFERENCES public.transportista(id_transportista);


--
-- TOC entry 5011 (class 2606 OID 16471)
-- Name: empleado fk_empleado_rol; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.empleado
    ADD CONSTRAINT fk_empleado_rol FOREIGN KEY (id_rol) REFERENCES public.rol(id_rol);


--
-- TOC entry 5021 (class 2606 OID 16647)
-- Name: pedido_contiene_producto fk_pcp_pedido; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pedido_contiene_producto
    ADD CONSTRAINT fk_pcp_pedido FOREIGN KEY (id_pedido) REFERENCES public.pedido(id_pedido);


--
-- TOC entry 5022 (class 2606 OID 16652)
-- Name: pedido_contiene_producto fk_pcp_producto; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pedido_contiene_producto
    ADD CONSTRAINT fk_pcp_producto FOREIGN KEY (sku) REFERENCES public.producto(sku);


--
-- TOC entry 5014 (class 2606 OID 16513)
-- Name: pedido fk_pedido_cliente; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pedido
    ADD CONSTRAINT fk_pedido_cliente FOREIGN KEY (rut_cliente) REFERENCES public.cliente(rut);


--
-- TOC entry 5015 (class 2606 OID 16518)
-- Name: pedido fk_pedido_empleado; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pedido
    ADD CONSTRAINT fk_pedido_empleado FOREIGN KEY (id_empleado) REFERENCES public.empleado(id_empleado);


--
-- TOC entry 5025 (class 2606 OID 16691)
-- Name: proveedor_suministra_producto fk_psp_producto; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.proveedor_suministra_producto
    ADD CONSTRAINT fk_psp_producto FOREIGN KEY (sku_producto) REFERENCES public.producto(sku);


--
-- TOC entry 5026 (class 2606 OID 16686)
-- Name: proveedor_suministra_producto fk_psp_proveedor; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.proveedor_suministra_producto
    ADD CONSTRAINT fk_psp_proveedor FOREIGN KEY (rut_proveedor) REFERENCES public.proveedor(rut);


-- Completed on 2026-07-11 12:18:39

--
-- PostgreSQL database dump complete
--

\unrestrict 2vh32p7vSmzANyRzROv3dG943JLq0udbVeMkL3tZKNPGS5aJD3PyPsoVvQYXVGQ

