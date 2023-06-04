

from django.urls import path,include
from .views import *
urlpatterns = [
    path("",home,name="home"),
    path("/<uuid:id>/",home,name="home"),
    path("get_file_status/<uuid:id>/",get_file_status,name="get_file_status"),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='register'),
    path('add/', add_view, name='add_view'),
    path('edit_conf/<str:pk>/', edit_view, name='edit_conf_view'),
    path('get_configurations/<str:pk>/', get_configurations, name='get_view'),
    path('delete_configurations/<str:pk>/', delete_configurations, name='delete_view'),

    path('stop_downloading/<str:pk>/', stop_downloading, name='stop_view'),
    path('download/<str:uuid>/', download_file, name='download_view'),

]



