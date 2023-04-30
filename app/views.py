from django.shortcuts import render

from rest_framework.response import Response
from .models import *
from django.http import JsonResponse

# Create your views here.
from pyrfc import Connection, ABAPApplicationError, ABAPRuntimeError, LogonError, CommunicationError
from configparser import ConfigParser
import time
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from threading import Thread

from .serializers import *
def home(request):
    conf = SAPConfig.objects.all().first()
    table = request.POST.get("table")
    res = {}
    if table and conf:
        table = table.upper()
        file = SapDownloading.objects.create(fetched_rows=0,table_name=table)
        t = Thread(target=Download_table,args=(conf,file))
        t.daemon = True
        t.start()
        
        res = {"message":"Data Fetching start","table_id":file.downloading_id}
    else:
        res = {"message":"conf and table name is required"}
    return render(request,"home.html",res)

def Download_table(conf,table:SapDownloading):
    
    conn = Connection(ashost=conf.ASHOST, sysnr=conf.SYSNR, user=conf.USER, passwd=conf.PASSWD,saprouter=conf.saprouter if conf.saprouter else "")
    start = time.time()
    try:
        data = []
        batch_size = 1000
        col_batch_size = 20
        
        result = conn.call("EM_GET_NUMBER_OF_ENTRIES", IT_TABLES=[{"TABNAME": table.table_name}])
        total_rows = result["IT_TABLES"][0]["TABROWS"]
        field_info = conn.call('DDIF_FIELDINFO_GET', TABNAME=table.table_name)
        fields_list = [field['FIELDNAME'] for field in field_info['DFIES_TAB']]
        table.total_rows=total_rows
        table.fetched_rows=0
        table.number_of_column=len(fields_list)
        table.save()
        print(f"{table.table_name} table have {total_rows} rows and {len(fields_list)} columns")
        for row in range(0,total_rows,batch_size):
            rows = []
            col_read = 0
            for col in range(col_batch_size,len(fields_list),col_batch_size):
                cols = fields_list[col_read:col]
                col_read = col
                result = conn.call('RFC_READ_TABLE', QUERY_TABLE=table.table_name, DELIMITER='|', ROWSKIPS=row, ROWCOUNT=batch_size,FIELDS=cols)
                table.fetched_cols = col_read
                table.save()
                if len(result['DATA']) == 0:
                    break
                _data = result["DATA"]
                if not rows:
                    rows.extend(_data)
                else:
                    for r in range(len(rows)):
                        d = _data[r].get("WA")
                        ro = rows[r].get("WA")
                        rows[r]={"WA": ro+d }
           
            data.extend(rows)
            table.fetched_rows = len(data)
            table.save()
        table.status = "Completed"
        table.save()
        rows = [row['WA'].split('|') for row in data]
        with open(f'media/{table.table_name}-{table.downloading_id}.txt', 'w') as f:
            f.write('|'.join([field for field in fields_list]) + '\n')
            f.writelines(['|'.join(row) + '\n' for row in rows])
    except CommunicationError:
        table.status = "Error"
        table.save()
        print("Could not connect to server.")
        raise
    except LogonError:
        table.status = "Error"
        table.save()
        print("Could not log in. Wrong credentials?")
        raise
    except (ABAPApplicationError, ABAPRuntimeError):
        table.status = "Error"
        table.save()
        print("An error occurred.")
        raise
    end = time.time()
    total = end - start
    print(f"Total time:{round(total,2)}s",)

@api_view(('GET',))
@renderer_classes((TemplateHTMLRenderer, JSONRenderer))
def get_file_status(request,id):
    print(id)
    file = SapDownloading.objects.filter(downloading_id=id).first()
    if file:
        data = DownloadingSerializer(file).data
        return JsonResponse(data)
    else:
        return JsonResponse({"message":"Wrong file id"},template_name='assessments.html')