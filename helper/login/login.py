from flask import redirect, request, url_for, Blueprint, abort
from flask_login import login_user, LoginManager, logout_user
from oauthlib.oauth2 import WebApplicationClient
from helper import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_DISCOVERY_URL, ADMIN_DATA
from helper.login.objects import User
import requests
import json


app_login = Blueprint('app_login', __name__)
login_manager = LoginManager(app_login)
login_manager.login_view = 'login'

try:
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
except requests.exceptions.ConnectionError:
    print('WARNING: google authentication is not working. Either no internet connection or google is unreachable')
    google_provider_cfg = None

client = WebApplicationClient(GOOGLE_CLIENT_ID)


@login_manager.user_loader
def load_user(user_id):
    if user_id in ADMIN_DATA.keys():
        return User(user_id, ADMIN_DATA[user_id])
    return None


@app_login.route('/login', methods=['GET', 'POST'])
def login():
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],)
    return redirect(request_uri)


@app_login.route('/logout')
def logout():
    logout_user()
    return redirect('/')


@app_login.route("/login/callback")
def callback():
    code = request.args.get("code")
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_provider_cfg["token_endpoint"]
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
    )
    client.parse_request_body_response(json.dumps(token_response.json()))
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    if userinfo_response.json().get("email_verified"):
        user_email = userinfo_response.json()["email"]
    else:
        return abort(403)

    for key, value in ADMIN_DATA.items():
        if value == user_email:
            user = User(key, value)
            login_user(user)
            return redirect(url_for('search'))
    else:
        abort(403)


if __name__ == '__main__':
    app_login.run(host='0.0.0.0', port=5000, ssl_context='adhoc')
