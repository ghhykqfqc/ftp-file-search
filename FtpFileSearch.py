import ftplib
import os
import time
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox
from zoneinfo import ZoneInfo
import requests
import re

def get_file_stat(ftp, filename):
    """
    使用 STAT 命令获取文件详细信息
    """
    try:
        # STAT 命令返回文件状态
        response = ftp.sendcmd(f"STAT {filename}")
        if not response.startswith("213"): 
            return None
        # 解析响应，提取并返回时间部分（如 "Dec 13 07:58"）
        time_part = re.search(r'(\w{3}) (\d{2}) (\d{2}:\d{2})', response)
        if not time_part:
            return None

        month_str, day_str, time_str = time_part.groups()

        # 将月份缩写转换为数字
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        month = month_map[month_str]

        # 获取今天的日期（年份 + 月份 + 日期）
        today = datetime.now(ZoneInfo('Asia/Shanghai'))
        year = today.year
        modify_date = datetime(year, month, int(day_str))

        # 拼接时间部分（如 "07:58"）
        modify_time = datetime.strptime(f"{modify_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M")

        return modify_time
    
    except Exception as e:
        print(f"STAT 命令失败: {e}")
    
    return None

# 通过目录下的文件列表匹配文件名解析到达时间（使用 LIST 命令）
def get_arrive_time_from_line(line, expected_filename):
    """
    解析 ftp LIST 命令返回的一行，提取文件名和修改时间
    :param line: 如 '-rw-r--r--    1 1500       weblogic      2444676 Dec 13 07:58 xxx_20251212_68.txt'
    :param expected_filename: 当前循环中的文件名，用于匹配
    :return: 到达时间（datetime 对象）或 None
    """
    # 匹配文件名
    match = re.search(r'(\S+)$', line)  # 匹配最后一个字段（文件名）
    if not match:
        return None

    filename = match.group(1)

    # 如果文件名不匹配，直接返回 None
    if filename != expected_filename:
        return None

    # 提取时间部分（如 "Dec 13 07:58"）
    time_part = re.search(r'(\w{3}) (\d{2}) (\d{2}:\d{2})', line)
    if not time_part:
        return None

    month_str, day_str, time_str = time_part.groups()

    # 将月份缩写转换为数字
    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    month = month_map[month_str]

    # 获取今天的日期（年份 + 月份 + 日期）
    today = datetime.now(ZoneInfo('Asia/Shanghai'))
    year = today.year
    modify_date = datetime(year, month, int(day_str))

    # 拼接时间部分（如 "07:58"）
    modify_time = datetime.strptime(f"{modify_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M")

    return modify_time

# Bark 含标题消息推送
def send_message(title, desp):
    # server酱 微信服务号推送
    # sendkey = "xxx"
    # url = f"https://sctapi.ftqq.com/{sendkey}.send"
    # data = {
    #     "title": title,
    #     "desp": desp
    # }

    # Bark 含标题消息推送
    send_key = os.getenv('SEND_KEY')
    url = f"https://api.day.app/{send_key}/{title}/{desp}"
    response = requests.post(url)
    return response.json()


# Bark 响铃推送
def send_sound():
    # Bark 推送重要警告
    send_key = os.getenv('SEND_KEY')
    url = f"https://api.day.app/{send_key}/重要警告?level=critical&volume=8"
    response = requests.post(url)
    return response.json()


def process_ftp_files(ftp_ip, ftp_port, ftp_username, ftp_password, ftp_base_url, last_day, bill_types):
    """
    根据文件列表循环查找 FTP 目录下是否有对应的文件。
    
    :param ftp_ip: FTP 服务器 IP 地址
    :param ftp_port: FTP 服务器端口
    :param ftp_username: FTP 用户名
    :param ftp_password: FTP 密码
    :param ftp_base_url: FTP 基础路径
    :param last_day: 日期字符串，用于拼接文件路径
    :param bill_types: 文件类型列表，例如 ['68', '9']
    """
    ftp = None
    timeSleepInterval = 15
    try:
        # 连接到 FTP 服务器
        ftp = ftplib.FTP()
        ftp.connect(ftp_ip, ftp_port)
        ftp.login(ftp_username, ftp_password)
        print("FTP 连接成功")

        # 切换到目标目录
        target_dir = f"{ftp_base_url}"
        ftp.cwd(target_dir)
        print(f"切换到目录: {target_dir}\n 每{timeSleepInterval}秒检查一次账单文件是否存在\n...")
        has_found_types = []
        arrive_times = dict()

        while True:
            # 获取目录下的文件列表
            file_list = ftp.nlst()
            # 获取目录下的文件列表（使用 LIST 命令）   
            file_lines = []
            ftp.retrlines('LIST', lambda line: file_lines.append(line))

            # 检查文件是否存在
            all_files_exist = True
            for bill_type in bill_types:
                file_name = f"10220014420000_{last_day}_{bill_type}.txt"
                search_time = datetime.now(ZoneInfo('Asia/Shanghai')).strftime("%Y-%m-%d %H:%M:%S")
                account_date = datetime.strptime(last_day, "%Y%m%d").strftime("%Y-%m-%d")
                
                print(f"--当前时间：{search_time} | 账单日：{account_date} | 正在检查{bill_type}账单{file_name}--")

                if file_name in file_list:  # 使用 nlst() 方法检查文件是否存在
                    # 该账单文件已找到，生成描述并发送通知
                    file_desp = f"{bill_type}账单{file_name}--已存在\n查询时间：{search_time}\n账单日：{account_date}"
                    print(f"{file_name}--{bill_type}账单--已存在")
                    if bill_type not in has_found_types:  # 存在的账单 仅发送一次通知 通过已找到类型列表记录防重
                        has_found_types.append(bill_type)
                        arrive_time = None

                        # 使用 消息推送服务 暂用Bark
                        messageResult = send_message(f"{bill_type}账单通知", file_desp)
                        if messageResult["code"] == 200:
                            print(f"消息发送成功")
                        else:
                            print(f"消息发送失败：{messageResult['message']}")

                        soundResult = send_sound()
                        if soundResult["code"] == 200:
                            print(f"响铃发送成功")
                        else:
                            print(f"响铃发送失败：{soundResult['message']}")
                    
                        # 仅获取一次账单到达时间
                        for line in file_lines:
                            # 通过目录下的文件列表匹配文件名解析到达时间
                            arrive_time = get_arrive_time_from_line(line, file_name)
                            if arrive_time:
                                arrive_times.update({bill_type: arrive_time})
                                break
                    # 检查bill_type账单的arrive_time是否存在
                    if bill_type in arrive_times:
                        print(f"{bill_type}账单到达时间：{arrive_times.get(bill_type)}\n")
                else:
                    # 该账单文件暂无
                    print(f"{file_name}--{bill_type}账单--不存在")
                    all_files_exist = False

            # 如果所有文件都存在，则退出循环
            if all_files_exist:
                print("所有文件均已找到，定时器关闭")
                break

            # 等待固定时间后重新检查 循环范围while True内
            time.sleep(timeSleepInterval)
            print("\n\n---重新检查文件...")

    except ftplib.all_errors as e:
        print(f"FTP 操作失败: {e}")
    finally:
        # 关闭 FTP 连接
        if ftp:
            ftp.quit()
            print("FTP 连接已关闭")


if __name__ == "__main__":
    # FTP 配置信息 从环境变量中安全地获取敏感信息
    ftp_ip = os.getenv('FTP_IP')  # 替换为实际 FTP IP 地址
    ftp_port = 21               # 替换为实际 FTP 端口号
    ftp_username = os.getenv('FTP_USERNAME')   # 替换为实际 FTP 用户名
    ftp_password = os.getenv('FTP_PASSWORD')   # 替换为实际 FTP 密码

    ftp_base_url = "/build"    # FTP 上的目标文件夹路径
    
    # 计算昨天的日期
    now = datetime.now(ZoneInfo('Asia/Shanghai'))
    daydelta = timedelta(days=1)
    last_time = now - daydelta
    last_day = last_time.strftime("%Y%m%d")

    # 定义账单类型
    bill_types = ["68", "9"]

    # 调用核心逻辑函数
    process_ftp_files(ftp_ip, ftp_port, ftp_username, ftp_password, ftp_base_url, last_day, bill_types)
