// Global Variables for Map and Services
var map = null;
var currentCoords = null;
var wishlistMarkers = []; // Stores Naver Map Markers
var geocoder = null; // Naver Maps Geocoder Service

// 💡 (Callback Function) 지도 초기화 및 이벤트 리스너 설정
function initMap() {
    var mapOptions = {
        center: new naver.maps.LatLng(37.5665, 126.9780), // 서울 시청 기본 좌표
        zoom: 10
    };
    map = new naver.maps.Map('map', mapOptions);
    
    // Geocoder 서비스 초기화 (주소 검색에 필요)
    geocoder = new naver.maps.Service.Geocoder();
    
    addMapListeners();
}

// 지도 이벤트 리스너 등록
function addMapListeners() {
    // 지도 클릭 시 좌표 표시 및 위시리스트 버튼 활성화
    naver.maps.Event.addListener(map, 'click', function(e) {
        currentCoords = e.coord;
        document.getElementById('coord-display').innerText = 
            '위도: ' + currentCoords.lat() + ' / 경도: ' + currentCoords.lng();
        document.getElementById('add-wish-button').disabled = false;
    });

    // 위시리스트 버튼에 이벤트 리스너 연결
    document.getElementById('add-wish-button').onclick = addWishlistItem;
}

// 1. 주소 검색 및 이동 기능
function searchAddress() {
    var address = document.getElementById('search-address').value;
    if (!address) return alert("주소를 입력해주세요.");

    geocoder.geocode({
        query: address
    }, function(status, response) {
        if (status !== naver.maps.Service.Status.OK) {
            return alert('주소 검색 중 오류가 발생했습니다.');
        }
        
        var result = response.v2.addresses[0];
        if (result) {
            var point = new naver.maps.Point(result.x, result.y);
            map.setCenter(point); // 지도의 중심 이동
            
            // 검색된 위치에 마커 표시
            new naver.maps.Marker({
                position: point,
                map: map
            });
            map.setZoom(15, false); // 줌 레벨 조정
        } else {
            alert('검색 결과가 없습니다.');
        }
    });
}

// 2. 좌표 초기화 기능
function clearCoords() {
    currentCoords = null;
    document.getElementById('coord-display').innerText = '위도: - / 경도: -';
    document.getElementById('add-wish-button').disabled = true;
}

// 3. 위시리스트 (마킹) 기능
function addWishlistItem() {
    if (!currentCoords) {
        return alert("지도에서 마킹할 위치를 먼저 클릭하세요.");
    }

    var name = document.getElementById('wishlist-name').value || "마킹 장소";
    
    // 1. 마커 추가
    var marker = new naver.maps.Marker({
        position: currentCoords,
        map: map,
        title: name
    });
    wishlistMarkers.push(marker);

    // 2. 리스트에 추가
    var list = document.getElementById('wishlist-list');
    var listItem = document.createElement('li');
    listItem.innerText = name + ' (' + currentCoords.lat().toFixed(4) + ', ' + currentCoords.lng().toFixed(4) + ')';
    
    // 클릭하면 해당 마커로 이동
    listItem.onclick = function() {
        map.setCenter(currentCoords);
        map.setZoom(15, true);
    };
    list.appendChild(listItem);
    
    // 3. UI 정리
    document.getElementById('wishlist-name').value = '';
    clearCoords();
}


// 인증 실패 확인 (선택 사항)
window.navermap_authFailure = function () {
    console.error("NAVER Maps API 인증에 실패했습니다.");
    alert("NAVER Maps API 인증 실패! (ncpKeyId 및 도메인 확인)");
}