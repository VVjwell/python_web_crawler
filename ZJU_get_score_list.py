import json
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd

# 输入用户信息以查询
user_data = {
    'username': None,  # 学号
    'password': None,  # 密码
    'execution': None,  # 动态生成需要从源代码里提取
    '_eventId': 'submit'
}


# 填充user_data
def get_user_info():
    global user_data
    user_data['username'] = input("学号：")
    user_data['password'] = input("密码：")



# rsa加密
def _rsa_encrypt(password_str, e_str, M_str):
    password_bytes = bytes(password_str, 'ascii')
    password_int = int.from_bytes(password_bytes, 'big')
    e_int = int(e_str, 16)
    M_int = int(M_str, 16)
    result_int = pow(password_int, e_int, M_int)
    return hex(result_int)[2:].rjust(128, '0')


# 最终结果保存到txt文档里
def get_course_score(course_resp, df):
    data = json.loads(course_resp.text)
    items = data.get('items', [])
    processed_items = []
    for item in items:
        processed_items.append({
            '课程': item.get('kcmc', ''),
            '绩点': item.get('jd', ''),
            '学分': item.get('xf', ''),
            '得分': item.get('cj', '')
        })
    new_df = pd.DataFrame(processed_items)
    if not new_df.empty:
        new_df['绩点'] = pd.to_numeric(new_df['绩点'],errors='coerce')
        new_df['学分'] = pd.to_numeric(new_df['学分'], errors='coerce')
    if df is None:
        return new_df
    else:
        # 合并DataFrame
        return pd.concate([df, new_df])


# 实现模拟登录，并获取成绩单
class LoginError(Exception):
    pass


def Score_list(url1):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0'}

    # 创建session
    session = requests.session()
    session.headers = headers
    # 请求登陆界面
    try:
        res1 = session.get(url1, headers=headers, timeout=(5, 10))
        res1.raise_for_status()  # 检查响应状态
        soup1 = BeautifulSoup(res1.text, 'html.parser')
        input_tag = soup1.find('input', {'name': 'execution'})
    except requests.exceptions.RequestException as e:
        print(f"请求登录页面失败,检查是否连接校园网，而且要关梯子")
        return
    # 获得动态验证数据，需要rsa加密
    user_data['execution'] = input_tag['value']
    res1 = session.get(url='https://zjuam.zju.edu.cn/cas/v2/getPubKey', headers=headers).json()
    n, e = res1['modulus'], res1['exponent']
    encrypt_password = _rsa_encrypt(user_data['password'], e, n)
    user_data['password'] = encrypt_password
    # 进行登录
    login_response = session.post(url1, headers=headers, data=user_data)
    try:
        dec = login_response.content.decode()
        if '统一身份认证' in dec or login_response.status_code != 200:
            raise LoginError('----------登录失败，请核实账号密码重新登录----------')
        else:
            print("----------登陆成功！----------")
    except LoginError as e:
        print(e)
        return
    except Exception as e:
        print(f"登录响应解析失败：{e}")
        return
    # 这是网页重定向的目标链接，与学号有关。
    user_url = ('http://zdbk.zju.edu.cn/jwglxt/cxdy/xscjcx_cxXscjIndex.html?doType=query&gnmkdm=N5083&su=' +
                user_data['username'])
    print("----------正在获取你的成绩单----------")
    i = 1;
    # 由于网页是动态刷新的，所以需要使用动态请求头
    df = None
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
            # 时间戳验证
            timestamp = int(time.time())
            payload = {
                'xn': '',
                'xq': '',
                'zscjl': '',
                'zscjr': '',
                '_search': 'false',
                'queryModel.showCount': 15,
                'queryModel.currentPage': i,  # 展示成绩第几页
                'queryModel.sortName': 'xkkh',
                'queryModel.sortOrder': 'asc',
                'time': Time,  # 表示点击次数
                'nd': timestamp * 1000
            }
            dynmic_headers['Cookie'] = '; '.join([f"{c.name}={c.value}" for c in session.cookies])
            course_resp = session.post(url=user_url, headers=dynmic_headers, data=payload)
            # 检查响应状态码
            if course_resp.status_code == 200:
                df = pd.concat([df,get_course_score(course_resp, None)],ignore_index=True)
                Time += 1
                i += 1
            else:
                print(f"请求失败，状态码：{course_resp.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"请求过程中发生错误：{e}")
    ori_df = df
    df = df[df['得分'] != '弃修']
    total_credits = df['学分'].sum()
    gpa_total = (df['绩点']*df['学分']).sum()
    gpa = round(gpa_total / total_credits, 2)

    try:
        ori_df.to_csv(f'所有课程均绩{gpa}_成绩单.csv', encoding='utf-8')
        print(f'所有课程平均绩点：{gpa}\n已经打印好成绩单，保存为csv，使用excel打开即可')
    except Exception as e:
        print('如果已打开成绩单.csv，请关闭后再生成')





if __name__ == '__main__':
    get_user_info()
    log_url = 'https://zjuam.zju.edu.cn/cas/login?service=http%3A%2F%2Fzdbk.zju.edu.cn%2Fjwglxt%2Fxtgl%2Flogin_ssologin.html'
    Score_list(log_url)
