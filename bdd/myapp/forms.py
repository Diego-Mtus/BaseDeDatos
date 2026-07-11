from django import forms
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.forms import BaseFormSet, formset_factory

from .models import AbonoCredito, Bodega, Categoria, Cliente, Empleado, Pedido, Producto


class ClienteChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        try:
            persona = obj.clientepersona
            nombre = f"{persona.nombre} {persona.apellido}"
        except ObjectDoesNotExist:
            try:
                empresa = obj.clienteempresa
                nombre = empresa.razon_social
            except ObjectDoesNotExist:
                nombre = obj.rut
        return f"{nombre} ({obj.rut})"

class BodegaChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        # Como no hay un ID numérico, mostramos ambos campos de la clave compuesta
        return f"{obj.nombre_bodega} ({obj.ubicacion_bodega})"

class EmpleadoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.nombre} {obj.apellido} (ID {obj.id_empleado})"


class ProductoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.sku} - {obj.nombre}"


class CategoriaChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.nombre



class ProductoForm(forms.ModelForm):
    sku = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="SKU",
    )
    nombre = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Nombre",
    )
    precio = forms.IntegerField(
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        label="Precio",
    )
    es_granel = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Es a granel",
    )
    categorias = CategoriaChoiceField(
        queryset=Categoria.objects.all().order_by("nombre"),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-control"}),
        label="Categorías",
    )

    # NUEVOS CAMPOS AÑADIDOS PARA EL CONTROL DE STOCK
    id_bodega = forms.ChoiceField(
        choices=[],  # Se llena dinámicamente en el __init__
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Bodega de Destino (Origen)",
        error_messages={'required': 'Debe seleccionar una bodega para asignar el stock.'}
    )
    
    cantidad_stock = forms.DecimalField(
        max_digits=10,
        decimal_places=3,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.001", "placeholder": "0.000"}),
        label="Cantidad de Stock a Ingresar",
    )

    class Meta:
        model = Producto
        fields = ["sku", "nombre", "precio", "es_granel", "categorias"]

    # Constructor para cargar las bodegas dinámicamente usando su clave compuesta como identificador
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Creamos los choices usando "nombre_bodega|ubicacion_bodega" como el valor único del value=""
        self.fields['id_bodega'].choices = [
            (f"{b.nombre_bodega}|{b.ubicacion_bodega}", f"{b.nombre_bodega} ({b.ubicacion_bodega})")
            for b in Bodega.objects.all().order_by("nombre_bodega")
        ]

    def clean_cantidad_stock(self):
        cantidad = self.cleaned_data.get("cantidad_stock")
        if cantidad is not None and cantidad < 0:
            raise forms.ValidationError("La cantidad de stock no puede ser un valor negativo.")
        return cantidad

class ClienteCreateForm(forms.ModelForm):
    # CONSTANTES QUE TU VISTA (`views.py`) ESTÁ BUSCANDO:
    TIPO_PERSONA = 'persona'
    TIPO_EMPRESA = 'empresa'

    tipo_cliente = forms.ChoiceField(
        choices=[(TIPO_PERSONA, "Persona Natural"), (TIPO_EMPRESA, "Empresa")],
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Tipo de Cliente",
        error_messages={'required': 'Este campo es obligatorio.'}
    )

    # Campos de Persona
    nombre = forms.CharField(
        max_length=30, 
        required=False, 
        widget=forms.TextInput(attrs={"class": "form-control"}),
        error_messages={'required': 'Este campo es obligatorio.'}
    )
    apellido = forms.CharField(
        max_length=30, 
        required=False, 
        widget=forms.TextInput(attrs={"class": "form-control"}),
        error_messages={'required': 'Este campo es obligatorio.'}
    )

    # Campos de Empresa
    razon_social = forms.CharField(
        max_length=50, 
        required=False, 
        widget=forms.TextInput(attrs={"class": "form-control"}),
        error_messages={'required': 'Este campo es obligatorio.'}
    )
    giro = forms.CharField(
        max_length=30, 
        required=False, 
        widget=forms.TextInput(attrs={"class": "form-control"}),
        error_messages={'required': 'Este campo es obligatorio.'}
    )

    class Meta:
        model = Cliente
        fields = ["rut", "fono_contacto", "email", "limite_credito", "saldo_deudor", "fecha_limite", "id_estado"]
        widgets = {
            "rut": forms.TextInput(attrs={"class": "form-control", "placeholder": "ej: 12.345.678-K"}),
            "fono_contacto": forms.NumberInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "limite_credito": forms.NumberInput(attrs={"class": "form-control"}),
            "saldo_deudor": forms.NumberInput(attrs={"class": "form-control"}),
            "fecha_limite": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "id_estado": forms.Select(attrs={"class": "form-control"}),
        }
        error_messages = {
            'rut': {'required': 'Este campo es obligatorio.'},
            'fono_contacto': {'required': 'Este campo es obligatorio.'},
            'email': {'required': 'Este campo es obligatorio.'},
            'limite_credito': {'required': 'Este campo es obligatorio.'},
            'saldo_deudor': {'required': 'Este campo es obligatorio.'},
            'fecha_limite': {'required': 'Este campo es obligatorio.'},
            'id_estado': {'required': 'Este campo es obligatorio.'},
        }

    # ==========================================
    # VALIDACIÓN DEL RUT CHILENO (Algoritmo Módulo 11)
    # ==========================================
    def clean_rut(self):
        rut_raw = self.cleaned_data.get("rut")
        if not rut_raw:
            return rut_raw

        rut_limpio = rut_raw.strip().upper()
        rut_solo_numeros = rut_limpio.replace(".", "").replace("-", "")

        if len(rut_solo_numeros) < 8 or len(rut_solo_numeros) > 9:
            raise forms.ValidationError("El RUT no tiene un largo válido.")

        cuerpo = rut_solo_numeros[:-1]
        dv = rut_solo_numeros[-1]

        if not cuerpo.isdigit():
            raise forms.ValidationError("El cuerpo del RUT debe contener solo números.")

        suma = 0
        multiplicador = 2
        for c in reversed(cuerpo):
            suma += int(c) * multiplicador
            multiplicador = 2 if multiplicador == 7 else multiplicador + 1

        dvr = 11 - (suma % 11)
        if dvr == 11:
            dv_esperado = "0"
        elif dvr == 10:
            dv_esperado = "K"
        else:
            dv_esperado = str(dvr)

        if dv != dv_esperado:
            raise forms.ValidationError("El RUT ingresado no es válido (Dígito verificador incorrecto).")

        cuerpo_int = int(cuerpo)
        rut_formateado = f"{cuerpo_int:,}- {dv}".replace(",", ".")
        rut_formateado = rut_formateado.replace("- ", "-")
        
        return rut_formateado

    # ==========================================
    # VALIDACIONES DE CONSTRAINTS (CHECK)
    # ==========================================
    def clean_fono_contacto(self):
        fono = self.cleaned_data.get("fono_contacto")
        if fono is not None:
            if fono < 10000000 or fono > 999999999:
                raise forms.ValidationError(
                    "El número telefónico debe tener entre 8 y 9 dígitos (ej: 912345678 o 22345678)."
                )
        return fono

    def clean_limite_credito(self):
        limite = self.cleaned_data.get("limite_credito")
        if limite is not None and limite < 0:
            raise forms.ValidationError("El límite de crédito no puede ser un valor negative.")
        return limite

    def clean_saldo_deudor(self):
        saldo = self.cleaned_data.get("saldo_deudor")
        if saldo is not None and saldo < 0:
            raise forms.ValidationError("El saldo deudor no puede ser un valor negativo.")
        return saldo

    # ==========================================
    # VALIDACIÓN GENERAL (PERSONA VS EMPRESA)
    # ==========================================
    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get("tipo_cliente")

        if tipo == "persona":
            if not cleaned_data.get("nombre"):
                self.add_error("nombre", "El nombre es obligatorio para personas naturales.")
            if not cleaned_data.get("apellido"):
                self.add_error("apellido", "El apellido es obligatorio para personas naturales.")
        elif tipo == "empresa":
            if not cleaned_data.get("razon_social"):
                self.add_error("razon_social", "La razón social es obligatoria para empresas.")
            if not cleaned_data.get("giro"):
                self.add_error("giro", "El giro es obligatorio para empresas.")

        return cleaned_data


class AbonoCreditoForm(forms.ModelForm):
    rut_cliente = ClienteChoiceField(
        queryset=Cliente.objects.select_related("clientepersona", "clienteempresa").all().order_by("rut"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    id_empleado = EmpleadoChoiceField(
        queryset=Empleado.objects.all().order_by("nombre", "apellido"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    metodo_pago = forms.ChoiceField(
        choices=(
            ("Efectivo", "Efectivo"),
            ("Transferencia", "Transferencia"),
            ("Tarjeta", "Tarjeta"),
            ("Cheque", "Cheque"),
        ),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Método de pago",
    )

    class Meta:
        model = AbonoCredito
        fields = ["rut_cliente", "monto", "metodo_pago", "id_empleado"]
        widgets = {
            "monto": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }


class PedidoCreateForm(forms.Form):
    rut_cliente = ClienteChoiceField(
        queryset=Cliente.objects.select_related("clientepersona", "clienteempresa").all().order_by("rut"),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Cliente",
    )
    id_empleado = EmpleadoChoiceField(
        queryset=Empleado.objects.all().order_by("nombre", "apellido"),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Empleado",
    )
    es_credito = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}), label="Es crédito")
    estado = forms.ChoiceField(
        choices=(
            ("pendiente", "Pendiente / En proceso"),
            ("aprobado", "Aprobado"),
            ("anulado", "Anulado"),
        ),
        initial="pendiente",
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Estado",
    )


class PedidoLineaForm(forms.Form):
    sku = ProductoChoiceField(
        queryset=Producto.objects.all().order_by("nombre"),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Producto",
        required=False,
    )
    cantidad = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=3,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.001", "min": 0}),
        label="Cantidad",
    )


class BasePedidoLineaFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        al_menos_una_linea = False

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            sku = form.cleaned_data.get("sku")
            cantidad = form.cleaned_data.get("cantidad")

            if sku or cantidad:
                al_menos_una_linea = True
                if not sku:
                    raise ValidationError("Cada línea debe tener un producto si se completa la cantidad.")
                if not cantidad:
                    raise ValidationError("Cada línea debe tener una cantidad si se selecciona un producto.")

        if not al_menos_una_linea:
            raise ValidationError("Agrega al menos un producto al pedido.")


PedidoLineaFormSet = formset_factory(PedidoLineaForm, formset=BasePedidoLineaFormSet, extra=1, can_delete=False, max_num=10)