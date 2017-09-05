import requests
import time
import logging
import os.path
import sys
import re
import threading
from win10toast import ToastNotifier
from retrying import retry


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_time():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def config_logging():
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        filename='zone.log',
                        filemode='w')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)


def read_configfile(filename):

    intData = {}
    with open(filename, 'r') as f:
        fileData = f.read()

    logging.info(fileData)
    formatData = re.finditer("\[(\S+)\]\s*=\s*(\S+)",fileData)
    for myData in formatData:
        intData[myData.group(1)] = myData.group(2)

    if not len(intData):
        logging.warning("无数据读入...")
        exit()

    return intData


class Scrapy_Zone(object):
    def __init__(self, url):
        self.url = url
        self.buildingInfo = {}
        self.zoneInfo = {}
        self.buildingPostfix = "selectList1"
        self.zonePostfix = "formList1"
        self.buildinginfo_analysis(self.get_building_info(self.url + "/online/roomResource.xp?action=" + self.buildingPostfix))

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def get_building_info(self, url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36 QQBrowser/3.9.3943.400",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }

        data = {
            "code": "01"
        }

        logging.info("获取建筑信息。。。\n")
        try:
            content = requests.post(url, data=data, headers=headers, timeout=10).json()
        except Exception as e:
            logging.warning("获取失败惹。。。嘤嘤嘤，重试之\n")
            logging.warning(e)

        return content

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def get_zone_info(self, url, buildingcode, zonename):
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36 QQBrowser/3.9.3943.400",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }

        data = {
            "code": "01",
            "buildingCode": buildingcode
        }

        logging.info("获取%s房间信息(建筑代码：%s)。。。\n" % (zonename, buildingcode))
        try:
            content = requests.post(url, data=data, headers=headers, timeout=10).json()
        except Exception as e:
            logging.warning("获取失败惹。。。嘤嘤嘤,重试之\n")
            logging.warning(e)

        return content

    def zoneinfo_analysis(self, content, buildingName):
        self.zoneInfo[buildingName] = []
        for name in content["list"]:
            for info in content["list"][name]:
                if info["status"] == "02":
                    self.zoneInfo[buildingName].append(info["roomName"])

    def buildinginfo_analysis(self, content):
        for info in content["list"]:
            self.buildingInfo[info["buildingName"]] = info["buildingCode"]

    def output_data(self,zonename):
        for buildingName in self.buildingInfo:
            self.zoneinfo_analysis(self.get_zone_info(self.url + "/online/roomResource.xp?action=" + self.zonePostfix,
                                                      self.buildingInfo[buildingName],
                                                      zonename),
                                   buildingName)
        return self.zoneInfo


def scrapy_thread(zonename, zoneobj):
    global myData
    global myLock

    logging.info("获取%s房间信息\n" % zonename)
    threadData = zoneobj.output_data(zonename)
    myLock.acquire()
    myData[zonename] = threadData
    myLock.release()


def main():

    config_logging()
    logging.info("参数配置中。。。")
    zoneData = read_configfile("zone.ini")

    logging.info("参数读取完毕")
    logging.info(zoneData)

    global myData
    myData = {}
    myZone = {}
    myThread = {}
    global myLock
    myLock = threading.Lock()

    logging.info("喵~ 开始运行咯~")
    logging.info("初始化ing。。。")

    for zoneName in zoneData:
        logging.info(zoneName)
        myZone[zoneName] = Scrapy_Zone(zoneData[zoneName])

    logging.info("初始化完成\n")

    while 1:
        myText = ""
        for zoneName in myZone:
            myThread[zoneName] = threading.Thread(target=scrapy_thread, args=(zoneName, myZone[zoneName]))
            myThread[zoneName].start()

        for zoneName in myZone:
            myThread[zoneName].join()

        logging.info(myData)

        for zoneName in myData:
            for buildingName in myData[zoneName]:
                if len(myData[zoneName][buildingName]):
                    myText = myText + zoneName + ":" + buildingName + "\n"

        logging.info("等待30秒继续。。。\n")

        if myText != "":
            toaster = ToastNotifier()
            toaster.show_toast("有新的住房消息~",
                               myText,
                               icon_path=resource_path("building2.ico"),
                               duration=10)

        time.sleep(30)


if __name__ == "__main__":

    main()
