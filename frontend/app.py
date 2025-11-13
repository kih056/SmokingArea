import os
from flask import Flask, render_template

app = Flask(__name__)

# 환경 변수에서 클라이언트 ID를 읽어옵니다.
# 환경 변수가 설정되지 않은 경우를 대비하여 기본값(None)을 설정할 수 있습니다.
NAVER_CLIENT_ID = os.environ.get('NAVER_MAP_CLIENT_ID')

@app.route('/')
def home():
    # render_template 함수에 NAVER_CLIENT_ID 변수를 전달합니다.
    return render_template('index.html', client_id=NAVER_CLIENT_ID)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)