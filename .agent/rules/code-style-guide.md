---
trigger: always_on
---

# Python Development Rules

## Python版本
- 使用 Python 3.10
- 运行命令统一使用 `python3` 而非 `python`

## 虚拟环境
- 创建虚拟环境：`python3 -m venv venv`
- 激活命令：`source venv/bin/activate`（Mac/Linux）
- 安装依赖前必须确保虚拟环境已激活
- 安装依赖：`python3 -m pip install -r requirements.txt`

## 运行命令规范
- 运行脚本：`python3 script.py`
- 安装包：`python3 -m pip install <package>`
- 运行模块：`python3 -m <module>`
- 运行测试：`python3 -m pytest tests/`
- 格式化代码：`python3 -m black .`
- 类型检查：`python3 -m mypy src/`

## 代码规范
- 遵循PEP 8代码风格
- 函数和类需要docstring文档
- 使用类型注解（Type Hints）

## 依赖管理
- 更新依赖：`python3 -m pip freeze > requirements.txt`
- 升级pip：`python3 -m pip install --upgrade pip`