# -*- coding: utf-8 -*-
"""
Runs a webserver that reports the machine's status as JSON object.
Intended to be used with openhab2 HTTP bindings for simple monitoring of home
servers.

Information included:
 * platform: processor, system
 * uptime: uptime, upsince
 * memory: total/avail/percentage used
 * load average

"""
import argparse
import json
import platform
import re
import sys
import time
from datetime import timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler


class SystemInfoRequestHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        # make response
        config = self.server.config
        result = {}
        if config["platform"]:
            result["platform"] = get_platform()
        if config["uptime"]:
            result["uptime"] = get_uptime()
        if config["memory"]:
            result["memory"] = get_memory()
        
        self.wfile.write(bytes(json.dumps(result), "utf8"))
        
        
class SystemInfoServer(HTTPServer):
    
    def __init__(self, config, *args, **kwargs):
        self.config = config
        super(SystemInfoServer, self).__init__(*args, **kwargs)


def get_platform():
    return {"processor": platform.processor(), "system": platform.system()}


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
        
    
print(get_platform())
print(get_uptime())
print(get_memory())


parser = argparse.ArgumentParser(description="System Info Server")
parser.add_argument("--port", type=int, default=8049)
parser.add_argument("--platform", action="store_true")
parser.add_argument("--uptime", action="store_true")
parser.add_argument("--memory", action="store_true")
config = vars(parser.parse_args())

httpd = SystemInfoServer(config, ("", config["port"]), SystemInfoRequestHandler)
httpd.serve_forever()
