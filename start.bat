@echo off
echo ==========================================
echo   Job Hunter - 智能求职推荐系统
echo ==========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未安装 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

:: 检查虚拟环境
if not exist "venv" (
    echo [初始化] 创建虚拟环境...
    python -m venv venv
)

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 安装依赖
echo [准备] 安装依赖...
pip install -r requirements.txt -q

:: 检查 .env 配置
if not exist ".env" (
    echo.
    echo [警告] 未找到 .env 配置文件！
    echo         请复制 .env.example 为 .env 并填写配置
    echo         copy .env.example .env
    echo.
    copy .env.example .env
    echo [提示] 已自动创建 .env 文件，请编辑后重新启动
    notepad .env
    pause
    exit /b 0
)

:: 启动应用
echo.
echo [启动] 正在启动 Job Hunter...
echo         访问管理面板: http://localhost:8000
echo         按 Ctrl+C 停止
echo.
python main.py
pause
