from flask import Flask 
from flask import url_for, request, redirect, render_template, session, jsonify 
from json import dumps, loads 
from requests import get, post, put
from random import randrange 
import sys, os
import datetime


def download_file(path):
    print("downloading " + path, end=" ", flush=True)
    answer = get("https://cloud-api.yandex.net/v1/disk/resources/download" + 
                    "?path=" + path, headers={"Authorization": "OAuth " +
                                                        token }
                ).json()
    try:
        f = open(client_path + "/" + path, "wb")
        f.write(get(answer["href"]).content)
        print("-- Done")
    except:
        print("error", answer)

def upload_file(path):
    print("uploading " + path, end=" ", flush=True)
    answer = get("https://cloud-api.yandex.net/v1/disk/resources/upload" +
                    "?overwrite=true" + 
                    "&path=" + path, headers={"Authorization": "OAuth " +
                                                        token }
                ).json()
    put(answer["href"], files={"file": open(client_path + "/" + path, "rb")})
    print("-- Done")

def download_folder(path):
    os.mkdir(client_path + "/" + path)
    items = get(
                "https://cloud-api.yandex.net/v1/disk/resources" + 
                "?path=/" + path +
                "&limit=10000", 
                headers={"Authorization": "OAuth " + token}
               ).json()
    try:
        for item in items["_embedded"]["items"]:
            if "file" in item: 
                print("downloading " + path + "/" + item["name"], end=" ", flush=True)
                f = open(client_path + "/" + path + "/" + item["name"], "wb")
                f.write(get(item["file"]).content)
                f.close()
                print("-- Done")
            else:
                download_folder(path + "/" + item["name"])
    except:
        print("error ", path, items) 
    
def upload_folder(path):
    answer = put(
                  "https://cloud-api.yandex.net/v1/disk/resources" + 
                  "?path=/" + path +
                  "&limit=10000", 

                  headers={"Authorization": "OAuth " + token}
                ).json() 
    for item in os.listdir(client_path + "/" + path):
        if os.path.isdir(client_path + "/" + path + "/" + item):
            upload_folder(path + "/" + item) 
        else:
            upload_file(path + "/" + item)

def sync_folder(path):
    path = path.strip("/")
    yand_folder = get(
                       "https://cloud-api.yandex.net/v1/disk/resources" + 
                       "?path=disk:/" + path +
                       "&limit=10000", 
                       headers={"Authorization": "OAuth " + token}
                     ).json()
    yand_folder = yand_folder["_embedded"]["items"]
    client_folder = os.listdir(f"{client_path}/{path}")
    get_data_url = "https://cloud-api.yandex.net/v1/disk/resources" + \
                   f"?path=/{path}/"
    for item in yand_folder:
        if item["type"] == "dir":
            if item["name"] not in client_folder or \
                   os.path.isfile(item["name"]):
                download_folder(path + "/" + item["name"])
                continue
            client_mod = datetime.datetime.utcfromtimestamp(os.path.getmtime( 
                             f"{client_path}/{path}/" + item["name"] 
                                                                            )).isoformat()[:15]
            yand_mod = item["modified"][:15]
            if last_sync_start <= client_mod <= last_sync_end or \
                   last_sync_start <= yand_mod <= last_sync_end:
                print("skipping ", path, item["name"])
                continue
            sync_folder(path + "/" + item["name"])
            continue
        if item["name"] not in client_folder:
            download_file(path + "/" + item["name"])
            continue
        client_mod = datetime.datetime.utcfromtimestamp(os.path.getmtime( 
                         f"{client_path}/{path}/" + item["name"] 
                                                                        )).isoformat()[:15]
        yand_mod = item["modified"][:15]
        if client_mod < last_sync_start and yand_mod > last_sync_end:
            download_file(path + "/" + item["name"])
        elif client_mod > last_sync_end and yand_mod < last_sync_start:
            upload_file(path + "/" + item["name"])
        elif (client_mod > last_sync_end and yand_mod > last_sync_end) or \
               (client_mod < last_sync_start and yand_mod < last_sync_start):
            print("conflict in {}. YD date {}, client date {}.".format( 
                            path + "/" + item["name"],
                            yand_mod,
                            client_mod                        
                                                                 ) +
                      "There are several options for you:"
                 )
            print("y -- for downloading from yand_disk")
            print("c -- for uploading from client")
            print("s -- to skip and they will stay like this till next sync")
            print("q -- to quit right now (you can check file and restart program, next time it will be faster)")
            print("you can open another terminal(-s) to check files and decide, this program will wait for you")
            command = input()
            while command not in ["y", "c", "s", "q"]:
                print("invalid command, try again")
                command = input()
            if command == "y":
                download_file(path + "/" + item["name"])
            elif command == "c":
                upload_file(path + "/" + item["name"])
            elif command == "s":
                continue
            else:
                os.kill(os.getpid(), 9)


try:
    f = loads(open("CONSTANTS.json", "r").read())
    last_sync_start_b = datetime.datetime.now().isoformat()[:15]
    CONSTANTS = loads(open("CONSTANTS.json", "r").read())
    token = CONSTANTS["access_token"]
    client_path = CONSTANTS["path"]
    last_sync_end = CONSTANTS["last_sync_end"][:15]
    last_sync_start = CONSTANTS["last_sync_start"][:15]
    sync_folder("")
    last_sync_end = datetime.datetime.now().isoformat()[:15]
    client_path = CONSTANTS["path"]
    CONSTANTS["last_sync_start"] = last_sync_start_b
    CONSTANTS["last_sync_end"] = last_sync_end
    f = open("CONSTANTS.json", "w")
    f.write(dumps(CONSTANTS))

except FileNotFoundError:
    print()
    print("now to start we need you to go to this page (you can use ctrl + lclick)")
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "petr_lapa_ochen_horoshiy"
    print("https://oauth.yandex.ru/authorize?response_type=code&client_id=c6c4390b2b624f7fa9946124341a1f9f")
     
    @app.route("/")
    def index():
        code = str(request.args.get("code"))
        func = request.environ.get("werkzeug.server.shutdown")
        client_id, client_secret = open("SECRETS.txt", "r").read().split("\n")
        if func is None:
            raise RuntimeError("Not running with the Werkzeug Server")
        print( "https://oauth.yandex.ru/token?" + 
                      'grant_type="authorization_code"') 
        token = post( "https://oauth.yandex.ru/token",
                      data="grant_type=authorization_code&" + 
                           "code=" + str(code) + 
                           f"&client_id={client_id}" +
                           f"&client_secret={client_secret}",
                    )
        f = open("CONSTANTS.json", "w+")
        data = token.json()
        print()
        print("dont worry this is ok that page doesnt work. you can close it")
        print("everything is fine. restart this program and it will be ok") 
        print("please select absolute path to Yandex.Disk folder (e. g. /home/user)")
        data["path"] = input() + "/Yandex.Disk"
        data["last_sync_start"] = '1970-01-01T00:00:00'
        data["last_sync_end"] = '1970-01-01T00:00:00'

        print(token)
        print("^ if it is 4xx its too bad! remove file CONSTANTS.json and restart")
        f.write(dumps(data))
        f.close()
        func()
        os.kill(os.getpid(), 9)
        return "ok now everything is completed. return to the terminal and restart program"
 
    if __name__ == "__main__":
        app.run(port=8080, host="127.0.0.1")
