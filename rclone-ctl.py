#!/usr/bin/python3

import configparser
import os
import logging
import random
import string
import signal
import subprocess
import time

logging.basicConfig(level=logging.DEBUG)


class RclonectlConfig(object):
    warnings = []

    _parser = None
    # parsed = {}

    def __init__(self, path=None):
        path = self.get_default_path() if path is None else path
        self.path = path
        self.warnings = []
        self._parsed = []
        self._parser = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
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


def util_ranstr(num):

    salt = ''.join(random.sample(string.ascii_letters + string.digits, num))
    return salt

def run_rcd(args):
    config = RclonectlConfig()
    logging.debug("Config file path: %s", config.path)
    config.read(config.path)

    if args.command == "stop":
        f = open(config.get("rclone-ctl", "pid_file",
                 fallback="rclone-ctl.pid"), "r")
        pid = int((f.read()))
        logging.info("Kill pid: %d",pid)
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            logging.error("No process found, already killed?")
        f.close()
        exit()

    exec_file = config.get("rclone", "exec_file", fallback="rclone")
    cache_dir = config.get("rclone", "cache_dir", fallback="/tmp/rclone-ctl")
    if not os.path.isdir(cache_dir):
        os.mkdir(cache_dir)
    rc_user = config.get("rclone", "rc_user", fallback="u-rclone-ctl")
    rc_pass = config.get("rclone", "rc_pass", fallback="forty-two")
    rc_addr = config.get("rclone", "rc_addr", fallback="localhost:5572")
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
            "Rclone failed to start with exiting code [%s]! Rclone-ctl is exiting ...", p.poll())
        exit()
    else:
        f = open(config.get("rclone-ctl", "pid_file",
                 fallback="rclone-ctl.pid"), "w")
        f.write(str(p.pid))
        f.close()

def run_without_command(args):
    parser.print_help()


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

    parser_service = subparsers.add_parser('serve', help='serve a remote with a different protocol')
    parser_service.add_argument(
        'command', choices=['start', 'stop'], action='store')
    parser_service.add_argument(
        'name', choices=['start', 'stop'], action='store')
    
    parser.set_defaults(func=run_without_command)
    args = parser.parse_args()
    args.func(args)
