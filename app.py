from flask import Flask, request, jsonify
import re
import requests
import concurrent.futures
import random
import time

app = Flask(__name__)

@app.route("/")
def home():
    return "Your backend API is live and ready!"

def check_usernames(usernames, proxy_list):
    proxy_index = [-1]
    proxy_cooldown = set()
    available_names = []
    invalid_names = []
    regex = re.compile(r'[^a-zA-Z0-9_.]')
    client = requests.Session()

    def get_current_proxy():
        if proxy_index[0] == -1:
            return None
        if proxy_index[0] < len(proxy_list):
            proxy = proxy_list[proxy_index[0]]
            return {'http': proxy, 'https': proxy}
        else:
            proxy_index[0] = -1
            proxy_cooldown.clear()
            return None

    def switch_proxy():
        proxy_cooldown.add(proxy_index[0])
        available_indexes = [i for i in range(len(proxy_list)) if i not in proxy_cooldown]
        proxy_index[0] = random.choice(available_indexes) if available_indexes else -1

    def check_username(username):
        retry = True
        while retry:
            retry = False
            result = bool(regex.search(username))
            if not (result or (len(username) < 3) or (len(username) > 16)):
                proxies = get_current_proxy()
                try:
                    res = client.get('https://api.mojang.com/users/profiles/minecraft/' + username, proxies=proxies, timeout=10)
                except:
                    switch_proxy()
                    retry = True
                    continue

                if res.status_code == 200:
                    pass
                elif res.status_code in (204, 404):
                    available_names.append(username)
                elif res.status_code == 429:
                    switch_proxy()
                    retry = True
                elif res.status_code == 503:
                    retry = True
                    time.sleep(2)
                else:
                    try:
                        res.raise_for_status()
                    except:
                        pass
                    return
            else:
                invalid_names.append(username)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(check_username, usernames)

    return available_names, invalid_names

@app.route('/check', methods=['POST'])
def check():
    data = request.json
    proxies = data.get('proxies', '')
    usernames = data.get('usernames', '')

    proxy_list = [p.strip() for p in proxies.splitlines() if p.strip()]
    username_list = [u.strip() for u in usernames.splitlines() if u.strip()]

    available, invalid = check_usernames(username_list, proxy_list)

    return jsonify({
        'available': available,
        'invalid': invalid
    })

if __name__ == '__main__':
    app.run(debug=True)
