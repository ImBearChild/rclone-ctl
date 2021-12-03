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

logging.basicConfig(level=logging.DEBUG)

SUPPORTRED_SERVE = ["webdav"]


class RclonectlConfig(object):
    warnings = []

    _parser = None
    # parsed = {}

    _default_ini = """
[rclone]
exec_file = rclone
rc_addr = localhost:5572
rc_user = u-rclone-ctl
rc_pass = forty-two
cache_dir = /tmp/rclone-ctl

[rclone-ctl]
pid_file=${rclone:cache_dir}/rclone-ctl.pid
"""

    def __init__(self, path=None):
        path = self.get_default_path() if path is None else path
        self.path = path
        self.warnings = []
        self._parsed = []
        self._parser = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation())
        self.read_string(self._default_ini)
        if path:
            self.read(path)
        # self._maintain_renaimed_options()

    def __getattr__(self, name):
        return getattr(self._parser, name)

    def get_default_path(self):
        p = os.path.join(os.getcwd(), "rclone-ctl.ini")
        if os.path.isfile(p):
            return p

    def get_services(self):
        return [s for s in self._parser.sections() if s.startswith("service@")]


class RemoteControlServer(object):
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


def util_ranstr(num):
    salt = ''.join(random.sample(string.ascii_letters + string.digits, num))
    return salt


def err_exit():
    logging.error("Rclone-ctl will exit due to unrecoverable error")
    exit()


def run_rcd():

    if args.command == "stop":
        f = open(config.get("rclone-ctl", "pid_file"), "r")
        pid = int((f.read()))
        logging.info("Kill pid: %d", pid)
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            logging.error("No process found, already killed?")
        f.close()
        exit()

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


def run_without_command():
    parser.print_help()


def run_service():
    service_name = "service@"+args.service
    if not service_name in config.get_services():
        logging.error("Service not found: %s", args.service)
        err_exit()
    rcs = RemoteControlServer(config.get("rclone", "rc_user"), config.get(
        "rclone", "rc_pass"), config.get("rclone", "rc_addr"))
    if not rcs.check():
        logging.error("Not a rclone remote server on %s",
                      config.get("rclone", "rc_addr"))
        err_exit()
    if args.command == "start":
        logging.info("Starting service %s", args.service)
        if config.get(service_name, "type") in SUPPORTRED_SERVE:
            serve_arg = [config.get(service_name, "type"),
                         "--user="+config.get(service_name, "user"),
                         "--pass="+config.get(service_name, "pass"),
                         "--addr="+config.get(service_name, "addr"),
                         config.get(service_name, "remote_path")]
            result = rcs.send_request(
                "core/command", {"command": "serve", "arg": serve_arg, "returnType": "STREAM"})
            logging.debug(result)
            if result['error']:
                logging.warning("Rclone repond an error")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Commandline control tool for rclone')
    subparsers = parser.add_subparsers(title='Available commands',
                                       dest='sub_command')

    parser_rcd = subparsers.add_parser(
        'rcd', help='run a rlcone remote control daemon')
    parser_rcd.set_defaults(func=run_rcd)
    parser_rcd.add_argument(
        'command', choices=['start', 'stop'], action='store')

    parser_service = subparsers.add_parser(
        'service', help='manage services provided by rclone')
    parser_service.set_defaults(func=run_service)
    parser_service.add_argument(
        'command', choices=['start', 'stop'], action='store')
    parser_service.add_argument(
        'service', action='store')

    parser.set_defaults(func=run_without_command)
    args = parser.parse_args()

    config = RclonectlConfig()
    logging.debug("Config file path: %s", config.path)
    config.read(config.path)
    args.func()
