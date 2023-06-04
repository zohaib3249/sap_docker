import datetime
from django.shortcuts import render, redirect


from rest_framework.response import Response
from .models import *
from django.http import JsonResponse
import multiprocessing

# Create your views here.
from pyrfc import Connection, ABAPApplicationError, ABAPRuntimeError, LogonError, CommunicationError
from configparser import ConfigParser
import time
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from threading import Thread
from django.contrib.auth import authenticate, login, logout
from .forms import UserLoginForm, UserRegistrationForm
from django.contrib import messages
from .forms import *
from celery import shared_task
from django.contrib.auth.decorators import login_required



from .serializers import *
@login_required(login_url='/login') #redirect when user is not logged in

def home(request,id=None):
    form = SapConfigurationFORM()
    edit_form = SapConfigurationEditFORM()
    configurations = SAPConfig.objects.filter(django_user=request.user)
    file = None

    if request.method == "POST":
        table = request.POST.get("table")
        selected_configuration = request.POST.get("selected_configuration")
        conf =SAPConfig.objects.filter(id=selected_configuration if selected_configuration else 0).first()
        if table and conf:
            table = table.upper()
            file = SapDownloading.objects.create(fetched_rows=0,table_name=table)
            t = Thread(target=Download_table,args=(conf,file))
            t.daemon = True
            t.start()
            messages.add_message(request, messages.SUCCESS, "Fetching Data has been started")
            return redirect ("home",id=file.downloading_id)
        else:
            if not file:
                messages.add_message(request, messages.ERROR, "invalid Configuration")
            else:
                messages.add_message(request, messages.ERROR, "Table name required")
    
    return render(request,"home.html",{"process_id":file.downloading_id if file else id,"configurations":configurations,"form":form,'edit_form':edit_form})
def merge_columns(data, split_data,lock):
    with lock:
        for r in range(len(data)):
            d = split_data[r].get("WA")
            ro = data[r].get("WA")
            data[r] = {"WA": ro + d}
    return data
@shared_task
def Download_table(conf,table:SapDownloading):

    try:
        conn = Connection(ashost=conf.ASHOST, sysnr=conf.SYSNR, user=conf.USER, passwd=conf.PASSWD,saprouter=conf.saprouter if conf.saprouter else "")
    except CommunicationError:
        table.error_message = "Could not connect to server"
        table.status = "Error"
        table.save()
        print("Could not connect to server.")
    except LogonError:
        table.error_message = "Could not log in. Wrong credentials."
        table.status = "Error"
        table.save()
        print("Could not log in. Wrong credentials?")
    except (ABAPApplicationError, ABAPRuntimeError):
       
        table.error_message = "An error occurred."
        table.status = "Error"
        table.save()
    except:
        table.success_message = f"Connection problem please add valid configuration"
        table.status = "Error"
        table.save()
        return
    start = time.time()
    try:
        data = []
        col_batch_size = 70
        
        result = conn.call("EM_GET_NUMBER_OF_ENTRIES", IT_TABLES=[{"TABNAME": table.table_name}])
        total_rows = result["IT_TABLES"][0]["TABROWS"]
        field_info = conn.call('DDIF_FIELDINFO_GET', TABNAME=table.table_name)
        fields_list = [field['FIELDNAME'] for field in field_info['DFIES_TAB']]
        table.total_rows=total_rows
        table.fetched_rows=0
        table.number_of_column=len(fields_list)
        table.success_message = f"{table.table_name} table have {total_rows} rows and {len(fields_list)} columns"
        table.save()
        print(f"{table.table_name} table have {total_rows} rows and {len(fields_list)} columns")
        data = []
        col_read = 0
        col = col_batch_size
        row = 0
        print("Reading start",datetime.datetime.now())
        lock = multiprocessing.Lock()
        manager = multiprocessing.Manager()
        merged_data = manager.list()
        while col_read < len(fields_list) and not table.is_stopped:
            cols = fields_list[col_read:col]
            try:
                s_t = time.time()
                result = conn.call('BBP_RFC_READ_TABLE', QUERY_TABLE=table.table_name, DELIMITER='|', ROWSKIPS=row, ROWCOUNT=total_rows,FIELDS=cols)
                e_t = time.time()
            except Exception as ex:
                if type(ex) == ABAPApplicationError and ex.key == 'DATA_BUFFER_EXCEEDED':
                    col = col - col_batch_size
                    col_batch_size = int(col_batch_size * 0.9)
                    col = col+col_batch_size
                    continue
                try:
                    conn = Connection(ashost=conf.ASHOST, sysnr=conf.SYSNR, user=conf.USER, passwd=conf.PASSWD,saprouter=conf.saprouter if conf.saprouter else "")
                except:
                    pass
                continue
            print(col,":Time",(e_t-s_t))
            if len(result['DATA']) == 0:
                break
            _data = result["DATA"]
            if not data:
                data.extend(_data)
            else:
                merging=time.time()
                for r in range(len(data)):
                    d = _data[r].get("WA")
                    ro = data[r].get("WA")
                    data[r]={"WA": ro+"|"+d }
                print(f"mering take time {time.time()- merging}",f"Query time {e_t-s_t}")
               
            col_read = col
            table.fetched_cols = col_read
            table.save()
            if col+col_batch_size > len(fields_list):
                col_batch_size = len(fields_list) - col
            col = col+col_batch_size
        print("waiting for pool")
        
        print("pool clear")
        table.status = "validate"
        table.save()
        file_path = f'media/{table.table_name}-{table.downloading_id}.txt'
        with open(file_path, 'w',encoding="utf-8") as f:
            f.write('|'.join([field for field in fields_list]) + '\n')
            for index , _row in enumerate(data):
                f.writelines(_row['WA'])
                f.writelines("\n")
        
        table.file_path = file_path
        table.status = "Completed"
        table.save()
    except CommunicationError:
        table.error_message = "Could not connect to server"
        table.status = "Error"
        table.save()
        print("Could not connect to server.")
    except LogonError:
        table.error_message = "Could not log in. Wrong credentials."
        table.status = "Error"
        table.save()
        print("Could not log in. Wrong credentials?")
    except (ABAPApplicationError, ABAPRuntimeError):
        table.error_message = "An error occurred."
        table.status = "Error"
        table.save()
    except Exception as ex:
        print(ex)
        table.error_message = "Something went wrong"
        table.status = "Error"
        table.save()
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
    

def login_view(request):
    if request.method == 'POST':
        login_form = UserLoginForm(request.POST)
        register_form = UserRegistrationForm()
        if login_form.is_valid():
            username = login_form.cleaned_data['username']
            password = login_form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.add_message(request, messages.SUCCESS, "Login successfully")
                return redirect('home')  # Replace 'home' with your desired homepage URL
            else:
                messages.add_message(request, messages.ERROR, "Invalid username or password")
        messages.add_message(request, messages.ERROR, "User and password are required")
    else:
        
        register_form = UserRegistrationForm()
        login_form = UserLoginForm()
    return render(request, 'login.html', {'login_form': login_form,'register_form':register_form,"page_link":"login"})


def register_view(request):
    login_form = UserLoginForm()
    


    if request.method == 'POST':
        
        register_form = UserRegistrationForm(request.POST)
        if register_form.is_valid():
            register_form.save()
            messages.add_message(request, messages.SUCCESS, "Your account has been created")
            return redirect('login')
        else:
            messages.add_message(request, messages.ERROR, "Got some errors please check")
    else:
        register_form = UserRegistrationForm()
    return render(request, 'login.html', {'login_form': login_form,'register_form':register_form,"page_link":"register"})

def logout_view(request):
    logout(request)
    messages.add_message(request, messages.INFO, "You are logout successfully")
    return redirect('login')

def add_view(request):
    
    if request.method == 'POST':
        form = SapConfigurationFORM(request.POST)
        
        if form.is_valid():
            obj = form.save()
            obj.django_user=request.user
            obj.save()
            messages.add_message(request, messages.SUCCESS, "Configuration saved")
            return redirect('/') 
        messages.add_message(request, messages.ERROR, "Ops got some errors")
    else:
        form = SapConfigurationFORM()
    
    return render(request, 'add_template.html', {'form': form})

def edit_view(request, pk):
    instance = SAPConfig.objects.get(pk=pk)
    print(instance)
    if request.method == 'POST':
        form = SapConfigurationEditFORM(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.add_message(request, messages.SUCCESS, "Configuration Edited")
            return redirect('/')
        else:
            messages.add_message(request, messages.ERROR, "Ops got some errors")
    else:
        form = SapConfigurationEditFORM(instance=instance)
    
    return render(request, 'edit_template.html', {'form': form})

@api_view(('GET',))
@renderer_classes((TemplateHTMLRenderer, JSONRenderer))
def get_configurations(request,pk):
    file = SAPConfig.objects.filter(id=pk).first()
    if file:
        data = SapSerializer(file).data
        return JsonResponse(data)
    else:
        return JsonResponse({"message":"Wrong file id"},template_name='assessments.html')
    

def delete_configurations(request,pk):
    file = SAPConfig.objects.filter(id=pk).first()
    if file:
        file.delete()
        messages.add_message(request, messages.SUCCESS, "Configuration has been deleted")
    else:
        messages.add_message(request, messages.ERROR, "Unable to find configuration")
    return redirect('/')
    
def stop_downloading(request,pk):
    file =  SapDownloading.objects.filter(downloading_id=pk).first()
    if file:
        file.is_stopped = True
        file.save()
        messages.add_message(request, messages.SUCCESS, "Table data fetching stopped")
    else:
        messages.add_message(request, messages.ERROR, "Unable to stop process")
    return redirect('/')