import os
import requests

# 默认连本机 8000；服务端换了端口时用环境变量覆盖即可。
# 切换 MySQL / 本地存储后端不需要改动客户端。
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
current_token = None
current_role = None


def read_int(prompt, allow_blank=False):
# 读一个整数输入；输错只给提示并返回 None，不让客户端抛异常崩溃。allow_blank=True 用于「直接回车返回」的场景，此时空输入不算错误。
    raw = input(prompt).strip()
    if allow_blank and raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        print("\n 请输入有效的纯数字！")
        return None


def send_request(method, path, json_data=None):
    headers = {}
    if current_token:
        headers["Authorization"] = f"Bearer {current_token}"#检验token

    url = f"{BASE_URL}{path}"#拼接完整地址
    try:
        if method == "GET":
            return requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            return requests.post(url, headers=headers, json=json_data, timeout=10)
        elif method == "PUT":
            return requests.put(url, headers=headers, json=json_data, timeout=10)
        elif method == "PATCH":
            return requests.patch(url, headers=headers, json=json_data, timeout=10)
        elif method == "DELETE":
            return requests.delete(url, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"\n 网络连接失败！请确保服务端已启动。详细错误: {e}")
        return None


def login():
    global current_token, current_role
    print("\n--- 登录 ---")
    username = input("请输入用户名: ")
    password = input("请输入密码: ")

    try:
        response = requests.post(
            f"{BASE_URL}/login",
            data={"username": username, "password": password},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        print(f"\n 登录失败：无法连接服务端。详细错误: {e}")
        return False

    if response.status_code == 200:
        data = response.json()
        current_token = data["access_token"]
        current_role = data.get("role", "student")
        print(f"\n 登录成功！欢迎你，{username}（{current_role}）。")
        return True
    else:
        print(f"\n 登录失败: {response.json().get('detail', '未知错误')}")
        return False


# --- 学生菜单 ---
def student_menu():
    while True:
        print("\n" + "=" * 30)
        print("      学生选课菜单")
        print("=" * 30)
        print("1. 查看全部课程")
        print("2. 搜索课程 (支持按学分排序)")
        print("3. 查看课程详情及剩余名额")
        print("4. 查看我的课程")
        print("5. 选择课程")
        print("6. 退选课程")
        print("7. 修改我的密码")
        print("0. 退出登录")
        choice = input("请选择操作: ")

        if choice == "1":
            res = send_request("GET", "/courses")
            if res and res.status_code == 200:
                print("\n================ 课程列表 ================")
                for c in res.json():
                    print(
                        f"ID: {c['id']} | 编号: {c['course_code']} | {c['course_name']} | 教师: {c['teacher']} | 学分: {c['credits']} | 状态: {c['status']}")
            elif res:
                print(f"\n失败: {res.text}")

        elif choice == "2":
            keyword = input("请输入搜索关键词: ")
            sort_by = input("排序方式 (id / credits / capacity / remaining 按剩余名额，直接回车默认): ")
            # 拼接 URL 参数
            url = f"/courses?keyword={keyword}"
            if sort_by: url += f"&sort_by={sort_by}"

            res = send_request("GET", url)
            if res and res.status_code == 200:
                print(f"\n--- 搜索结果 ---")
                for c in res.json():
                    seats = c.get("remaining_seats")
                    seats_text = "未知" if seats is None else str(seats)
                    print(f"[{c['id']}] {c['course_name']} | 教师: {c['teacher']} | 学分: {c['credits']} | 剩余名额: {seats_text}")
            elif res:
                print(f"\n失败: {res.text}")



        elif choice == "3":

            # 防御 1：非数字输入只给提示，不拼进 URL、不让程序崩溃
            course_id = read_int("请输入要查看的课程 ID: ")
            if course_id is None:
                continue

            res = send_request("GET", f"/courses/{course_id}")

            if res and res.status_code == 200:

                data = res.json()

                print("\n--- 课程详情 ---")

                # 防御 2：用 .get() 取值，就算后端少返回了字段，也不会闪退报错

                print(f"课程名称: {data.get('course_name', '未知')}")

                print(f"授课教师: {data.get('teacher', '未知')}")

                print(f"总容量: {data.get('capacity', 0)} 人")

                print(f"已选人数: {data.get('enrolled_count', 0)} 人")

                print(f"剩余名额: {data.get('remaining_seats', 0)} 人")

                print(f"课程状态: {data.get('status', '未知')}")

            elif res:

                print(f"\n失败: {res.text}")

        elif choice == "4":
            res = send_request("GET", "/me/courses")
            if res and res.status_code == 200:
                print("\n--- 我的已选课程 ---")
                for c in res.json():
                    print(f"[{c['id']}] {c['course_name']}")
            elif res:
                print(f"\n失败: {res.text}")

        elif choice == "5":
            course_id = read_int("请输入要选的课程 ID: ")
            if course_id is None:
                continue
            res = send_request("POST", f"/courses/{course_id}/enroll")
            if res: print(f"\n结果: {res.json().get('message', res.json().get('detail'))}")

        elif choice == "6":
            course_id = read_int("请输入要退的课程 ID: ")
            if course_id is None:
                continue
            res = send_request("DELETE", f"/courses/{course_id}/enroll")
            if res: print(f"\n结果: {res.json().get('message', res.json().get('detail'))}")
        elif choice == "7":
            print("\n--- 修改密码 ---")
            old_pwd = input("请输入原密码: ")
            new_pwd = input("请输入新密码 (至少6位): ")

            # 发给后端的 JSON 数据
            payload = {"old_password": old_pwd, "new_password": new_pwd}

            res = send_request("PATCH", "/users/me/password", payload)

            if res:
                if res.status_code == 200:
                    print(f"\n{res.json().get('message')}")
                    print("为了安全，系统将自动退出，请使用新密码重新登录。")
                    break  # 直接跳出循环，回到主菜单（相当于强制重新登录）
                else:
                    print(f"\n修改失败！原因: {res.json().get('detail')}")
            else:
                print("\n网络异常，未收到响应")
        elif choice == "0":
            break


# --- 管理员菜单 ---
def admin_menu():
    while True:
        print("\n" + "=" * 30)
        print("      管理员后台菜单")
        print("=" * 30)
        print("1. 创建学生")
        print("2. 查看所有学生")
        print("3. 启用/停用学生")
        print("4. 创建课程")
        print("5. 修改课程状态 (开/关)")
        print("6. 删除课程")
        print("7. 查看某门课的选课名单")
        print("8. 查看课程选课统计 (新)")
        print("9. 查看课程列表")
        print("0. 退出登录")
        choice = input("请选择操作: ")

        if choice == "1":
            username = input("输入新学生用户名: ")
            pwd = input("输入密码: ")
            res = send_request("POST", "/users/", {"username": username, "password": pwd, "role": "student"})
            if res: print(f"\n结果: {res.json().get('username', res.json().get('detail'))}")


        elif choice == "2":
            #  注意这里的斜杠，必须和后端一致
            res = send_request("GET", "/users/")
            # 先判断网络是否断开
            if res is None:
                continue
            if res.status_code == 200:
                users = res.json()
                if not users:
                    print("\n当前系统里还没有学生。")
                else:
                    print("\n================ 学生列表 ================")

                    for u in users:
                        status_text = " 启用" if u['is_active'] else " 禁用"

                        print(
                            f"ID: {u['id']:2} | 用户名: {u['username']:10} | 角色: {u['role']:7} | 状态: {status_text}")

                    print("==========================================")

            else:

                #  如果报错了，把后端真实的报错打印出来！

                print(f"\n 获取学生列表失败！状态码: {res.status_code}")

                print(f"报错详情: {res.text}")

                if res.status_code in [401, 403]:
                    print(" 提示：请确认你当前登录的是 admin 账号！")
        elif choice == "3":
            uid = read_int("输入学生 ID: ")
            if uid is None:
                continue
            status = input("输入 1 启用 / 0 停用: ")

            #  关键：因为后端改成了接收 Pydantic 模型（JSON），所以这里必须传字典
            is_active_bool = True if status == "1" else False
            payload = {"is_active": is_active_bool}

            res = send_request("PATCH", f"/users/{uid}/status", payload)

            if res:
                if res.status_code == 200:
                            # 根据返回的 is_active 动态打印状态
                    current_status = "启用" if res.json().get('is_active') else "停用"
                    print(f"\n操作成功！该用户当前状态: {current_status}")
                else:
                    print(f"\n 操作失败！原因: {res.json().get('detail')}")
            else:
                print("\n 网络异常，未收到响应")

        elif choice == "4":
            code = input("输入课程编号: ")
            name = input("输入课程名称: ")
            teacher = input("输入教师名: ")
            # 容量输错（字母/空/0/负数）只提示并回到菜单，不再 int() 直接崩溃
            capacity = read_int("输入容量: ")
            if capacity is None:
                continue
            if capacity <= 0:
                print("\n 容量必须是大于 0 的整数！")
                continue
            res = send_request("POST", "/courses",
                               {"course_code": code, "course_name": name, "teacher": teacher, "credits": 2,
                                "capacity": capacity})
            if res: print(f"\n创建结果: {res.json().get('course_name', res.json().get('detail'))}")

        elif choice == "5":
            course_id = read_int("输入要操作的课程 ID: ")
            if course_id is None:
                continue
            status = input("输入 open (开放) 或 closed (关闭): ")
            res = send_request("PATCH", f"/courses/{course_id}/status", {"status": status})
            if res: print(f"\n修改状态结果: {res.json().get('message', res.json().get('detail', '修改成功'))}")

        elif choice == "6":
            course_id = read_int("输入要删除的课程 ID: ")
            if course_id is None:
                continue
            res = send_request("DELETE", f"/courses/{course_id}")
            if res: print(f"\n删除结果: {res.json().get('message', res.json().get('detail'))}")

        elif choice == "7":
            course_id = read_int("输入课程 ID 查看名单: ")
            if course_id is None:
                continue
            res = send_request("GET", f"/courses/{course_id}/students")
            if res and res.status_code == 200:
                print("\n--- 选课名单 ---")
                for u in res.json():
                    print(f"学生: {u['username']}")
            elif res:
                print(f"\n 失败: {res.text}")

        # 在对应的位置加上elif：
        elif choice == "8":
            course_id = read_int("输入要查看统计的课程 ID: ")
            if course_id is None:
                continue
            res = send_request("GET", f"/courses/{course_id}/stats")
            if res and res.status_code == 200:
                data = res.json()
                print("\n---  课程选课统计 ---")
                print(f"课程名称: {data['course_name']}")
                print(f"总容量: {data['capacity']}")
                print(f"已选人数: {data['enrolled_count']}")
                print(f"剩余名额: {data['remaining_seats']}")
                print(f"满员率: {data['fill_rate']}")
            elif res:
                print(f"\n 失败: {res.text}")

        elif choice == "9":
            # 查看课程列表，并可进一步查看某门课的详情
            res = send_request("GET", "/courses")
            if res and res.status_code == 200:
                print("\n================ 课程列表 ================")
                for c in res.json():
                    print(
                        f"ID: {c['id']} | 编号: {c['course_code']} | {c['course_name']} | 教师: {c['teacher']} | 学分: {c['credits']} | 状态: {c['status']}")
                print("==========================================")

                course_id = read_int("输入课程 ID 查看详情，直接回车返回: ", allow_blank=True)
                if course_id is not None:
                    res2 = send_request("GET", f"/courses/{course_id}")
                    if res2 and res2.status_code == 200:
                        d = res2.json()
                        print("\n--- 课程详情 ---")
                        print(f"课程名称: {d.get('course_name', '未知')}")
                        print(f"授课教师: {d.get('teacher', '未知')}")
                        print(f"总容量: {d.get('capacity', 0)} 人")
                        print(f"已选人数: {d.get('enrolled_count', 0)} 人")
                        print(f"剩余名额: {d.get('remaining_seats', 0)} 人")
                        print(f"课程状态: {d.get('status', '未知')}")
                    elif res2:
                        print(f"\n 失败: {res2.text}")
            elif res:
                print(f"\n 失败: {res.text}")

        elif choice == "0":
            break



def main():
    while True:
        print("\n" + "=" * 30)
        print("欢迎使用 校园选课系统")
        print("=" * 30)
        print("1. 登录")
        print("0. 退出系统")
        choice = input("请选择操作: ")

        if choice == "1":
            if login():
                if current_role == "admin":
                    admin_menu()
                else:
                    student_menu()
        elif choice == "0":
            print("感谢使用，再见！")
            break


if __name__ == "__main__":
    main()

#终端交互