import datetime
import math
import os
import shutil
from django.shortcuts import render, redirect
import mimetypes

from rest_framework.response import Response
from .models import *
from django.http import FileResponse, JsonResponse
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
COL_BATCH_SIZE = 50


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
            file_type = FileExtentions.objects.filter().first()
            file = SapDownloading.objects.create(fetched_rows=0,table_name=table,file_type=file_type)
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
class  FThread(Thread):
    def __init__(self,col,total_cols,total_rows,table:SapDownloading,fields_list,configurations,thread_id):
        super().__init__()
        self._result = []
        self.table =table
        self.total_cols =total_cols
        self.col =col
        self.configurations=configurations
        self.total_rows=total_rows
        self.fields_list=fields_list
        self.thread_id = thread_id
        self._result = []
    
        
        


    def run(self):
        print(f"Thread start:{self.thread_id}")
        table = self.table
        total_cols = self.total_cols
        col = self.col
        configurations= self.configurations
        total_rows= self.total_rows
        fields_list=self.fields_list
        thread_id = self.thread_id
        
        print(total_cols,total_rows,thread_id)
        conn = None
        data = []
        col_batch_size = COL_BATCH_SIZE
        self.rows = []
        from_cols = col
        col_read = col
        if col+col_batch_size > total_cols:
            col_batch_size = total_cols - col
    
        col = col_batch_size+col
        while col_read < total_cols:
            cols = fields_list[col_read:col]
            try:
                
                s_t = time.time()
                result = conn.call('BBP_RFC_READ_TABLE', QUERY_TABLE=table.table_name, DELIMITER='|', ROWSKIPS=0, ROWCOUNT=total_rows,FIELDS=cols)
                e_t = time.time()
            except Exception as ex:

                if type(ex) == ABAPApplicationError and ex.key == 'DATA_BUFFER_EXCEEDED':
                    col = col - col_batch_size
                    col_batch_size = int(col_batch_size * 0.9)
                    col = col+col_batch_size
                    continue
                try:
                    conn = Connection(ashost=configurations.ASHOST, sysnr=configurations.SYSNR, user=configurations.USER, passwd=configurations.PASSWD,saprouter=configurations.saprouter)
                except:
                    time.sleep(1)
                    continue
                continue
            #print(f"\n Thread{thread_id},cols_readed:{col_read},Total:{len(fields_list)},Total Rows:{total_rows},,Col size:{col}")
            
            if len(result['DATA']) == 0:
                break
            _data = result["DATA"]
            
            if not self.rows:
                self.rows.extend(_data)
                #168,175
                #
            else:
                merging=time.time()
                for r in range(len(self.rows)):
                    d = _data[r].get("WA")
                    ro = self.rows[r].get("WA")
                    self.rows[r]={"WA": ro+"|"+d }
                #print(f"mering take time {time.time()- merging}",f"Query time {e_t-s_t}")
            col_read = col
            table.fetched_cols += total_cols - col_read
            table.save()
            if col+col_batch_size > total_cols:
                col_batch_size = total_cols - col
            col = col+col_batch_size
        

        #print(f"{len(self.rows)} number of rows are found from thread {thread_id}")

        self._result = self.rows
        self.rows = None
        return self._result
    def result(self):
       
        return self._result
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
        threads = []
        result = conn.call("EM_GET_NUMBER_OF_ENTRIES", IT_TABLES=[{"TABNAME": table.table_name}])
        total_rows = result["IT_TABLES"][0]["TABROWS"]
        field_info = conn.call('DDIF_FIELDINFO_GET', TABNAME=table.table_name)
        fields_list = [field['FIELDNAME'] for field in field_info['DFIES_TAB']]
        table.total_rows=total_rows
        table.fetched_rows=0
        table.number_of_column=len(fields_list)
        table.success_message = f"{table.table_name} table have {total_rows} rows and {len(fields_list)} columns"
        table.save()
        COL_BATCH_SIZE = 50
        print(f"{table.table_name} table have {total_rows} rows and {len(fields_list)} columns")
        if COL_BATCH_SIZE > len(fields_list):
                COL_BATCH_SIZE = len(fields_list)
        col = 0
        number_of_column =  len(fields_list)
        number_of_threads = int(math.ceil((number_of_column) / COL_BATCH_SIZE))
        for thread in range(number_of_threads):
            if col + COL_BATCH_SIZE > number_of_column:
                thread_total_cols = number_of_column
            else:
                thread_total_cols = col + COL_BATCH_SIZE
            thread_t = FThread(col,thread_total_cols,total_rows,table,fields_list,conf,thread)
            thread_t.start()
            threads.append(thread_t)
            print(col,thread_total_cols,total_rows,conf)
            if col+ COL_BATCH_SIZE > len(fields_list):
                COL_BATCH_SIZE = len(fields_list) - col
            col = col+COL_BATCH_SIZE
            
        time.sleep(1)
        temp_folder =f"{table}_{table.downloading_id}_temp_files"
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
        file_names = []
        for thread in threads:
            thread.join()
            thread_data=thread.result()
            thread._result = None
            file_name =f'{temp_folder}/{table}_{thread.thread_id}.txt'
            rows = [row['WA'].split('|') for row in thread_data]
            with open(file_name, 'w',encoding='utf-8') as f:
                f.writelines([table.file_type.separator.join(row) + '\n' for row in rows])
            file_names.append(file_name)
            thread_data = []
        
        files = [open(file_name, 'r',encoding='utf-8') for file_name in file_names]
        file_path = f'media/{table.table_name}-{table.downloading_id}.txt'
        output = open(file_path, 'w',encoding='utf-8')
        output.write(table.file_type.separator.join([field for field in fields_list]) + '\n')
        row_index = 0
        time.sleep(1)
        start_mergin_time = time.time()
        while True:
            merged_row = ''
            for file in files:
                line = file.readline().strip()
                if not line:
                    break
                merged_row += line + table.file_type.separator
        
            if not merged_row:
                break
            output.write(merged_row[:-1] + '\n')
            row_index +=1
        if time.time() - start_mergin_time > 1:
            start_mergin_time = time.time()
            t=Thread(target=update_table,args=(table,row_index))
            t.daemon = True
            t.start()

        for file in files:
            file.close()

        output.close()
        print(f"Merged file '{file_path}' has been created.")
        try:
            shutil.rmtree(temp_folder, ignore_errors=False, onerror=None)
        except:
            pass
        table.status = "validate"
        table.save()
        
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
def update_table(table:SapDownloading,row_index):
    table.fetched_rows = row_index
    table.save()
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

def download_file(request, uuid):
    # Retrieve the file object based on the UUID
    file_obj = SapDownloading.objects.filter(downloading_id=uuid).first()
    if not file_obj:
        messages.add_message(request, messages.SUCCESS, "Invalid file id")
        return redirect('/')

    if not os.path.exists(file_obj.file_path):
        messages.add_message(request, messages.SUCCESS, "File not found")
        return redirect('/')

    content_type, _ = mimetypes.guess_type(file_obj.file_path)
    if not content_type:
        content_type = 'application/octet-stream'
    response = FileResponse(open(file_obj.file_path, 'rb'), content_type=content_type)

    # Set the Content-Disposition header to force a download
    response['Content-Disposition'] = f'attachment; filename="{file_obj.table_name}-{file_obj.downloading_id}.{file_obj.file_type.extension}"'

    # Set the Content-Length header
    response['Content-Length'] = os.path.getsize(file_obj.file_path)

    return response