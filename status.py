# -*- coding: utf-8 -*-
"""
Runs a webserver that reports the machine's status as JSON object.
Intended to be used with openhab2 HTTP bindings for simple monitoring of home
servers.

Information included:
 * platform: processor, system
 * uptime: uptime, upsince
 * memory: total/avail/percentage used
 * load: average 1min/5min/15min

"""
import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


# ==== HTTP server components
class SystemInfoRequestHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        config = self.server.config
        # check if client is authorized
        if config["key"] != "none":
            params = parse_qs(urlparse(self.path).query)
            provided_key = None
            if "key" in params and params["key"]:
                provided_key = params["key"][0]
            if provided_key != config["key"]:
                self.send_response(401)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(bytes("Unauthorized.", "utf8"))
                return
        # respond after successful authorization
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        # make response
        result = {}
        if config["platform"]:
            result["platform"] = get_platform()
        if config["uptime"]:
            result["uptime"] = get_uptime()
        if config["memory"]:
            result["memory"] = get_memory()
        if config["load"]:
            result["load"] = get_load()
        if config["storage"]:
            result["storage"] = get_storage(config["storage"])
        
        self.wfile.write(bytes(json.dumps(result), "utf8"))
        
        
class SystemInfoServer(HTTPServer):
    
    def __init__(self, config, *args, **kwargs):
        self.config = config
        super(SystemInfoServer, self).__init__(*args, **kwargs)


# ==== status information sources
def get_platform():
    return {"platform": platform.machine(), "system": platform.system()}


def get_uptime():
    if not sys.platform.startswith("linux"):
        return {"uptime": 0, "upsince": time.time()}
    with open("/proc/uptime", "r") as f:
        up_seconds = float(f.readline().split()[0])
        up_since = time.time() - up_seconds
    return {"uptime": up_seconds, "upsince": up_since}
    
    
def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)
    
    
def get_memory():
    if not sys.platform.startswith("linux"):
        return {"total": "0 Bytes", "avail": "0 Bytes", "percent_used": 100.0}
    with open("/proc/meminfo", "r") as f:
        data = f.read()
        exp_total = re.compile(r"MemTotal:.*?(\d+)")
        exp_avail = re.compile(r"MemAvailable:.*?(\d+)")
        m = exp_total.findall(data)
        total = float(m[0]) * 1024
        m = exp_avail.findall(data)
        avail = float(m[0]) * 1024
        used = total - avail
        percent_used = 100*used/total
        
    return {"total": sizeof_fmt(total), "avail": sizeof_fmt(avail),
            "percent_used": round(percent_used, 1)}
            
            
def get_load():
    if not sys.platform.startswith("linux"):
        return {"load1": 0, "load5": 0, "load15": 0}
    with open("/proc/loadavg", "r") as f:
        d = f.read().split()
        load = list(map(float, d[:3]))
        return {"load1": load[0], "load5": load[1], "load15": load[2]}
        
        
def get_df(mnt):
    d = subprocess.check_output(["df", "-B 1", mnt]).decode("ascii").split("\n")[1]
    vals = d.split()
    total = int(vals[1])
    used = int(vals[2])
    avail = int(vals[3])
    percent_used = int(vals[4][:-1])
    return {"total_bytes": total, "total": sizeof_fmt(total),
            "used_bytes": used, "used": sizeof_fmt(used),
            "avail_bytes": avail, "avail": sizeof_fmt(avail),
            "percent_used": percent_used}
        
        
def get_storage(mounts):
    result = {}
    for mnt in mounts:
        if os.path.exists(mnt) and os.path.isdir(mnt):
            info = get_df(mnt)
            if mnt == "/":
                name = "root"
            else:
                name = mnt.strip("/").replace("/", "-")
            result[name] = info
    return result
        
    
# ==== prepare command line parser
parser = argparse.ArgumentParser(description="System Info Server")
parser.add_argument("--port", type=int, default=8049)
parser.add_argument("--key", type=str, default="none")
parser.add_argument("--platform", action="store_true")
parser.add_argument("--uptime", action="store_true")
parser.add_argument("--memory", action="store_true")
parser.add_argument("--load", action="store_true")
parser.add_argument("--storage", type=str, nargs="*", default=[])

# ==== run server
config = vars(parser.parse_args())
httpd = SystemInfoServer(config, ("", config["port"]),
                         SystemInfoRequestHandler)
httpd.serve_forever()
