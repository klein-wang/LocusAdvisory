import json, os, sys, tempfile, re
from datetime import datetime
from flask import Flask, request, jsonify, session, redirect, send_file
from flask_cors import CORS
from functools import wraps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import Database
from db_loader import load_user_sow_data
from main import run_pipeline_from_sow_list
from sow_types import SOW_TYPES
from currencies import CURRENCIES, DEFAULT_CURRENCY, DEFAULT_EXCHANGE_RATES
from emailer import send_verification_code, send_feedback_notification
from config import SECRET_KEY, CORS_ORIGINS, PORT, DEV_EMAIL_MODE

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 30

CORS(app, supports_credentials=True, resources={r"/api/*": {
    "origins": CORS_ORIGINS,
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


EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


@app.route('/api/login', methods=['POST'])
def api_login():
    d = request.get_json()
    u = (d.get('username') or d.get('identifier') or '').strip()
    p = d.get('password') or ''
    if not u or not p:
        return jsonify({'error': 'Username/email and password required'}), 400
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
    e = (d.get('email') or '').strip().lower()
    p = d.get('password') or ''
    code = (d.get('verification_code') or '').strip()

    if not u or not e or not p:
        return jsonify({'error': 'All fields (username, email, password) required'}), 400
    if not EMAIL_REGEX.match(e):
        return jsonify({'error': 'Invalid email address'}), 400
    if len(p) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    if not re.match(r'^[a-zA-Z0-9_]{3,30}$', u):
        return jsonify({'error': 'Username must be 3-30 chars, letters/numbers/underscore only'}), 400

    if db.is_username_taken(u):
        return jsonify({'error': 'Username already taken'}), 400
    if db.is_email_taken(e):
        return jsonify({'error': 'Email already registered'}), 400

    email_verified = False
    if code:
        email_verified = db.verify_code(e, code, purpose='register')
        if not email_verified:
            return jsonify({'error': 'Invalid or expired verification code'}), 400
    else:
        dev_mode = DEV_EMAIL_MODE
        if dev_mode:
            email_verified = True
        else:
            return jsonify({'error': 'Email verification code required'}), 400

    try:
        uid = db.create_user(u, e, p, email_verified=email_verified)
        user = db.get_user(uid)
        session["user_id"] = uid
        session.permanent = True
        return jsonify({'id': uid, 'username': u, 'email': e, 'email_verified': email_verified})
    except Exception as ex:
        return jsonify({'error': str(ex)}), 400


@app.route('/api/auth/send-code', methods=['POST'])
def api_send_code():
    d = request.get_json()
    e = (d.get('email') or '').strip().lower()
    purpose = (d.get('purpose') or 'register').strip()
    if purpose not in ('register', 'reset'):
        return jsonify({'error': 'Invalid purpose'}), 400
    if not e or not EMAIL_REGEX.match(e):
        return jsonify({'error': 'Valid email required'}), 400

    if purpose == 'register' and db.is_email_taken(e):
        return jsonify({'error': 'Email already registered'}), 400
    if purpose == 'reset' and not db.is_email_taken(e):
        return jsonify({'error': 'No account found with that email'}), 404

    if db.has_pending_code(e, purpose):
        pass

    code = db.create_verification_code(e, purpose=purpose)

    dev_mode = DEV_EMAIL_MODE
    if dev_mode:
        return jsonify({'ok': True, 'dev_code': code, 'message': 'DEV MODE - code: ' + code})

    sent = send_verification_code(e, code, purpose=purpose)
    if not sent:
        return jsonify({'error': 'Failed to send email. Please try again later.'}), 500
    return jsonify({'ok': True, 'message': 'Verification code sent to ' + e})


@app.route('/api/auth/verify-code', methods=['POST'])
def api_verify_code():
    d = request.get_json()
    e = (d.get('email') or '').strip().lower()
    code = (d.get('code') or '').strip()
    purpose = (d.get('purpose') or 'register').strip()
    if not e or not code:
        return jsonify({'error': 'Email and code required'}), 400
    ok = db.verify_code(e, code, purpose=purpose)
    if ok:
        return jsonify({'ok': True})
    return jsonify({'error': 'Invalid or expired code'}), 400


@app.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    d = request.get_json()
    e = (d.get('email') or '').strip().lower()
    code = (d.get('code') or '').strip()
    new_pw = d.get('new_password') or ''
    if not e or not code or not new_pw:
        return jsonify({'error': 'Email, code, and new password required'}), 400
    if len(new_pw) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    if not EMAIL_REGEX.match(e):
        return jsonify({'error': 'Invalid email'}), 400
    if not db.is_email_taken(e):
        return jsonify({'error': 'No account found with that email'}), 404

    ok = db.verify_code(e, code, purpose='reset')
    if not ok:
        return jsonify({'error': 'Invalid or expired code'}), 400

    db.update_user_password(e, new_pw)
    user = db.get_user_by_email(e)
    if user:
        session["user_id"] = user["id"]
        session.permanent = True
    return jsonify({'ok': True})


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
    currency = (d.get('currency') or DEFAULT_CURRENCY).strip().upper()
    if not name or not st:
        return jsonify({'error': 'Fields required'}), 400
    if st not in SOW_TYPES:
        return jsonify({'error': 'Invalid type: ' + st}), 400
    if currency not in CURRENCIES:
        currency = DEFAULT_CURRENCY
    try:
        aid = db.create_asset(uid, name, st, currency=currency)
        return jsonify({'id': aid, 'name': name, 'sow_type': st, 'currency': currency})
    except Exception as ex:
        return jsonify({'error': str(ex)}), 400


@app.route('/api/assets/<int:aid>', methods=['PUT'])
@login_required
def api_update_asset(aid):
    uid = session["user_id"]
    d = request.get_json()
    n = (d.get('name') or '').strip() or None
    st = (d.get('sow_type') or '').strip() or None
    cur = (d.get('currency') or '').strip().upper() or None
    if cur and cur not in CURRENCIES:
        cur = None
    try:
        db.update_asset(uid, aid, name=n, sow_type=st, currency=cur)
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

    cur_settings = db.get_user_currency_settings(uid)
    display_currency = d.get('display_currency') or cur_settings['display_currency']
    currency_rates = cur_settings['currency_rates']

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
        display_currency=display_currency,
        currency_rates=currency_rates,
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
    if not f.filename or not f.filename.lower().endswith('.xlsx'):
        return jsonify({'error': 'Please upload an .xlsx file'}), 400
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        f.save(tmp.name)
        try:
             result = db.import_excel_to_user(uid, tmp.name)
             return jsonify(result)
        except Exception as ex:
            return jsonify({'error': str(ex)}), 400
        finally:
            os.unlink(tmp.name)

@app.route('/api/export', methods=['GET'])
@login_required
def api_export():
    from excel_parser import write_excel
    uid = session["user_id"]
    sow_list = load_user_sow_data(db, uid)
    if not sow_list:
        return jsonify({'error': 'No assets to export'}), 400
    tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
    tmp.close()
    try:
        write_excel(tmp.name, sow_list)
        user = db.get_user(uid)
        name_tag = (user.get("username", "assets") if user else "assets")
        download_name = f"{name_tag}_assets_{datetime.now().strftime('%Y%m%d')}.xlsx"
        return send_file(
            tmp.name,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
    except Exception as ex:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        return jsonify({'error': f'Export failed: {str(ex)}'}), 500


@app.route('/api/import-sample', methods=['POST'])
@login_required
def api_import_sample():
    uid = session["user_id"]
    sp = os.path.join(APP_DIR, 'sample_data', 'sample_assets.xlsx')
    if not os.path.exists(sp):
        return jsonify({'error': 'Sample not found'}), 404
    try:
         result = db.import_excel_to_user(uid, sp)
         return jsonify(result)
    except Exception as ex:
        return jsonify({'error': str(ex)}), 400


@app.route('/api/sow-types', methods=['GET'])
def api_sow_types():
    return jsonify([{
        'key': k, 'label': v.label, 'is_asset': v.is_asset,
        'default_annual_growth': v.default_annual_growth,
        'default_monthly_contribution': v.default_monthly_contribution
    } for k, v in SOW_TYPES.items()])


@app.route('/api/currencies', methods=['GET'])
def api_currencies():
    return jsonify([{
        'code': k, 'symbol': v.symbol, 'label': v.label
    } for k, v in CURRENCIES.items()])


@app.route('/api/currency-settings', methods=['GET'])
@login_required
def api_get_currency_settings():
    uid = session["user_id"]
    settings = db.get_user_currency_settings(uid)
    return jsonify({
        "display_currency": settings["display_currency"],
        "currency_rates": settings["currency_rates"],
        "default_rates": dict(DEFAULT_EXCHANGE_RATES),
        "available_currencies": [
            {"code": k, "symbol": v.symbol, "label": v.label}
            for k, v in CURRENCIES.items()
        ],
    })


@app.route('/api/currency-settings', methods=['PUT'])
@login_required
def api_save_currency_settings():
    d = request.get_json()
    uid = session["user_id"]
    display_currency = (d.get('display_currency') or '').strip().upper() or None
    if display_currency and display_currency not in CURRENCIES:
        display_currency = None
    rates_raw = d.get('currency_rates')
    cleaned_rates = {}
    if isinstance(rates_raw, dict):
        for code, val in rates_raw.items():
            code_upper = str(code).strip().upper()
            if code_upper in CURRENCIES:
                try:
                    fv = float(val)
                    if fv > 0:
                        cleaned_rates[code_upper] = fv
                except (TypeError, ValueError):
                    pass
    try:
        db.set_user_currency_settings(
            uid,
            display_currency=display_currency,
            currency_rates=cleaned_rates if cleaned_rates else None,
        )
        return jsonify({"ok": True})
    except Exception as ex:
        return jsonify({"error": str(ex)}), 400


@app.route('/api/template', methods=['GET'])
def api_template():
    path = os.path.join(APP_DIR, 'sample_data', 'template_assets.xlsx')
    if not os.path.exists(path):
        return jsonify({'error': 'Template not found'}), 404
    return send_file(path, as_attachment=True, download_name='asset_import_template.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/api/feedback', methods=['POST'])
def api_feedback():
    d = request.get_json()
    uid = session.get("user_id")
    email = (d.get('email') or '').strip().lower()
    name = (d.get('name') or '').strip()
    message = (d.get('message') or '').strip()
    rating = d.get('rating')

    if not message or not email:
        return jsonify({'error': 'Email and message required'}), 400
    if not EMAIL_REGEX.match(email):
        return jsonify({'error': 'Invalid email'}), 400
    if len(message) < 5:
        return jsonify({'error': 'Message is too short'}), 400
    if rating is not None:
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                rating = None
        except (TypeError, ValueError):
            rating = None

    saved_name = name
    if not saved_name and uid:
        user = db.get_user(uid)
        if user:
            saved_name = user.get('username', '')

    fid = db.create_feedback(uid, email, message, rating=rating, name=saved_name)

    try:
        send_feedback_notification(saved_name or 'Anonymous', email, message, rating=rating)
    except Exception:
        pass

    return jsonify({'ok': True, 'id': fid})


if __name__ == '__main__':
    print(f'LocusAdvisory Web Server on http://127.0.0.1:{PORT}')
    app.run(host='0.0.0.0', port=PORT, debug=False)