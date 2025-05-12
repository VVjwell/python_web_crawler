import json
import time
import requests
from bs4 import BeautifulSoup
import re

from pycparser.c_ast import Pragma
from selenium import webdriver
from urllib.parse import urlparse, parse_qs
#输入用户信息以查询
user_data = {
    'username': None,#学号
    'password': None,#密码
    'execution': None,#动态生成需要从源代码里提取
    '_eventId': 'submit'
}
#填充user_data
def get_user_info():
    global user_data
    user_data['username'] = input("输入要查询的学号：")
    user_data['password'] = input("输入密码：")
#rsa加密
def _rsa_encrypt(password_str, e_str, M_str):
    password_bytes = bytes(password_str, 'ascii')
    password_int = int.from_bytes(password_bytes, 'big')
    e_int = int(e_str, 16)
    M_int = int(M_str, 16)
    result_int = pow(password_int, e_int, M_int)
    return hex(result_int)[2:].rjust(128, '0')

#最终结果保存到txt文档里
def get_course_score(course_resp,i):
    data = json.loads(course_resp.text)
    items = data.get('items',[])
    if i == 1:
        with open('成绩.txt', 'w', encoding='utf-8') as f:
            for item in items:
                score = item.get('cj', '')
                course_name = item.get('kcmc', '')
                f.write(f"【{course_name}】的分数:{score}\n")
            f.write('\n')
    else:
        with open('成绩.txt', 'a', encoding='utf-8') as f:
            for item in items:
                score = item.get('cj', '')
                course_name = item.get('kcmc', '')
                f.write(f"【{course_name}】的分数:{score}\n")
            f.write('\n')

#实现模拟登录，并获取成绩单
def Score_list(url1):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0'}
    #创建session
    session = requests.session()
    session.headers = headers
    #请求登陆界面
    res1 = session.get(url1,headers=headers)
    soup1 = BeautifulSoup(res1.text, 'html.parser')
    form = soup1.find('form',id='fm1')
    input_tag = soup1.find('input', {'name': 'execution'})
    #获得动态验证数据，需要rsa加密
    user_data['execution']= input_tag['value']
    res1 = session.get(url='https://zjuam.zju.edu.cn/cas/v2/getPubKey',headers=headers).json()
    n, e = res1['modulus'], res1['exponent']
    encrypt_password = _rsa_encrypt(user_data['password'], e, n)
    user_data['password'] = encrypt_password
    #进行登录
    login_response = session.post(url1, headers = headers,data = user_data)
    soup2 = BeautifulSoup(login_response.text, 'html.parser')
    try:
        dec = login_response.content.decode()
        if '统一身份认证' in dec:
            raise LoginError('----------登录失败，请核实账号密码重新登录----------')
        else:
            print("----------登陆成功！----------")
    except Exception as err:
        pass
    #这是网页重定向的目标链接，与学号有关。
    user_url = 'http://zdbk.zju.edu.cn/jwglxt/cxdy/xscjcx_cxXscjIndex.html?doType=query&gnmkdm=N5083&su='+user_data['username']
    print("----------正在获取你的成绩单----------")
    i = 1;
    #由于网页是动态刷新的，所以需要使用动态请求头
    while i < 10:
        try:
            Time = 0
            dynmic_headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Encoding': 'gzip, deflate',
                'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,en-GB;q=0.6',
                'Cache-Control': 'no-cache',
                'Content-Length': '158',
                'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                'Host': 'zdbk.zju.edu.cn',
                'Origin': 'http://zdbk.zju.edu.cn',
                'Pragma': 'no-cache',
                'Proxy-Connection': 'keep-alive',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
                'X-Requested-With': 'XMLHttpRequest',
                'Cookie': '',
                'Referer': user_url
            }
            #时间戳验证
            timestamp = int(time.time())
            payload = {
                'xn': '',
                'xq': '',
                'zscjl': '',
                'zscjr': '',
                '_search': 'false',
                'queryModel.showCount': 15,
                'queryModel.currentPage': i,#展示成绩第几页
                'queryModel.sortName': 'xkkh',
                'queryModel.sortOrder': 'asc',
                'time': Time,#表示点击次数
                'nd': timestamp * 1000
            }
            dynmic_headers['Cookie'] = '; '.join([f"{c.name}={c.value}" for c in session.cookies])
            course_resp = session.post(url=user_url, headers=dynmic_headers, data=payload)
            # 检查响应状态码
            if course_resp.status_code == 200:
                soup3 = BeautifulSoup(course_resp.text, 'html.parser')
                get_course_score(course_resp,i)
                Time+=1
                i+=1
            else:
                print(f"请求失败，状态码：{course_resp.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"请求过程中发生错误：{e}")
get_user_info()
log_url ='https://zjuam.zju.edu.cn/cas/login?service=http%3A%2F%2Fzdbk.zju.edu.cn%2Fjwglxt%2Fxtgl%2Flogin_ssologin.html'
Score_list(log_url)