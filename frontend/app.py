import os
import requests
import csv # [추가]
import io  # [추가]
from flask import Flask, render_template, request, jsonify, Response

app = Flask(__name__)

# 환경 변수 로드
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')

# [신규] 위시리스트 데이터를 저장할 임시 메모리 저장소
# (서버를 재시작하면 초기화됩니다. 영구 저장을 원하면 DB 연동이 필요합니다.)
wishlist_db = {}

@app.route('/map')
def home():
    return render_template('index.html', client_id=NAVER_CLIENT_ID)

@app.route('/')
def intro():
    return render_template('intro.html')

# [신규] 2단계: 로드뷰 파노라마 페이지 라우트
@app.route('/panorama')
def panorama():
    return render_template('panorama.html', client_id=NAVER_CLIENT_ID)

# [신규] 2단계: 위시리스트 API (GET, POST, DELETE)
@app.route('/api/wishlist', methods=['GET', 'POST', 'DELETE'])
def api_wishlist():
    if request.method == 'GET':
        return jsonify(wishlist_db)
    
    data = request.json
    address = data.get('address')
    
    if request.method == 'POST':
        wishlist_db[address] = {
            'group_name': data.get('group_name', '기본'),
            'color': data.get('color', '#0078ff'),
            'note': data.get('note', ''),
            'address': address
        }
        return jsonify({"msg": "saved", "data": wishlist_db[address]})
        
    if request.method == 'DELETE':
        if address in wishlist_db:
            del wishlist_db[address]
        return jsonify({"msg": "deleted"})

@app.route('/geocode', methods=['GET'])
def geocode():
    query = request.args.get('query')
    if not query:
        return jsonify({'error': '검색할 주소를 입력하세요.'}), 400

    url = 'https://maps.apigw.ntruss.com/map-geocode/v2/geocode'
    headers = {
        'x-ncp-apigw-api-key-id': NAVER_CLIENT_ID,
        'x-ncp-apigw-api-key': NAVER_CLIENT_SECRET,
        'Accept': 'application/json'
    }
    params = {'query': query}
    try:
        response = requests.get(url, headers=headers, params=params)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# [신규] 위시리스트 CSV 다운로드 기능
@app.route('/api/wishlist/export')
def export_wishlist():
    if not wishlist_db:
        return "저장된 데이터가 없습니다.", 404

    # 1. CSV 생성을 위한 메모리 버퍼 생성
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 2. 헤더(컬럼명) 작성
    writer.writerow(['그룹', '주소', '메모', '색상'])
    
    # 3. 데이터 작성
    for info in wishlist_db.values():
        writer.writerow([
            info.get('group_name', '기본'),
            info.get('address', ''),
            info.get('note', ''),
            info.get('color', '')
        ])
        
    # 4. 한글 깨짐 방지를 위해 BOM(utf-8-sig) 인코딩 적용
    csv_data = output.getvalue().encode('utf-8-sig')
    
    # 5. 파일 다운로드 응답 반환
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=wishlist_data.csv"}
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)