import sys
import os
import json
import time
import zmail
from datetime import datetime
import threading
import base64

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QPlainTextEdit,
    QTimeEdit, QCheckBox, QGroupBox, QFormLayout, QMessageBox, QDateEdit
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QTime, QDate
from PySide6.QtGui import QTextCursor
from qt_material import apply_stylesheet

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.models.cube import Cube

class Communicate(QObject):
    print_signal = Signal(str)
    finished_signal = Signal()

class XueqiuApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("雪球组合监控工具 - GUI版")
        self.resize(1000, 800)
        
        # 配置文件路径
        self.config_file = os.path.join(os.getcwd(), "gui_config.json")
        self.load_config()
        
        # 信号传输
        self.comm = Communicate()
        self.comm.print_signal.connect(self.append_log)
        self.comm.finished_signal.connect(self.on_task_finished)
        
        # 日志文件路径
        self.log_file = os.path.join(os.getcwd(), "position_ui.log")
        self.results_file = os.path.join(os.getcwd(), "last_run_results.json")
        
        self.init_ui()
        
        # 运行控制状态
        self.is_running = False
        self.current_logs = []
        self.json_logs = []
        
        # 调度器
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.update_schedule()
        
        # 初始加载预览
        if self.file_path_edit.text():
            self.preview_cubes()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                
                # 尝试解码密码
                pwd = self.config.get("sender_pwd", "")
                if pwd.startswith("b64:"):
                    try:
                        self.config["sender_pwd"] = base64.b64decode(pwd[4:]).decode('utf-8')
                    except:
                        pass
            except:
                self.config = {}
        else:
            self.config = {}

    def save_config(self):
        # 创建副本进行保存，避免修改内存中的明文配置
        config_to_save = self.config.copy()
        pwd = config_to_save.get("sender_pwd", "")
        if pwd and not pwd.startswith("b64:"):
            config_to_save["sender_pwd"] = "b64:" + base64.b64encode(pwd.encode('utf-8')).decode('utf-8')
            
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config_to_save, f, indent=4, ensure_ascii=False)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # --- 数据源设置 ---
        file_group = QGroupBox("数据源 (Cube List)")
        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit(self.config.get("json_path", ""))
        self.file_path_edit.setPlaceholderText("选择包含 cube_list 的 JSON 文件")
        self.file_path_edit.textChanged.connect(self.preview_cubes)
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self.browse_file)
        file_layout.addWidget(QLabel("JSON文件:"))
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(btn_browse)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # --- 配置面板 ---
        settings_layout = QHBoxLayout()
        
        # 定时运行设置
        sched_group = QGroupBox("定时运行设置")
        sched_form = QFormLayout()
        self.time_edit = QTimeEdit()
        default_time_str = self.config.get("run_time", "15:00")
        default_time = QTime.fromString(default_time_str, "HH:mm")
        if not default_time.isValid():
            default_time = QTime(15, 0)
        self.time_edit.setTime(default_time)
        
        self.weekdays_checkbox = QCheckBox("每周一至周五运行")
        self.weekdays_checkbox.setChecked(self.config.get("weekdays_only", True))
        
        self.query_date_edit = QDateEdit()
        self.query_date_edit.setCalendarPopup(True)
        self.set_default_query_date()
        
        btn_apply_sched = QPushButton("保存并应用定时设置")
        btn_apply_sched.clicked.connect(self.apply_schedule_settings)
        
        sched_form.addRow("运行时间:", self.time_edit)
        sched_form.addRow("查询调仓日期:", self.query_date_edit)
        sched_form.addRow(self.weekdays_checkbox)
        sched_form.addRow(btn_apply_sched)
        sched_group.setLayout(sched_form)
        settings_layout.addWidget(sched_group)
        
        # 邮件通知设置
        email_group = QGroupBox("邮件通知设置")
        email_form = QFormLayout()
        self.sender_email = QLineEdit(self.config.get("sender_email", ""))
        self.sender_pwd = QLineEdit(self.config.get("sender_pwd", ""))
        self.sender_pwd.setEchoMode(QLineEdit.Password)
        self.receiver_email = QLineEdit(self.config.get("receiver_email", ""))
        
        email_form.addRow("发件人邮箱:", self.sender_email)
        email_form.addRow("授权码/密码:", self.sender_pwd)
        email_form.addRow("收件人邮箱:", self.receiver_email)
        
        btn_save_email = QPushButton("保存邮件设置")
        btn_save_email.clicked.connect(self.save_email_settings)
        self.btn_test_email = QPushButton("发送测试邮件")
        self.btn_test_email.clicked.connect(self.test_send_email)
        
        email_btn_layout = QHBoxLayout()
        email_btn_layout.addWidget(btn_save_email)
        email_btn_layout.addWidget(self.btn_test_email)
        email_form.addRow(email_btn_layout)
        email_group.setLayout(email_form)
        settings_layout.addWidget(email_group)
        
        layout.addLayout(settings_layout)
        
        # --- 日志显示 ---
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout()
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(350)
        log_layout.addWidget(self.log_view)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # --- 控制按钮 ---
        ctrl_layout = QHBoxLayout()
        self.btn_run_now = QPushButton("立即手动运行一次")
        self.btn_run_now.clicked.connect(self.run_now)
        self.btn_run_now.setMinimumHeight(50)
        self.btn_run_now.setStyleSheet("font-weight: bold; font-size: 16px; background-color: #2e7d32;")
        
        self.btn_stop = QPushButton("停止运行")
        self.btn_stop.clicked.connect(self.stop_run)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setMinimumHeight(50)
        self.btn_stop.setStyleSheet("font-weight: bold; font-size: 16px; background-color: #c62828;")
        
        ctrl_layout.addWidget(self.btn_run_now)
        ctrl_layout.addWidget(self.btn_stop)
        layout.addLayout(ctrl_layout)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择JSON文件", "", "JSON Files (*.json)")
        if file_path:
            self.file_path_edit.setText(file_path)
            self.config["json_path"] = file_path
            self.save_config()
            self.preview_cubes()

    def preview_cubes(self):
        json_path = self.file_path_edit.text()
        if not json_path or not os.path.exists(json_path):
            return
            
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cube_list = []
            if isinstance(data, list):
                cube_list = [c for c in data if str(c).startswith("ZH")]
            elif isinstance(data, dict):
                if "cube_list" in data:
                    cube_list = [c for c in data["cube_list"] if str(c).startswith("ZH")]
                else:
                    cube_list = [k for k in data.keys() if str(k).startswith("ZH")]
            
            if cube_list:
                self.log(f"[预览] 已从文件载入 {len(cube_list)} 个组合: {', '.join(cube_list)}")
        except Exception as e:
            self.log(f"[预览] 读取 JSON 失败: {e}")

    def apply_schedule_settings(self):
        self.config["run_time"] = self.time_edit.time().toString("HH:mm")
        self.config["weekdays_only"] = self.weekdays_checkbox.isChecked()
        self.save_config()
        self.update_schedule()
        QMessageBox.information(self, "成功", "定时设置已更新并应用")

    def save_email_settings(self):
        self.config["sender_email"] = self.sender_email.text()
        self.config["sender_pwd"] = self.sender_pwd.text()
        self.config["receiver_email"] = self.receiver_email.text()
        self.save_config()
        QMessageBox.information(self, "成功", "邮件设置已保存")

    def set_default_query_date(self):
        today = QDate.currentDate()
        weekday = today.dayOfWeek()  # 1 (Monday) to 7 (Sunday)
        if weekday <= 5:
            # Mon-Fri
            self.query_date_edit.setDate(today)
        else:
            # Sat-Sun
            days_to_subtract = weekday - 5
            self.query_date_edit.setDate(today.addDays(-days_to_subtract))

    def update_schedule(self):
        self.scheduler.remove_all_jobs()
        run_time = self.time_edit.time()
        hour = run_time.hour()
        minute = run_time.minute()
        
        if self.weekdays_checkbox.isChecked():
            # Mon-Fri
            trigger = CronTrigger(day_of_week='mon-fri', hour=hour, minute=minute)
            day_desc = "周一至周五"
        else:
            # Every day
            trigger = CronTrigger(hour=hour, minute=minute)
            day_desc = "每天"
            
        self.scheduler.add_job(self.run_task, trigger)
        self.log(f"定时任务已设定: {day_desc} {run_time.toString('HH:mm')}")

    def append_log(self, text):
        self.log_view.appendPlainText(text)
        self.log_view.moveCursor(QTextCursor.End)

    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"[{timestamp}] {message}"
        self.comm.print_signal.emit(full_msg)
        self.current_logs.append(full_msg)
        
        # 写入日志文件
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(full_msg + "\n")
        except Exception as e:
            print(f"写入日志文件失败: {e}")
        return full_msg

    def run_now(self):
        if self.is_running:
            return
        self.btn_run_now.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.is_running = True
        threading.Thread(target=self.run_task, daemon=True).start()

    def stop_run(self):
        if self.is_running:
            self.is_running = False
            self.log(">>> 正在请求停止程序，请稍候...")
            self.btn_stop.setEnabled(False)

    def run_task(self):
        self.current_logs = []
        self.json_logs = []
        if not self.is_running:
            self.is_running = True
            
        try:
            query_date_str = self.query_date_edit.date().toString("yyyyMMdd")
            start_msg = self.log(f"程序启动运行... (查询日期: {query_date_str})")
            self.json_logs.append(start_msg)
            
            json_path = self.file_path_edit.text()
            if not json_path or not os.path.exists(json_path):
                self.log("错误: 未指定 JSON 文件或文件不存在!")
                return
                
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        cube_list = data
                    elif isinstance(data, dict):
                        if "cube_list" in data:
                            cube_list = data["cube_list"]
                        else:
                            cube_list = list(data.keys())
                    else:
                        self.log("错误: JSON 格式异常。")
                        return
                
                load_msg = self.log(f"成功读取 JSON。共发现 {len(cube_list)} 个组合: {', '.join(cube_list)}")
                self.json_logs.append(load_msg)
            except Exception as e:
                self.log(f"读取 JSON 失败: {e}")
                return

            for c in cube_list:
                if not self.is_running:
                    self.log("程序已被用户手动停止。")
                    break
                if not c: continue
                
                cube_temp_logs = []
                has_rebalance = False
                
                try:
                    cube_temp_logs.append(self.log(f"正在获取组合信息: {c} ..."))
                    cb = Cube(c)
                    info = cb.get_basic_info()
                    cube_temp_logs.append(self.log(f">>> 组合名称: {info['name']}"))
                    
                    # 界面可见，但不进 JSON 暂存列表
                    self.log(f"    当前净值: {info['value']}")
                    self.log(f"    创建时间: {info['created_on']}")
                    
                    query_date_str = self.query_date_edit.date().toString("yyyyMMdd")
                    rebalances = cb.get_specific_day_rebalance(query_date_str)
                    if rebalances:
                        has_rebalance = True
                        for rb in rebalances:
                            for h in rb.get('rebalancing_histories', []):
                                updated_at = datetime.fromtimestamp(h['updated_at']/1000).strftime('%Y-%m-%d %H:%M:%S')
                                prev = h.get('prev_weight', 0.0) or 0.0
                                target = h.get('target_weight', 0.0)
                                trade = '买入' if target > prev else '卖出'
                                cube_temp_logs.append(self.log(f"    [*] 调仓: {h['stock_name']} | {trade} | {prev:.2f}% -> {target:.2f}% | 价格: {h['price']} | 时间: {updated_at}"))
                    else:
                        self.log(f"    [-] 当日该组合无调仓记录")
                    
                    if has_rebalance:
                        self.json_logs.extend(cube_temp_logs)
                        
                except Exception as e:
                    self.log(f"获取组合 {c} 详情时出错: {e}")
                
                time.sleep(2)

            if self.is_running:
                end_msg1 = self.log("程序运行结束。")
                end_msg2 = self.log("="*50)
                self.json_logs.extend([end_msg1, end_msg2])
                
                # 保存运行结果到 JSON 文件
                self.save_run_results(self.json_logs)
                
                # 发送邮件
                self.send_email()
            else:
                self.log("程序被手动终止，跳过保存结果和发送邮件。")

        except Exception as e:
            self.log(f"运行过程发生未捕获异常: {e}")
            
        finally:
            self.comm.finished_signal.emit()

    def on_task_finished(self):
        self.is_running = False
        self.btn_run_now.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def save_run_results(self, logs):
        """将过滤后的运行日志保存到 JSON 文件中"""
        try:
            result_data = {
                "run_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "query_date": self.query_date_edit.date().toString("yyyyMMdd"),
                "logs": logs
            }
            with open(self.results_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, indent=4, ensure_ascii=False)
            self.log(f"运行结果已保存到: {self.results_file}")
        except Exception as e:
            self.log(f"保存运行结果失败: {e}")

    def send_email(self):
        content = "\n".join(self.json_logs)
        self._execute_send_email(content, "监控日报")

    def test_send_email(self):
        sender = self.sender_email.text()
        receiver = self.receiver_email.text()
        pwd = self.sender_pwd.text()
        
        if not all([sender, receiver, pwd]):
            QMessageBox.warning(self, "错误", "邮件配置不完整，请填写所有字段后再测试。")
            return
            
        self.log("正在准备发送测试邮件...")
        content = "这是一封来自雪球组合监控工具的测试邮件，如果您收到此邮件，说明配置正确。"
        if self._execute_send_email(content, "测试邮件"):
            QMessageBox.information(self, "成功", "测试邮件发送成功！")
        else:
            QMessageBox.critical(self, "失败", "测试邮件发送失败，请检查日志查看错误详情。")

    def _execute_send_email(self, content, subject_suffix):
        sender = self.sender_email.text()
        receiver = self.receiver_email.text()
        pwd = self.sender_pwd.text()
        
        if not all([sender, receiver, pwd]):
            self.log(f"邮件配置不全，已跳过{subject_suffix}。")
            return False
            
        try:
            server = zmail.server(sender, pwd)
            date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            mail = {
                'subject': f"雪球组合监控{subject_suffix} - {date_str}",
                'content_text': content
            }
            
            # zmail 会自动根据发件人识别 SMTP 服务器
            server.send_mail(receiver, mail)
            self.log(f"邮件({subject_suffix})同步成功！")
            return True
        except Exception as e:
            self.log(f"邮件({subject_suffix})发送失败: {e}")
            return False

class StreamProxy:
    def __init__(self, log_func):
        self.log_proxy = log_func

    def write(self, text):
        if text.strip():
            self.log_proxy(text.strip())

    def flush(self):
        pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 使用 qt-material 提升颜值
    apply_stylesheet(app, theme='dark_teal.xml')
    
    window = XueqiuApp()
    
    # 重定向 stdout
    sys.stdout = StreamProxy(window.log)
    
    window.show()
    sys.exit(app.exec())
