from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import itertools
import numpy as np
import os

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

@app.route('/')
def home():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

def calculate_pinch(cold_streams, hot_streams, Tmin=10):
    adj_cold = [{'id': c['id'], 'Ts': c['Ts'] + Tmin/2, 'Tt': c['Tt'] + Tmin/2, 'CP': c['CP']} for c in cold_streams]
    adj_hot = [{'id': h['id'], 'Ts': h['Ts'] - Tmin/2, 'Tt': h['Tt'] - Tmin/2, 'CP': h['CP']} for h in hot_streams]

    temp_points = sorted(set([
        *[s['Ts'] for s in adj_cold], *[s['Tt'] for s in adj_cold],
        *[s['Ts'] for s in adj_hot], *[s['Tt'] for s in adj_hot]
    ]), reverse=True)

    heat_diffs = []
    for i in range(len(temp_points)-1):
        T1, T2 = temp_points[i], temp_points[i+1]
        delta_T = T1 - T2
        CPh = sum(h['CP'] for h in adj_hot if h['Ts'] >= T1 and h['Tt'] <= T2)
        CPc = sum(c['CP'] for c in adj_cold if c['Tt'] >= T1 and c['Ts'] <= T2)
        heat_diffs.append(delta_T * (CPh - CPc))

    cum_heat = [0]
    for q in heat_diffs:
        cum_heat.append(cum_heat[-1] + q)

    min_heat = min(cum_heat)
    shifted_heat = [q - min_heat for q in cum_heat]

    heating = shifted_heat[0]
    cooling = shifted_heat[-1]

    pinch_indices = [i for i, q in enumerate(shifted_heat) if q == 0]
    pinch_temp = temp_points[pinch_indices[0]] if pinch_indices else None
    hot_pinch = pinch_temp + Tmin/2 if pinch_temp else None
    cold_pinch = pinch_temp - Tmin/2 if pinch_temp else None

    return {
        'heating_duty': heating,
        'cooling_duty': cooling,
        'pinch_temps': [hot_pinch, cold_pinch]
    }

def calculate_stream_heat(stream, pinch_temp, is_hot):
    """計算流體在 Pinch 點上方的熱量"""
    if is_hot:
        if stream['Ts'] <= pinch_temp:
            return 0
        Tt = max(pinch_temp, stream['Tt'])
        return (stream['Ts'] - Tt) * stream['CP']
    else:
        if stream['Tt'] <= pinch_temp:
            return 0
        Ts = max(pinch_temp, stream['Ts'])
        return (stream['Tt'] - Ts) * stream['CP']

def calculate_stream_heat_below(stream, pinch_temp, is_hot):
    """計算流體在 Pinch 點下方的熱量"""
    if is_hot:
        if stream['Tt'] >= pinch_temp:
            return 0
        Ts = min(pinch_temp, stream['Ts'])
        return (Ts - stream['Tt']) * stream['CP']
    else:
        if stream['Ts'] >= pinch_temp:
            return 0
        Tt = min(pinch_temp, stream['Tt'])
        return (Tt - stream['Ts']) * stream['CP']

def try_heat_exchange(hot_heats, cold_heats):
    """嘗試進行熱交換並返回交換結果"""
    exchanges = []
    external_heating = {}
    
    # 深度複製以避免修改原始數據
    hot_remaining = hot_heats.copy()
    cold_remaining = cold_heats.copy()
    
    # 對每個冷流進行配對
    for cold_id, cold_heat in list(cold_remaining.items()):
        if cold_heat <= 0:
            continue
            
        # 嘗試與每個熱流配對
        for hot_id, hot_heat in list(hot_remaining.items()):
            if hot_heat <= 0:
                continue
                
            # 計算可交換的熱量
            exchange_heat = min(hot_heat, cold_heat)
            if exchange_heat > 0:
                exchanges.append((hot_id, cold_id, exchange_heat))
                hot_remaining[hot_id] -= exchange_heat
                cold_remaining[cold_id] -= exchange_heat
                cold_heat = cold_remaining[cold_id]
                if cold_heat <= 0:
                    break
    
    # 計算需要的外部加熱
    for cold_id, remaining in cold_remaining.items():
        if remaining > 0.01:
            external_heating[cold_id] = remaining
            
    return {
        'exchanges': exchanges,
        'external_heating': external_heating
    }

def try_heat_exchange_below(hot_heats, cold_heats):
    """嘗試進行 Pinch 點下方的熱交換"""
    exchanges = []
    external_cooling = {}
    
    # 深度複製以避免修改原始數據
    hot_remaining = hot_heats.copy()
    cold_remaining = cold_heats.copy()
    
    # 對每個冷流進行配對
    for cold_id, cold_heat in list(cold_remaining.items()):
        if cold_heat <= 0:
            continue
            
        # 嘗試與每個熱流配對
        for hot_id, hot_heat in list(hot_remaining.items()):
            if hot_heat <= 0:
                continue
                
            # 計算可交換的熱量
            exchange_heat = min(hot_heat, cold_heat)
            if exchange_heat > 0:
                exchanges.append((hot_id, cold_id, exchange_heat))
                hot_remaining[hot_id] -= exchange_heat
                cold_remaining[cold_id] -= exchange_heat
                cold_heat = cold_remaining[cold_id]
                if cold_heat <= 0:
                    break
    
    # 計算需要的外部冷卻
    total_cooling = 0
    for hot_id, remaining in hot_remaining.items():
        if remaining > 0.01:
            external_cooling[hot_id] = remaining
            total_cooling += remaining
            
    # 檢查是否有剩餘的熱量需要冷卻
    if total_cooling > 0:
        return {
            'exchanges': exchanges,
            'external_cooling': external_cooling
        }
    
    return None

def normalize_solution(solution):
    """將解決方案標準化，以便比較是否為相同的熱交換方案"""
    # 收集所有熱交換量
    exchange_amounts = []
    
    # 處理上方交換
    for _, _, heat in solution['exch_above']:
        exchange_amounts.append(round(heat, 2))
        
    # 處理下方交換
    for _, _, heat in solution['exch_below']:
        exchange_amounts.append(round(heat, 2))
        
    # 將熱交換量排序，只考慮熱量大小
    exchange_amounts.sort(reverse=True)
    
    # 返回排序後的熱交換量列表
    return tuple(exchange_amounts)

def design_HEN(hot_streams, cold_streams, pinch_data):
    hot_pinch, cold_pinch = pinch_data['pinch_temps']
    target_heating = pinch_data['heating_duty']  # 目標外部加熱需求
    target_cooling = pinch_data['cooling_duty']  # 目標外部冷卻需求
    all_solutions = []
    
    # 計算每條流體在 Pinch 點上方的熱量
    hot_heats_above = {
        h['id']: calculate_stream_heat(h, hot_pinch, True)
        for h in hot_streams
    }
    cold_heats_above = {
        c['id']: calculate_stream_heat(c, cold_pinch, False)
        for c in cold_streams
    }
    
    # 計算每條流體在 Pinch 點下方的熱量
    hot_heats_below = {
        h['id']: calculate_stream_heat_below(h, hot_pinch, True)
        for h in hot_streams
    }
    cold_heats_below = {
        c['id']: calculate_stream_heat_below(c, cold_pinch, False)
        for c in cold_streams
    }
    
    # 用於追踪已經找到的獨特解決方案
    unique_solutions = set()
    
    # 生成所有可能的熱流順序（上方）
    for hot_order_above in itertools.permutations(hot_heats_above.keys()):
        # 生成所有可能的冷流順序（上方）
        for cold_order_above in itertools.permutations(cold_heats_above.keys()):
            # 按照當前順序重組熱量字典（上方）
            ordered_hot_heats_above = {h_id: hot_heats_above[h_id] for h_id in hot_order_above}
            ordered_cold_heats_above = {c_id: cold_heats_above[c_id] for c_id in cold_order_above}
            
            # 嘗試進行上方熱交換
            result_above = try_heat_exchange(ordered_hot_heats_above, ordered_cold_heats_above)
            if result_above is None:
                continue
                
            # 檢查外部加熱是否符合目標
            total_heating = sum(result_above['external_heating'].values())
            if abs(total_heating - target_heating) > 0.01:
                continue
                
            # 生成所有可能的冷流順序（下方）
            for cold_order_below in itertools.permutations(cold_heats_below.keys()):
                # 生成所有可能的熱流順序（下方）
                for hot_order_below in itertools.permutations(hot_heats_below.keys()):
                    # 按照當前順序重組熱量字典（下方）
                    ordered_hot_heats_below = {h_id: hot_heats_below[h_id] for h_id in hot_order_below}
                    ordered_cold_heats_below = {c_id: cold_heats_below[c_id] for c_id in cold_order_below}
                    
                    # 嘗試進行下方熱交換
                    result_below = try_heat_exchange_below(ordered_hot_heats_below, ordered_cold_heats_below)
                    if result_below is None:
                        continue
                        
                    # 檢查外部冷卻是否符合目標
                    total_cooling = sum(result_below['external_cooling'].values())
                    if abs(total_cooling - target_cooling) > 0.01:
                        continue
                    
                    # 創建完整的解決方案
                    solution = {
                        'exch_above': result_above['exchanges'],
                        'exch_below': result_below['exchanges'],
                        'ext_heating': result_above['external_heating'],
                        'ext_cooling': result_below['external_cooling']
                    }
                    
                    # 標準化解決方案並檢查是否為新的獨特解
                    normalized = normalize_solution(solution)
                    if normalized not in unique_solutions:
                        unique_solutions.add(normalized)
                        all_solutions.append(solution)
    
    return all_solutions

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = request.json
        if not data:
            return jsonify({'error': '沒有收到數據'}), 400
            
        cold_streams = data.get('cold_streams', [])
        hot_streams = data.get('hot_streams', [])
        
        if not cold_streams or not hot_streams:
            return jsonify({'error': '冷流或熱流數據缺失'}), 400
            
        # 獲取 Tmin 相關參數
        tmin_min = float(data.get('tmin_min', 10))
        tmin_max = float(data.get('tmin_max', 10))
        tmin_step = float(data.get('tmin_step', 1))
        
        # 如果只提供了單一 Tmin 值，就使用該值
        if tmin_min == tmin_max:
            tmin_values = [tmin_min]
        else:
            # 使用 numpy 生成一系列 Tmin 值
            tmin_values = np.arange(tmin_min, tmin_max + tmin_step/2, tmin_step).tolist()

        # 儲存每個 Tmin 值的結果
        all_results = []
        
        # 對每個 Tmin 值進行計算
        for tmin in tmin_values:
            pinch_result = calculate_pinch(cold_streams, hot_streams, tmin)
            hen_solutions = design_HEN(hot_streams, cold_streams, pinch_result)
            
            result = {
                'tmin': tmin,
                'pinch_result': pinch_result,
                'hen_solutions': hen_solutions,
                'solution_count': len(hen_solutions)
            }
            all_results.append(result)

        response = {
            'results': all_results,
            'tmin_values': tmin_values
        }

        return jsonify(response)
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': f'計算過程發生錯誤: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 