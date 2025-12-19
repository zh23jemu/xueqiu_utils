import sys
import os
import json
import time
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime
import threading

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QPlainTextEdit,
    QTimeEdit, QCheckBox, QGroupBox, QFormLayout, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QTime
from PySide6.QtGui import QTextCursor
from qt_material import apply_stylesheet

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.models.cube import Cube

class Communicate(QObject):
    print_signal = Signal(str)

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
        
        self.init_ui()
        
        # 运行控制状态
        self.is_running = False
        self.current_logs = []
        
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
            except:
                self.config = {}
        else:
            self.config = {}

    def save_config(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

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
        
        btn_apply_sched = QPushButton("保存并应用定时设置")
        btn_apply_sched.clicked.connect(self.apply_schedule_settings)
        
        sched_form.addRow("运行时间:", self.time_edit)
        sched_form.addRow(self.weekdays_checkbox)
        sched_form.addRow(btn_apply_sched)
        sched_group.setLayout(sched_form)
        settings_layout.addWidget(sched_group)
        
        # 邮件通知设置
        email_group = QGroupBox("邮件通知设置")
        email_form = QFormLayout()
        self.smtp_server = QLineEdit(self.config.get("smtp_server", "smtp.qq.com"))
        self.smtp_port = QLineEdit(self.config.get("smtp_port", "465"))
        self.sender_email = QLineEdit(self.config.get("sender_email", ""))
        self.sender_pwd = QLineEdit(self.config.get("sender_pwd", ""))
        self.sender_pwd.setEchoMode(QLineEdit.Password)
        self.receiver_email = QLineEdit(self.config.get("receiver_email", ""))
        
        email_form.addRow("SMTP服务器:", self.smtp_server)
        email_form.addRow("端口:", self.smtp_port)
        email_form.addRow("发件人邮箱:", self.sender_email)
        email_form.addRow("授权码/密码:", self.sender_pwd)
        email_form.addRow("收件人邮箱:", self.receiver_email)
        
        btn_save_email = QPushButton("保存邮件设置")
        btn_save_email.clicked.connect(self.save_email_settings)
        email_form.addRow(btn_save_email)
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
        self.config["smtp_server"] = self.smtp_server.text()
        self.config["smtp_port"] = self.smtp_port.text()
        self.config["sender_email"] = self.sender_email.text()
        self.config["sender_pwd"] = self.sender_pwd.text()
        self.config["receiver_email"] = self.receiver_email.text()
        self.save_config()
        QMessageBox.information(self, "成功", "邮件设置已保存")

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
        self.is_running = True
        self.log("程序启动运行...")
        
        json_path = self.file_path_edit.text()
        if not json_path or not os.path.exists(json_path):
            self.log("错误: 未指定 JSON 文件或文件不存在!")
            self.finish_run()
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
                        # 如果是像 cubes.json 这样的字典格式，Key 就是组合 ID
                        cube_list = list(data.keys())
                else:
                    self.log("错误: JSON 格式异常。")
                    self.finish_run()
                    return
            
            self.log(f"成功读取 JSON。共发现 {len(cube_list)} 个组合: {', '.join(cube_list)}")
        except Exception as e:
            self.log(f"读取 JSON 失败: {e}")
            self.finish_run()
            return

        for c in cube_list:
            if not self.is_running:
                self.log("程序已被用户手动停止。")
                break
            if not c: continue
            try:
                self.log(f"正在获取组合信息: {c} ...")
                cb = Cube(c)
                info = cb.get_basic_info()
                self.log(f">>> 组合名称: {info['name']}")
                self.log(f"    当前净值: {info['value']}")
                self.log(f"    创建时间: {info['created_on']}")
                
                # 获取今日调仓
                rebalances = cb.get_specific_day_rebalance()
                if rebalances:
                    for rb in rebalances:
                        for h in rb.get('rebalancing_histories', []):
                            updated_at = datetime.fromtimestamp(h['updated_at']/1000).strftime('%Y-%m-%d %H:%M:%S')
                            prev = h.get('prev_weight', 0.0) or 0.0
                            target = h.get('target_weight', 0.0)
                            trade = '买入' if target > prev else '卖出'
                            self.log(f"    [*] 调仓: {h['stock_name']} | {trade} | {prev:.2f}% -> {target:.2f}% | 价格: {h['price']} | 时间: {updated_at}")
                else:
                    self.log(f"    [-] 今日该组合无调仓记录")
                
            except Exception as e:
                self.log(f"获取组合 {c} 详情时出错: {e}")
            
            # 模拟 main.py 中的延时，避免请求过快
            time.sleep(2)

        self.log("程序运行结束。")
        self.log("="*50)
        
        # 发送邮件
        self.send_email()
        self.finish_run()

    def finish_run(self):
        self.is_running = False
        # 回到主线程恢复按钮
        def restore_btn():
            self.btn_run_now.setEnabled(True)
            self.btn_stop.setEnabled(False)
        QTimer.singleShot(0, restore_btn)

    def send_email(self):
        sender = self.sender_email.text()
        receiver = self.receiver_email.text()
        pwd = self.sender_pwd.text()
        host = self.smtp_server.text()
        port_str = self.smtp_port.text()
        
        if not all([sender, receiver, pwd, host, port_str]):
            self.log("邮件配置不全，已跳过邮件同步。")
            return
            
        try:
            port = int(port_str)
            content = "\n".join(self.current_logs)
            message = MIMEText(content, 'plain', 'utf-8')
            message['From'] = sender
            message['To'] = receiver
            date_str = datetime.now().strftime('%Y-%m-%d')
            message['Subject'] = Header(f"雪球组合监控日报 - {date_str}", 'utf-8')

            # 这里默认使用 SSL 方式，通常 465 端口需要
            if port == 465:
                server = smtplib.SMTP_SSL(host, port)
            else:
                server = smtplib.SMTP(host, port)
                server.starttls()
                
            server.login(sender, pwd)
            server.sendmail(sender, [receiver], message.as_string())
            server.quit()
            self.log("邮件同步成功！")
        except Exception as e:
            self.log(f"邮件发送失败: {e}")

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
