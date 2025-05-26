# Heat Exchanger Network Design

這是一個熱交換器網路設計的網頁應用程式。使用者可以輸入冷熱流體的參數，系統會計算最佳的熱交換網路配置。

## 功能

- 支援多個冷熱流體的輸入
- 計算 Pinch 點溫度
- 設計最佳熱交換網路
- 計算外部加熱和冷卻需求

## 技術棧

- 後端：Python Flask
- 前端：HTML, JavaScript
- 部署：Render.com

## 安裝步驟

1. 安裝 Python 依賴：
```bash
pip install -r requirements.txt
```

2. 啟動後端伺服器：
```bash
python server.py
```

3. 在瀏覽器中打開 `index.html` 文件

## 使用說明

1. 在網頁界面中輸入冷流和熱流的參數：
   - 起始溫度 (°C)
   - 終止溫度 (°C)
   - CP 值 (kW/°C)

2. 點擊"新增冷流"或"新增熱流"按鈕來添加更多流體

3. 點擊"計算"按鈕進行分析

4. 查看結果：
   - Pinch 溫度（熱端和冷端）
   - 外部加熱需求
   - 外部冷卻需求
   - 符合 Pinch 準則的熱交換解

## 注意事項

- 確保後端伺服器正在運行（`server.py`）
- 所有溫度單位為 °C
- CP 值單位為 kW/°C
- 最小溫差（Tmin）預設為 10°C 