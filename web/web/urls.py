"""web URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
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
from django.urls import include, path, register_converter

from . import views


class MD5Converter:
    regex = '.*[0-9a-zA-Z]{32}'

    def to_python(self, value):
        return str(value)

    def to_url(self, value):
        return str(value)


register_converter(MD5Converter, 'md5')

urlpatterns = [
    path('<md5:path>', views.md5log)
]
