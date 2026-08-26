import json, os, sys, tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import Database
from db_loader import load_user_sow_data
from main import run_pipeline_from_sow_list
from sow_types import SOW_TYPES

app = Flask(__name__)
CORS(app)
db = Database()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@app.route('/')
def index():
    with open(os.path.join(ROOT, 'src', 'frontend.html')) as f:
        return f.read()

@app.route('/api/users', methods=['GET'])
def api_users():
    return jsonify(db.list_users())

@app.route('/api/users', methods=['POST'])
def api_create_user():
    d = request.get_json()
    u = (d.get('username') or '').strip()
    e = (d.get('email') or '').strip()
    p = d.get('password') or ''
    if not u or not e or not p:
        return jsonify({'error': 'All fields required'}), 400
    try:
        uid = db.create_user(u, e, p)
        return jsonify({'id': uid, 'username': u, 'email': e})
    except Exception as ex:
        return jsonify({'error': str(ex)}), 400

@app.route('/api/assets', methods=['GET'])
def api_assets():
    uid = request.args.get('user_id', type=int)
    if not uid:
        return jsonify({'error': 'user_id required'}), 400
    assets = db.list_assets(uid)
    for a in assets:
        vals = db.get_asset_monthly_values(uid, a['id'])
        a['monthly_values'] = vals
        a['latest_month'] = max(vals.keys()) if vals else None
        a['latest_value'] = vals.get(a['latest_month'], 0) if a['latest_month'] else 0
    return jsonify(assets)

@app.route('/api/assets', methods=['POST'])
def api_add_asset():
    d = request.get_json()
    uid = d.get('user_id')
    name = (d.get('name') or '').strip()
    st = (d.get('sow_type') or '').strip()
    if not uid or not name or not st:
        return jsonify({'error': 'Fields required'}), 400
    if st not in SOW_TYPES:
        return jsonify({'error': 'Invalid type: ' + st}), 400
    try:
        aid = db.create_asset(uid, name, st)
        return jsonify({'id': aid, 'name': name, 'sow_type': st})
    except Exception as ex:
        return jsonify({'error': str(ex)}), 400

@app.route('/api/assets/<int:aid>', methods=['PUT'])
def api_update_asset(aid):
    d = request.get_json()
    uid = d.get('user_id')
    if not uid:
        return jsonify({'error': 'user_id required'}), 400
    n = (d.get('name') or '').strip() or None
    st = (d.get('sow_type') or '').strip() or None
    try:
        db.update_asset(uid, aid, name=n, sow_type=st)
        return jsonify({'ok': True})
    except Exception as ex:
        return jsonify({'error': str(ex)}), 400

@app.route('/api/assets/<int:aid>', methods=['DELETE'])
def api_delete_asset(aid):
    uid = request.args.get('user_id', type=int)
    if not uid:
        return jsonify({'error': 'user_id required'}), 400
    db.delete_asset(uid, aid)
    return jsonify({'ok': True})

@app.route('/api/assets/<int:aid>/mv', methods=['GET'])
def api_get_mv(aid):
    uid = request.args.get('user_id', type=int)
    if not uid:
        return jsonify({'error': 'user_id required'}), 400
    return jsonify({'monthly_values': db.get_asset_monthly_values(uid, aid)})

@app.route('/api/assets/<int:aid>/mv', methods=['POST'])
def api_set_mv(aid):
    d = request.get_json()
    uid = d.get('user_id')
    m = (d.get('month') or '').strip()
    v = d.get('value')
    if not uid or not m or v is None:
        return jsonify({'error': 'Fields required'}), 400
    try:
        db.set_monthly_value(uid, aid, m, float(v))
        return jsonify({'ok': True})
    except Exception:
        return jsonify({'error': 'Invalid value'}), 400

@app.route('/api/assets/<int:aid>/mv/<month>', methods=['DELETE'])
def api_del_mv(aid, month):
    uid = request.args.get('user_id', type=int)
    if not uid:
        return jsonify({'error': 'user_id required'}), 400
    db.delete_monthly_value(uid, aid, month)
    return jsonify({'ok': True})

@app.route('/api/forecast', methods=['POST'])
def api_forecast():
    d = request.get_json()
    uid = d.get('user_id')
    if not uid:
        return jsonify({'error': 'user_id required'}), 400
    sow_list = load_user_sow_data(db, uid)
    if not sow_list:
        return jsonify({'error': 'No assets'}), 400
    result = run_pipeline_from_sow_list(
        sow_list=sow_list,
        forecast_months=d.get('forecast_months', 12),
        stochastic=d.get('stochastic', False),
        monte_carlo_runs=d.get('monte_carlo_runs', 500),
        growth_overrides=d.get('growth_overrides', {}),
        min_growth_overrides=d.get('min_growth_overrides', {}),
        max_growth_overrides=d.get('max_growth_overrides', {}),
        contribution_overrides=d.get('contribution_overrides', {}),
        sow_contribution_overrides=d.get('sow_contribution_overrides', {}),
    )
    return jsonify(result)

@app.route('/api/import', methods=['POST'])
def api_import():
    uid = request.form.get('user_id', type=int)
    if not uid:
        return jsonify({'error': 'user_id required'}), 400
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'No file'}), 400
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        f.save(tmp.name)
        try:
            c = db.import_excel_to_user(uid, tmp.name)
            return jsonify({'count': c})
        except Exception as ex:
            return jsonify({'error': str(ex)}), 400
        finally:
            os.unlink(tmp.name)

@app.route('/api/import-sample', methods=['POST'])
def api_import_sample():
    d = request.get_json()
    uid = d.get('user_id')
    if not uid:
        return jsonify({'error': 'user_id required'}), 400
    sp = os.path.join(ROOT, 'output', 'user_hkd_assets.xlsx')
    if not os.path.exists(sp):
        return jsonify({'error': 'Sample not found'}), 404
    try:
        c = db.import_excel_to_user(uid, sp)
        return jsonify({'count': c})
    except Exception as ex:
        return jsonify({'error': str(ex)}), 400

@app.route('/api/sow-types', methods=['GET'])
def api_sow_types():
    return jsonify([{
        'key': k, 'label': v.label, 'is_asset': v.is_asset,
        'default_annual_growth': v.default_annual_growth,
        'default_monthly_contribution': v.default_monthly_contribution
    } for k, v in SOW_TYPES.items()])

if __name__ == '__main__':
    print('LocusAdvisory Web Server on http://127.0.0.1:5001')
    app.run(host='0.0.0.0', port=5001, debug=False)