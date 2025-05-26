import sys
import os

# 添加應用目錄到 Python 路徑
project_home = '/home/EcoPlannerBot/mysite'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# 導入 Flask 應用
from server import app as application

if __name__ == '__main__':
    app.run() 