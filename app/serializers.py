from rest_framework import  serializers
from .models import *


class DownloadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SapDownloading
        fields = "__all__"

class SapSerializer(serializers.ModelSerializer):
    class Meta:
        model = SAPConfig
        fields = "__all__"