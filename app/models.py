from django.db import models
import uuid
from django.contrib.auth.models import User
# Create your models here.
ASHOST='172.21.72.21'
CLIENT='100'
SYSNR='00'
USER='STUDENT036'
PASSWD='Mathew123@'
saprouter='/H/161.38.17.212'
def get_unique_id():
    return uuid.uuid4()
class SAPConfig(models.Model):
    django_user = models.ForeignKey(User,on_delete=models.CASCADE,null=True,blank=True)
    ASHOST = models.CharField(max_length=255)
    CLIENT = models.CharField(max_length=255)
    SYSNR = models.CharField(max_length=255)
    USER = models.CharField(max_length=255)
    PASSWD = models.CharField(max_length=255)
    saprouter = models.CharField(max_length=255)
    def __str__(self) -> str:
        return f"{self.ASHOST}-{self.USER}"
table_status = (
    ("InProgress","InProgress"),
     ("Completed","Completed"),
     ("Error","Error"),

)
class SapDownloading(models.Model):
    downloading_id = models.UUIDField(default=get_unique_id,max_length=255)
    status = models.CharField(choices=table_status,default="InProgress",max_length=255)
    total_rows = models.IntegerField(default=0)
    fetched_rows = models.IntegerField(default=0)
    fetched_cols = models.IntegerField(default=0)
    table_name = models.CharField(max_length=255)
    number_of_column = models.IntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.table_name}-{self.status}-{self.fetched_rows}"

    
