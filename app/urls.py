"""
URL configuration for app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    # Put more specific patterns first
    path('record/create/', views.create_record_type, name='create_record_type'),
    path('record/<str:record_type>/edit/', views.edit_record_type, name='edit_record_type'),
    path('record/<str:record_type>/delete/', views.delete_record_type, name='delete_record_type'),
    path('record/<str:record_type>/stages/', views.edit_stages, name='edit_stages'),
    path('record/<str:record_type>/fields/new/', views.new_custom_field, name='new_custom_field'),
    path('record/<str:record_type>/fields/<str:field_name>/edit/', views.edit_custom_field, name='edit_custom_field'),
    path('record/<str:record_type>/core-fields/<str:field_name>/edit/', views.edit_core_field, name='edit_core_field'),
    path('record/<str:record_type>/roles/add/', views.add_role, name='add_role'),
    path('record/<str:record_type>/roles/<int:role_id>/edit/', views.edit_role, name='edit_role'),
    # Put the catch-all record_type pattern last
    path('record/<str:record_type>/', views.record_fields, name='record_fields'),
]
