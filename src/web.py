import json, os, sys, tempfile
from flask import Flask, request, jsonify, session, redirect, send_file
from flask_cors import CORS
from functools import wraps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import Database
from db_loader import load_user_sow_data
from main import run_pipeline_from_sow_list
from sow_types import SOW_TYPES

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

CORS(app, supports_credentials=True, resources={r"/api/*": {
    "origins": os.environ.get("CORS_ORIGINS", "*"),
}})

db = Database()
APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(APP_DIR)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route('/')
def index():
    with open(os.path.join(ROOT, 'src', 'frontend.html')) as f:
        return f.read()


@app.route('/api/me', methods=['GET'])
def api_me():
    user_id = session.get("user_id")
    if user_id:
        user = db.get_user(user_id)
        if user:
            return jsonify(user)
    return jsonify({"error": "Not authenticated"}), 401


@app.route('/api/login', methods=['POST'])
def api_login():
    d = request.get_json()
    u = (d.get('username') or '').strip()
    p = d.get('password') or ''
    if not u or not p:
        return jsonify({'error': 'Username and password required'}), 400
    user = db.authenticate_user(u, p)
    if user:
        session["user_id"] = user["id"]
        session.permanent = True
        return jsonify(user)
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/users', methods=['GET'])
@login_required
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
        user = db.get_user(uid)
        session["user_id"] = uid
        return jsonify({'id': uid, 'username': u, 'email': e})
    except Exception as ex:
        return jsonify({'error': str(ex)}), 400


@app.route('/api/assets', methods=['GET'])
@login_required
def api_assets():
    uid = session["user_id"]
    assets = db.list_assets(uid)
    for a in assets:
        vals = db.get_asset_monthly_values(uid, a['id'])
        a['monthly_values'] = vals
        a['latest_month'] = max(vals.keys()) if vals else None
        a['latest_value'] = vals.get(a['latest_month'], 0) if a['latest_month'] else 0
    return jsonify(assets)


@app.route('/api/assets', methods=['POST'])
@login_required
def api_add_asset():
    d = request.get_json()
    uid = session["user_id"]
    name = (d.get('name') or '').strip()
    st = (d.get('sow_type') or '').strip()
    if not name or not st:
        return jsonify({'error': 'Fields required'}), 400
    if st not in SOW_TYPES:
        return jsonify({'error': 'Invalid type: ' + st}), 400
    try:
        aid = db.create_asset(uid, name, st)
        return jsonify({'id': aid, 'name': name, 'sow_type': st})
    except Exception as ex:
        return jsonify({'error': str(ex)}), 400


@app.route('/api/assets/<int:aid>', methods=['PUT'])
@login_required
def api_update_asset(aid):
    uid = session["user_id"]
    d = request.get_json()
    n = (d.get('name') or '').strip() or None
    st = (d.get('sow_type') or '').strip() or None
    try:
        db.update_asset(uid, aid, name=n, sow_type=st)
        return jsonify({'ok': True})
    except Exception as ex:
        return jsonify({'error': str(ex)}), 400


@app.route('/api/assets/<int:aid>', methods=['DELETE'])
@login_required
def api_delete_asset(aid):
    uid = session["user_id"]
    db.delete_asset(uid, aid)
    return jsonify({'ok': True})


@app.route('/api/assets/<int:aid>/mv', methods=['GET'])
@login_required
def api_get_mv(aid):
    uid = session["user_id"]
    return jsonify({'monthly_values': db.get_asset_monthly_values(uid, aid)})


@app.route('/api/assets/<int:aid>/mv', methods=['POST'])
@login_required
def api_set_mv(aid):
    d = request.get_json()
    uid = session["user_id"]
    m = (d.get('month') or '').strip()
    v = d.get('value')
    if not m or v is None:
        return jsonify({'error': 'Fields required'}), 400
    try:
        db.set_monthly_value(uid, aid, m, float(v))
        return jsonify({'ok': True})
    except Exception:
        return jsonify({'error': 'Invalid value'}), 400


@app.route('/api/assets/<int:aid>/mv/<month>', methods=['DELETE'])
@login_required
def api_del_mv(aid, month):
    uid = session["user_id"]
    db.delete_monthly_value(uid, aid, month)
    return jsonify({'ok': True})


@app.route('/api/forecast', methods=['POST'])
@login_required
def api_forecast():
    d = request.get_json()
    uid = session["user_id"]
    sow_list = load_user_sow_data(db, uid)
    if not sow_list:
        return jsonify({'error': 'No assets'}), 400

    user_overrides = db.get_user_sow_overrides(uid)
    req_growth = dict(d.get('growth_overrides', {}))
    req_min = dict(d.get('min_growth_overrides', {}))
    req_max = dict(d.get('max_growth_overrides', {}))
    req_contrib = dict(d.get('contribution_overrides', {}))
    for st, o in user_overrides.items():
        if o.get('annual_growth') is not None and st not in req_growth:
            req_growth[st] = o['annual_growth']
        if o.get('monthly_contribution') is not None and st not in req_contrib:
            req_contrib[st] = o['monthly_contribution']
        if o.get('min_growth') is not None and st not in req_min:
            req_min[st] = o['min_growth']
        if o.get('max_growth') is not None and st not in req_max:
            req_max[st] = o['max_growth']

    result = run_pipeline_from_sow_list(
        sow_list=sow_list,
        forecast_months=d.get('forecast_months', 12),
        stochastic=d.get('stochastic', False),
        monte_carlo_runs=d.get('monte_carlo_runs', 500),
        growth_overrides=req_growth,
        min_growth_overrides=req_min,
        max_growth_overrides=req_max,
        contribution_overrides=req_contrib,
        sow_contribution_overrides=d.get('sow_contribution_overrides', {}),
    )
    return jsonify(result)


@app.route('/api/settings', methods=['GET'])
@login_required
def api_get_settings():
    from sow_types import SOW_TYPES
    uid = session["user_id"]
    overrides = db.get_user_sow_overrides(uid)
    types = []
    for key, t in SOW_TYPES.items():
        o = overrides.get(key, {})
        types.append({
            "key": key,
            "label": t.label,
            "is_asset": t.is_asset,
            "defaults": {
                "annual_growth": t.default_annual_growth,
                "monthly_contribution": t.default_monthly_contribution,
            },
            "overrides": {
                "annual_growth": o.get("annual_growth"),
                "monthly_contribution": o.get("monthly_contribution"),
                "min_growth": o.get("min_growth"),
                "max_growth": o.get("max_growth"),
            },
        })
    return jsonify({"sow_types": types})


@app.route('/api/settings', methods=['PUT'])
@login_required
def api_save_settings():
    d = request.get_json()
    uid = session["user_id"]
    overrides = d.get("overrides", {})
    cleaned = {}
    for st, fields in overrides.items():
        entry = {}
        for k in ("annual_growth", "monthly_contribution", "min_growth", "max_growth"):
            v = fields.get(k)
            if v is None or v == "":
                entry[k] = None
            else:
                try:
                    entry[k] = float(v)
                except (TypeError, ValueError):
                    entry[k] = None
        has_any = any(entry.get(k) is not None for k in entry)
        if has_any:
            cleaned[st] = entry
        else:
            db.delete_user_sow_override(uid, st)
    if cleaned:
        db.set_user_sow_overrides(uid, cleaned)
    return jsonify({"ok": True})


@app.route('/api/import', methods=['POST'])
@login_required
def api_import():
    uid = session["user_id"]
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
@login_required
def api_import_sample():
    uid = session["user_id"]
    sp = os.path.join(APP_DIR, 'sample_data', 'sample_assets.xlsx')
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


@app.route('/api/template', methods=['GET'])
def api_template():
    path = os.path.join(APP_DIR, 'sample_data', 'template_assets.xlsx')
    if not os.path.exists(path):
        return jsonify({'error': 'Template not found'}), 404
    return send_file(path, as_attachment=True, download_name='asset_import_template.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    print(f'LocusAdvisory Web Server on http://127.0.0.1:{port}')
    app.run(host='0.0.0.0', port=port, debug=False)