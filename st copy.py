from pathlib import Path
from sap_setup import django_setup
django_setup()
import os
import streamlit as st
from pyrfc import Connection, ABAPApplicationError, ABAPRuntimeError, LogonError, CommunicationError
import pandas as pd
import time
import streamlit as st
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
root.wm_attributes('-topmost', 1)

LOGIN_CREDENTIALS = {"username": "admin", "password": "admin"}

from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from app.models import *


def register():
    st.write("# Register")
    username = st.text_input(label="Username",key="_Username")
    email = st.text_input(label="Email",key="_Email")
    password = st.text_input(label="Password", type="password",key="_password")
    if st.button(label="Register",key="_Register"):
        if username and email and password:
            user = User.objects.create_user(username=username,email=email)
            
            user.set_password(password)
            user.save()
            st.success("Your account has been created,Please login")
            
        else:
            st.error("Invalid username or password")

def login():
    st.write("# Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):

        if authenticate(username=username,password=password):
            user = User.objects.get(username=username)
            st.session_state.user=user
           
            show_app_interface()
        else:
            st.error("Invalid username or password")


def gt_data_from_sap(table,conn):
    start = time.time()
    try:
        data = []
        batch_size = 1000
        col_batch_size = 20
        with st.spinner("Fetching data..."):
            result = conn.call("EM_GET_NUMBER_OF_ENTRIES", IT_TABLES=[{"TABNAME": table}])
            total_rows = result["IT_TABLES"][0]["TABROWS"]
            field_info = conn.call('DDIF_FIELDINFO_GET', TABNAME=table)
            fields_list = [field['FIELDNAME'] for field in field_info['DFIES_TAB']]
            print(f"{table} table have {total_rows} rows and {len(fields_list)} columns")
            st.write(f"{table} table have {total_rows} rows and {len(fields_list)} columns")
            progress_bar = st.progress(0)
            for row in range(0,total_rows,batch_size):
                rows = []
                col_read = 0
                for col in range(col_batch_size,len(fields_list),col_batch_size):
                    cols = fields_list[col_read:col]
                    col_read = col
                    result = conn.call('RFC_READ_TABLE', QUERY_TABLE=table, DELIMITER='|', ROWSKIPS=row, ROWCOUNT=batch_size,FIELDS=cols)
                    
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
                    progress_bar.progress((len(data)+col_read) / (total_rows+len(fields_list)))
                if len(data):
                    print(f"{len(data)} rows are fetched")
                data.extend(rows)
                progress_bar.progress((len(data)+col_read) / (total_rows+len(fields_list)))
                
            print(f"{len(data)} number of rows are found")
        time.sleep(1)
        with st.spinner("Saving data..."):
            rows = [row['WA'].split('|') for row in data]
            with open(f'{table}.txt', 'w') as f:
                f.write('|'.join([field for field in fields_list]) + '\n')
                f.writelines(['|'.join(row) + '\n' for row in rows])
        end = time.time()
        total = end - start
        st.success(f"Data saved successfully, Time elapsed {round(total,2)}s")
        with open(f'{table}.txt', "r") as f:
            file_contents = f.read()
        st.download_button(f"Download {table}", file_contents, file_name=f"{table}.txt")
    except CommunicationError:
        st.error("Could not connect to server.")
        raise
    except LogonError:
        st.error("Could not log in. Wrong credentials?")
        raise
    except (ABAPApplicationError, ABAPRuntimeError):
        st.error("An error occurred.")
        raise
    


def main():
    st.write("# Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):

        if authenticate(username=username,password=password):
            user = User.objects.get(username=username)
            st.session_state.user=user
            
            hide_st_style = """
                <style>
              
                {visibility: hidden;}
                </style>
            """
            st.markdown(hide_st_style, unsafe_allow_html=True)
            show_app_interface()
        else:
            st.error("Invalid username or password")

def show_app_interface():

    try:
        user = st.session_state.user
        s_data = st.session_state.data
    except:
        s_data = {}
    sap_conf = SAPConfig.objects.filter(django_user=user).first()
    st.write(f"Hi {user}")
    st.write("# Sap Data Extractor")
    with st.expander("Connection Details"):
        ASHOST = st.text_input(label="Host",key="Host",value=sap_conf.ASHOST if sap_conf else "")
        CLIENT = st.text_input(label="CLIENT",key="CLIENT",value=sap_conf.CLIENT if sap_conf else "")
        SYSNR = st.text_input(label="SYSNR",key="SYSNR",value=sap_conf.SYSNR if sap_conf else "")
        USER = st.text_input(label="User",key="User",value=sap_conf.USER if sap_conf else "")
        PASSWD = st.text_input(label="Password", type="password",key="Password",value=sap_conf.PASSWD if sap_conf else "")
        SAPROUTER = st.text_input(label="SAPROUTER",key="SapRouter",value=sap_conf.saprouter if sap_conf else "")
        if st.button("Save"):
            if ASHOST and SYSNR and USER and PASSWD:
                SAPConfig.objects.get_or_create(django_user=user,defaults={"ASHOST":ASHOST,"saprouter":SAPROUTER,"PASSWD":PASSWD,"USER":USER,"CLIENT":CLIENT,"SYSNR":SYSNR})
                st.success("Connection details saved successfully")
            else:
                st.error("ASHOST,SYSNR,USER and PASSWD are required")
    conn = ""
    try:
        conn = Connection(ashost=ASHOST, sysnr=SYSNR, user=USER, passwd=PASSWD,saprouter=SAPROUTER)
        st.success("Configuration server")
    except:
        st.error("Need server configuration")
    st.write("## Export Settings")
    table_name = st.text_input("Table Name",value=s_data.get("table_name",""))
    

    file_format = st.selectbox("File Format", options=["csv", "xlsx", "json"])
    btn =st.button("Fetch Data")
    if btn:
        if user and conn:
            data = {"table_name":table_name}
            st.session_state.data=data
            gt_data_from_sap(table_name,conn)
        else:
            st.error("Please add working configuration")
    

   
            

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

if __name__ == "__main__":
    
    # Check if the user is in session
    if "user" not in st.session_state:
        Login_t, Register_t = st.tabs(["Login","Register"])
        with Login_t:
            login()
        with Register_t:
            register()
       
    else:

        show_app_interface()
   
    

