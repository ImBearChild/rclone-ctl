#!/usr/bin/python3

import configparser
import os
import logging
import random
import string
import signal
import subprocess
import time
import urllib.request
import json
import sys

logging.basicConfig(level=logging.DEBUG)
SUPPORTRED_SERVE = ["webdav"]

class RclonectlConfig(object):
    warnings = []

    parser = None
    # parsed = {}

    _default_ini = """
[rclone]
exec_file = rclone
rc_addr = localhost:5572
rc_user = u-rclone-ctl
rc_pass = forty-two
cache_dir = /tmp/rclone-ctl

[rclone-ctl]
pid_file=${rclone:cache_dir}/rclonectl.pid
"""

    def __init__(self, path=None):
        path = self.get_default_path() if path is None else path
        self.path = path
        self.warnings = []
        self._parsed = []
        self.parser = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation())
        self.read_string(self._default_ini)
        if path:
            self.read(path)
        # self._maintain_renaimed_options()

    def __getattr__(self, name):
        return getattr(self.parser, name)

    def get_default_path(self):
        p = os.path.join(os.getcwd(), "rclonectl.ini")
        if os.path.isfile(p):
            return p

    def get_section(self,section):
        return self.parser[section]
    def get_services(self):
        return [s for s in self.parser.sections() if s.endswith(".service")]
    def get_mounts(self):
        return [s for s in self.parser.sections() if s.endswith(".mount")]
    def get_units(self):
        return [s for s in self.parser.sections() if s.startswith("unit:")]

class RcloneRCServer(object):
    addr = None
    opener = None

    def __init__(self, user, passwd, addr="localhost:5572"):
        self.path = "http://"+addr+"/"
        p = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        p.add_password(None, self.path, user, passwd)
        auth_handler = urllib.request.HTTPBasicAuthHandler(p)
        self.opener = urllib.request.build_opener(auth_handler)
        self.opener.addheaders.append(("Content-Type", "application/json"))

    def send_request(self, command, parameter):
        json_para = json.dumps(parameter)
        logging.debug(json_para)
        data = bytes(json_para, encoding="utf-8")
        req = urllib.request.Request(
            self.path+command, data, headers={'Content-Type': 'application/json'})
        resp = self.opener.open(req)
        json_resp = resp.read().decode('utf-8')
        logging.debug(json_resp)
        return json.loads(json_resp)

    def check(self):
        try:
            r = self.send_request("rc/noopauth", {"rclone": "magic"})
        except urllib.error.URLError as e:
            logging.error(e)
            return False
        if r["rclone"] == "magic":
            return True
        return False


class RclonectlUnit(object):
    name = ""
    _conf = None
    _rc_server = None
    _start_handler = None
    _stop_handler = None

    def __init__(self,name, conf, rc_server):
        self.unit_name = name
        self._conf = conf
        self._rc_server = rc_server
        logging.debug(name)
        if self.unit_name.endswith("service"):
            self._start_handler = self._start_service
            self._stop_handler = self._stop_service

    def _start_service(self):
        if self._conf['protocol'] in SUPPORTRED_SERVE:
            serve_arg = [self._conf['protocol'],
                         "--user="+self._conf['user'],
                         "--pass="+self._conf['pass'],
                         "--addr="+self._conf['addr'],
                         self._conf['remote_path']]
            result = self._rc_server.send_request(
                "core/command", {"command": "serve", "arg": serve_arg,"_async": True})
            if result.get('error'):
                logging.warning("Rclone reported an error")
            if result.get('jobid'):
                logging.info("Success!")

    def _stop_service(self):
        logging.error("Unsupported feature! Still under developemnt...")

    def start(self):
        logging.info("Starting unit %s", self.unit_name)
        self._start_handler()
        pass
    def stop(self):
        logging.info("Stopping unit %s", self.unit_name)
        self._stop_handler()
        pass

def util_ranstr(num):
    salt = ''.join(random.sample(string.ascii_letters + string.digits, num))
    return salt


def err_exit():
    logging.error("Rclone-ctl will exit due to unrecoverable error")
    sys.exit()


def exec_rcd():
    if args.command == "stop":
        f = open(config.get("rclone-ctl", "pid_file"), "r")
        pid = int((f.read()))
        logging.info("Kill pid: %d", pid)
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            logging.error("No process found, already killed?")
        f.close()
        sys.exit()

    exec_file = config.get("rclone", "exec_file")
    cache_dir = config.get("rclone", "cache_dir")
    if not os.path.isdir(cache_dir):
        os.mkdir(cache_dir)
    rc_user = config.get("rclone", "rc_user")
    rc_pass = config.get("rclone", "rc_pass")
    rc_addr = config.get("rclone", "rc_addr")
    cmd = [exec_file, "rcd",
           "--cache-dir="+cache_dir,
           "--rc-addr="+rc_addr,
           "--rc-user="+rc_user,
           "--rc-pass="+rc_pass]
    logging.info("CMD: %s", cmd)

    p = subprocess.Popen(cmd)
    logging.debug("Waiting 3 secs...")
    time.sleep(3)
    if p.poll():
        logging.error(
            "rclone failed to start with exiting code [%s]!", p.poll())
        err_exit()
    else:
        f = open(config.get("rclone-ctl", "pid_file"), "w")
        f.write(str(p.pid))
        f.close()


def exec_without_command():
    parser.print_help()


def exec_unit():
    unit_name = args.unit
    if not "unit:"+unit_name in config.get_units():
        logging.error("Service not found: %s", args.unit)
        err_exit()
    rcs = RcloneRCServer(config.get("rclone", "rc_user"), config.get(
        "rclone", "rc_pass"), config.get("rclone", "rc_addr"))
    if not rcs.check():
        logging.error("Not a rclone remote server on %s",
                      config.get("rclone", "rc_addr"))
        err_exit()
    if args.command == "start":
        unit = RclonectlUnit(unit_name, config.get_section("unit:"+unit_name), rcs)
        unit.start()
    elif args.command == "stop":
        unit = RclonectlUnit(unit_name, config.get_section("unit:"+unit_name), rcs)
        unit.stop()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Commandline control tool for rclone')
    subparsers = parser.add_subparsers(title='Available commands',
                                       dest='sub_command')

    parser_rcd = subparsers.add_parser(
        'rcd', help='run a rlcone remote control daemon')
    parser_rcd.set_defaults(func=exec_rcd)
    parser_rcd.add_argument(
        'command', choices=['start', 'stop'], action='store')

    parser_unit = subparsers.add_parser(
        'unit', help='manage services provided by rclone')
    parser_unit.set_defaults(func=exec_unit)
    parser_unit.add_argument(
        'command', choices=['start', 'stop'], action='store')
    parser_unit.add_argument(
        'unit', action='store')

    parser.set_defaults(func=exec_without_command)
    args = parser.parse_args()

    config = RclonectlConfig()
    logging.debug("Config file path: %s", config.path)
    config.read(config.path)
    args.func()
