#!/usr/bin/python
# encoding=utf-8

"""
@Author  :  Lijiawei
@Date    :  2022/6/19
@Desc    :  adb line.
@Update  :  2022/7/14 by Rafa chen
"""
import os
import platform
import queue
import stat
import subprocess
import threading
import time

import select

STATICPATH = os.path.dirname(os.path.realpath(__file__))
DEFAULT_ADB_PATH = {
    "Windows": os.path.join(STATICPATH, "adb", "windows", "adb.exe"),
    "Darwin": os.path.join(STATICPATH, "adb", "mac", "adb"),
    "Linux": os.path.join(STATICPATH, "adb", "linux", "adb"),
    "Linux-x86_64": os.path.join(STATICPATH, "adb", "linux", "adb"),
    "Linux-armv7l": os.path.join(STATICPATH, "adb", "linux_arm", "adb"),
}


def make_file_executable(file_path):
    """
    If the path does not have executable permissions, execute chmod +x
    :param file_path:
    :return:
    """
    if os.path.isfile(file_path):
        mode = os.lstat(file_path)[stat.ST_MODE]
        executable = True if mode & stat.S_IXUSR else False
        if not executable:
            os.chmod(file_path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return True
    return False


def builtin_adb_path():
    """
    Return built-in adb executable path

    Returns:
        adb executable path

    """
    system = platform.system()
    machine = platform.machine()
    adb_path = DEFAULT_ADB_PATH.get('{}-{}'.format(system, machine))
    proc = subprocess.Popen('adb devices', stdout=subprocess.PIPE, shell=True)
    result = proc.stdout.read()
    if not isinstance(result, str):
        result = str(result, 'utf-8')
    if result and "command not found" not in result:
        adb_path = "adb"
        return adb_path

    if not adb_path:
        adb_path = DEFAULT_ADB_PATH.get(system)
    if not adb_path:
        raise RuntimeError("No adb executable supports this platform({}-{}).".format(system, machine))

    # overwrite uiautomator adb
    if "ANDROID_HOME" in os.environ:
        del os.environ["ANDROID_HOME"]
    if system != "Windows":
        # chmod +x adb
        make_file_executable(adb_path)
    return adb_path


class ADB(object):

    def __init__(self):
        self.adb_path = builtin_adb_path()
        self.process = None
        self.command_queue = queue.Queue()
        self.running = True
        self.lock = threading.Lock()
        self.result_threading = threading.Thread(target=self._read_output)
        self.result_threading.daemon = True

    def adb_new_shell(self, cmd, deviceId):
        response_event = threading.Event()
        response_data = {'event': response_event, 'output': []}

        with self.lock:  # 使用锁确保线程安全
            if self.process is None:
                # 如果没有现有进程，创建一个新的ADB Shell进程
                self.process = subprocess.Popen([self.adb_path, '-s', deviceId, 'shell'],
                                                stdin=subprocess.PIPE,
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE,
                                                bufsize=0,  # 行缓冲
                                                universal_newlines=True,
                                                text=True)
                self.result_threading.start()  # 启动线程读取输出

            # 写入命令
            self.process.stdin.write(cmd + '\n')
            self.process.stdin.flush()
            self.command_queue.put(response_data)

        # 等待输出
        response_event.wait()
        output = response_data['output']
        return output  # 返回输出

    def shell(self, cmd, deviceId):
        run_cmd = f'{self.adb_path} -s {deviceId} shell {cmd}'
        result = subprocess.Popen(run_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[
            0].decode("utf-8").strip()
        return result

    def new_shell(self, cmd):
        run_cmd = f'{self.adb_path} shell {cmd}'
        result = subprocess.Popen(run_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[
            0].decode("utf-8").strip()
        return result

    def tcp_shell(self, deviceId, cmd):
        run_cmd = f'{self.adb_path} -s {deviceId} {cmd}'
        result = os.system(run_cmd)
        return result

    def shell_noDevice(self, cmd):
        run_cmd = f'{self.adb_path} {cmd}'
        result = os.system(run_cmd)
        return result

    def close_shell(self):
        with self.lock:
            self.running = False
            if self.process:
                self.process.terminate()
                self.process = None

    def _read_output(self):
        start_time = time.time()
        out_put_list = ''
        while self.running:
            for line in iter(self.process.stdout.readline, b''):
                out_put_list += line
                print(out_put_list)
            print("woc")
            if out_put_list.__len__() > 0:
                with self.lock:
                    if not self.command_queue.empty():
                        response_data = self.command_queue.get()
                        response_data['output'] = out_put_list
                        response_data['event'].set()
                        out_put_list = ''
            elif (time.time() - start_time) > 2:
                response_data['event'].set()
                break


adb = ADB()


class ADBShell:
    def __init__(self):
        self.process = None
        self.output_queue = queue.Queue()
        self.thread = threading.Thread(target=self._read_output)
        self.adb_path = builtin_adb_path()

    def _read_output(self):
        while True:
            line = self.process.stdout.readline()
            if line:
                self.output_queue.put(line)
            else:
                break

    def send_command(self, command, deviceId):
        if self.process is None:
            self.process = subprocess.Popen([self.adb_path, '-s', deviceId, 'shell'], stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True)
            self.thread.daemon = True
            self.thread.start()
        self.process.stdin.write(command + '\n')
        self.process.stdin.flush()
        output = []
        while True:
            try:
                line = self.output_queue.get(timeout=1)
                if line.endswith('$ '):  # 假设shell提示符是'# '
                    break
                output.append(line.strip())
            except queue.Empty:
                break
        return '\n'.join(output)

    def close(self):
        self.process.stdin.write('exit\n')
        self.process.stdin.flush()
        self.process.terminate()
        self.thread.join()


adb_shell = ADBShell()
