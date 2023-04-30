

from django.urls import path,include
from .views import *
urlpatterns = [
    path("",home,name="home"),
    path("get_file_status/<uuid:id>",get_file_status,name="get_file_status")
]
