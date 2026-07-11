from django.contrib import admin
from django.db import models as dj_models

from . import models as app_models


for model in app_models.__dict__.values():
	if (
		isinstance(model, type)
		and issubclass(model, dj_models.Model)
		and model._meta.app_label == 'myapp'
		and not model._meta.abstract
		and model._meta.pk.__class__.__name__ != 'CompositePrimaryKey'
	):
		admin.site.register(model)
