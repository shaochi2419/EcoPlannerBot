from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 啟用 CORS 支持

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = request.get_json()
        
        # 獲取輸入數據
        cold_streams = data.get('cold_streams', [])
        hot_streams = data.get('hot_streams', [])
        tmin_min = data.get('tmin_min', 2)
        tmin_max = data.get('tmin_max', 30)
        tmin_step = data.get('tmin_step', 0.5)
        
        # TODO: 在這裡實現您的計算邏輯
        # 這是一個示例響應
        result = {
            'status': 'success',
            'tmin': 10,  # 最佳 Tmin
            'exch_above': [],  # Pinch 點上方的熱交換器
            'exch_below': [],  # Pinch 點下方的熱交換器
            'utility_hot': 0,  # 熱公用工程負荷
            'utility_cold': 0  # 冷公用工程負荷
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

if __name__ == '__main__':
    app.run(debug=True)