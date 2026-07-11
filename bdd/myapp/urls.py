from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('clientes/', views.clientes_list, name='clientes-list'),
    path('clientes/nuevo/', views.cliente_create, name='cliente-create'),
    path('clientes/<str:rut>/', views.cliente_detail, name='cliente-detail'),
    path('pedidos/', views.pedidos_list, name='pedidos-list'),
    path('pedidos/nuevo/', views.pedido_create, name='pedido-create'),
    path('pedidos/<int:id_pedido>/', views.pedido_detail, name='pedido-detail'),
    path('abonos/', views.abonos_list, name='abonos-list'),
    path('alertas/', views.alertas_credito, name='alertas-credito'),
    path('reportes/', views.reportes, name='reportes'),
    path('productos/', views.productos_list, name='productos-list'),
    path('productos/nuevo/', views.producto_create, name='producto-create'),
    path('productos/<str:sku>/', views.productos_detail, name='productos-detail'),
    path('browse/<str:model_name>/', views.model_list, name='model-list'),
    path('browse/<str:model_name>/<str:token>/', views.model_detail, name='model-detail'),
]