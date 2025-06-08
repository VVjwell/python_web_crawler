import json
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
# 输入用户信息以查询
user_data = {
    'username': None,  # 学号
    'password': None,  # 密码
    'execution': None,  # 动态生成需要从源代码里提取
    '_eventId': 'submit'
}

def GPAto4(df):
    # 初始化新列
    df['4分制绩点'] = np.nan  # 默认NaN

    # 统一处理 "得分" 列（兼容数字、字母、中文）
    for idx, row in df.iterrows():
        score = str(row['得分']).strip()  # 转为字符串并去除空格

        # 1. 处理百分制数字（如 "85"）
        if score.isdigit():
            score_num = float(score)
            if score_num >= 86:
                df.at[idx, '4分制绩点'] = 4.0
            elif 83 <= score_num <= 85:
                df.at[idx, '4分制绩点'] = 3.9
            elif 80 <= score_num <= 82:
                df.at[idx, '4分制绩点'] = 3.6
            elif 77 <= score_num <= 79:
                df.at[idx, '4分制绩点'] = 3.3
            elif 74 <= score_num <= 76:
                df.at[idx, '4分制绩点'] = 3.0
            elif 71 <= score_num <= 73:
                df.at[idx, '4分制绩点'] = 2.7
            elif 68 <= score_num <= 70:
                df.at[idx, '4分制绩点'] = 2.4
            elif 65 <= score_num <= 67:
                df.at[idx, '4分制绩点'] = 2.1
            elif 62 <= score_num <= 64:
                df.at[idx, '4分制绩点'] = 1.8
            elif 60 <= score_num <= 61:
                df.at[idx, '4分制绩点'] = 1.5
            else:
                df.at[idx, '4分制绩点'] = 0.0

        # 2. 处理五级制（A/B/C/D/F）
        elif score.upper() in ['A', 'B', 'C', 'D', 'F']:
            grade_map = {'A': 4.0, 'B': 3.5, 'C': 2.5, 'D': 1.5, 'F': 0.0}
            df.at[idx, '4分制绩点'] = grade_map[score.upper()]

        # 3. 处理二级制（合格/不合格）
        elif score in ['合格', '不合格']:
            df.at[idx, '4分制绩点'] = 3.0 if score == '合格' else 0.0
        # 4.A+ A A-
        elif score.upper() in ['A+','A','A-' 'B+','B','B-',  'C+','C','C-',   'D', 'F']:
            grade_map = {'A+':4.0,'A':4.0,'A-':4.0,
                         'B+':3.8,'B':3.5,'B-':3.2,
                         'C+':2.8,'C':2.5,'C-':2.2,
                         'D':1.5, 'F':0}
            df.at[idx, '4分制绩点'] = grade_map[score.upper()]
        # 5 优秀 良好 中等 及格 不及格
        elif score in ['优秀', '良好', '中等', '及格' ,'不及格']:
            grade_map = {
                '优秀':4.0, '良好':3.5, '中等':2.5, '及格':1.5, '不及格':0.0
            }
            df.at[idx,'4分制绩点'] = grade_map[score]

    return df

# 填充user_data
def get_user_info():
    global user_data
    user_data['username'] = input("学号：")
    user_data['password'] = input("密码：")


def remake(df):
    def assign_score_priority(score):
        # 1. 百分制：直接使用数值
        if score.isdigit():
            return float(score)

        # 2. 五级制（A > B > C > D > F）
        elif score.upper() in ['A', 'B', 'C', 'D', 'F']:
            priority_map = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}
            return priority_map[score.upper()]

        # 3. 二级制（合格 > 不合格）
        elif score in ['合格', '不合格']:
            priority_map = {'合格': 2, '不合格': 1}
            return priority_map[score]

        # 4. A+/A/A-等
        elif score.upper() in ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F']:
            priority_map = {
                'A+': 11, 'A': 10, 'A-': 9,
                'B+': 8, 'B': 7, 'B-': 6,
                'C+': 5, 'C': 4, 'C-': 3,
                'D': 2, 'F': 1
            }
            return priority_map[score.upper()]
        # 5.优秀等
        elif score in ['优秀', '良好', '中等', '及格' ,'不及格']:
            priority_map = {
                '优秀':6,'良好':5, '中等':4, '及格':3 ,'不及格':2
            }
            return priority_map[score.upper()]
    # 为成绩分配优先级
    df['score_priority'] = df['得分'].apply(assign_score_priority)
    # 识别重名课程（课程列重复）
    course_counts = df['课程'].value_counts()
    duplicate_courses = course_counts[course_counts > 1].index
    if len(duplicate_courses) > 0:
        # 分离重名课程和非重名课程
        df_duplicates = df[df['课程'].isin(duplicate_courses)]
        df_non_duplicates = df[~df['课程'].isin(duplicate_courses)]

        # 对重名课程按优先级排序，保留最高分的记录
        df_duplicates = df_duplicates.sort_values('score_priority', ascending=False)
        df_remake = df_duplicates.groupby('课程').first().reset_index()

        # 合并非重名课程和处理后的重名课程
        df_remake = pd.concat([df_non_duplicates, df_remake], ignore_index=True)
    else:
        # 没有重名课程，直接返回原数据框
        df_remake = df.copy()

        # 删除临时优先级列
    df_remake = df_remake.drop(columns=['score_priority'])

    return df_remake

# rsa加密
def _rsa_encrypt(password_str, e_str, M_str):
    password_bytes = bytes(password_str, 'ascii')
    password_int = int.from_bytes(password_bytes, 'big')
    e_int = int(e_str, 16)
    M_int = int(M_str, 16)
    result_int = pow(password_int, e_int, M_int)
    return hex(result_int)[2:].rjust(128, '0')


# 最终结果保存到csv文档里
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
        return pd.concat([df, new_df])


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
    # 处理重修课程
    df_remake = remake(df)

    filter_conditions = (
            (df['得分'] != '弃修')
    )
    df_filtered = df_remake[filter_conditions].copy()
    # 计算5分GPA
    total_credits = df_filtered['学分'].sum()
    gpa_total = (df_filtered['绩点'] * df_filtered['学分']).sum()
    gpa = gpa_total / total_credits  # 使用严格四舍五入
    print(f"5分GPA: {gpa:.2f}")
    # 计算4分GPA
    df_4 = GPAto4(df_remake.copy())
    df_4_filtered = df_4[filter_conditions].copy()
    total_credits_4 = df_4_filtered['学分'].sum()
    gpa_total_4 = (df_4_filtered['4分制绩点'] * df_4_filtered['学分']).sum()
    gpa_4 = gpa_total_4 / total_credits_4 if total_credits_4 > 0 else 0
    print(f"4分GPA: {gpa_4:.2f}")
    try:
        df.to_csv(f'5分制所有课程均绩{gpa:.2f}_成绩单.csv', encoding='utf-8')
        df_4.to_csv(f'4分制所有课程均绩{gpa_4:.2f}_成绩单.csv', encoding='utf-8')
        print(f'已经打印好成绩单，保存为csv，使用excel打开即可')

    except Exception as e:
        print('如果已打开成绩单.csv，请关闭后再生成')





if __name__ == '__main__':
    get_user_info()
    log_url = 'https://zjuam.zju.edu.cn/cas/login?service=http%3A%2F%2Fzdbk.zju.edu.cn%2Fjwglxt%2Fxtgl%2Flogin_ssologin.html'
    Score_list(log_url)
