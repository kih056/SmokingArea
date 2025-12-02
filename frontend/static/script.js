const BASE_URL = "http://localhost:5050"; // API 주소 수정

// 전역 변수
var map = null;
var currentMarker = null;
var currentCoords = null;
var nearbyCircle = null;
var nearbyMarkers = [];
var isNearbyMode = false;

// [신규] 위시리스트 마커 관리용
var savedMarkers = [];
var savedInfoWindows = {};

window.onload = function() {
    initMap();
    loadWishlist(); // 초기 로드
};

function initMap() {
    var mapOptions = {
        center: new naver.maps.LatLng(37.3595704, 127.105399),
        zoom: 15
    };
    map = new naver.maps.Map('map', mapOptions);
    
    // 1. 다각형 데이터 로드 (기존 로직 유지)
    loadPolygons();

    // 2. 지도 클릭 이벤트
    naver.maps.Event.addListener(map, 'click', function(e) {
        searchCoordinateToAddress(e.coord);
    });
}

// [신규] 사이드바 토글 기능
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const btnIcon = document.querySelector('#sidebar-toggle-btn i');
    sidebar.classList.toggle('collapsed');
    
    if (sidebar.classList.contains('collapsed')) {
        btnIcon.className = 'fa-solid fa-chevron-right';
    } else {
        btnIcon.className = 'fa-solid fa-chevron-left';
    }
}

// ---------------------------------------------------
// [수정] 위시리스트 로직 (참고 JS 파일 이식 + API 연동)
// ---------------------------------------------------

async function loadWishlist() {
    const container = document.getElementById('wishlist-container');
    const groupList = document.getElementById('group-list');
    
    try {
        const res = await fetch('/api/wishlist');
        const data = await res.json();
        
        // 초기화
        savedMarkers.forEach(m => m.setMap(null));
        savedMarkers = []; savedInfoWindows = {};
        container.innerHTML = '';
        groupList.innerHTML = '';

        const groupedData = {};
        const groupSet = new Set();

        // 데이터 분류 및 마커 생성
        for (const [addr, info] of Object.entries(data)) {
            addSavedMarker(addr, info); // 지도에 저장된 마커 표시

            const gName = info.group_name || '기본';
            if (!groupedData[gName]) groupedData[gName] = [];
            groupedData[gName].push({ address: addr, ...info });
            groupSet.add(gName);
        }

        // 그룹명 자동완성 옵션 추가
        groupSet.forEach(g => {
            const opt = document.createElement('option');
            opt.value = g;
            groupList.appendChild(opt);
        });

        // UI 렌더링
        if (Object.keys(groupedData).length === 0) {
            container.innerHTML = '<div style="text-align:center; color:#999; padding:10px; font-size:12px;">저장된 장소가 없습니다.</div>';
            return;
        }

        Object.keys(groupedData).sort().forEach(groupName => {
            const items = groupedData[groupName];
            
            const details = document.createElement('details');
            details.className = "group-item";
            details.open = true;

            const summary = document.createElement('summary');
            summary.innerHTML = `
                <span><i class="fa-solid fa-folder" style="color:#ffc107; margin-right:5px;"></i> ${groupName}</span>
                <span style="font-size:11px; background:#eee; padding:2px 6px; rounded:4px; border-radius:10px;">${items.length}</span>
            `;

            const listDiv = document.createElement('div');
            items.forEach(item => {
                listDiv.appendChild(createListItem(item));
            });

            details.appendChild(summary);
            details.appendChild(listDiv);
            container.appendChild(details);
        });

    } catch (e) { console.error("위시리스트 로드 실패:", e); }
}

function createListItem(item) {
    const el = document.createElement('div');
    el.className = "wish-item";
    el.innerHTML = `
        <div class="wish-item-header" onclick="moveToLocation('${item.address}')">
            <div class="color-dot" style="background-color: ${item.color};"></div>
            <div style="flex-grow:1;">
                <div class="wish-address">${item.address}</div>
                ${item.note ? `<div class="wish-note"><i class="fa-regular fa-note-sticky"></i> ${item.note}</div>` : ''}
            </div>
        </div>
        <div class="item-actions">
            <button class="action-btn del" onclick="deleteItem('${item.address}')" title="삭제">
                <i class="fa-solid fa-trash"></i>
            </button>
        </div>
    `;
    return el;
}

// [신규] 저장 (API 호출)
async function saveCurrentLocation() {
    if (!currentCoords) return alert("저장할 위치를 선택해주세요.");
    
    const address = document.getElementById('footer-address').innerText; // 오버레이의 주소 사용
    const group = document.getElementById('wishlist-group').value || "기본";
    const color = document.getElementById('wishlist-color').value;
    const note = document.getElementById('wishlist-note').value;

    try {
        await fetch('/api/wishlist', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ address, group_name: group, color, note })
        });
        
        // 입력 폼 초기화
        document.getElementById('wishlist-note').value = '';
        alert("저장되었습니다.");
        loadWishlist(); // 리스트 갱신
    } catch (e) { alert("저장 실패: " + e); }
}

// [신규] 삭제
async function deleteItem(address) {
    if (!confirm("정말 삭제하시겠습니까?")) return;
    try {
        await fetch('/api/wishlist', {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ address })
        });
        loadWishlist();
    } catch(e) { alert("삭제 오류"); }
}

// [신규] 저장된 마커 지도 표시
function addSavedMarker(address, info) {
    naver.maps.Service.geocode({ query: address }, function(status, response) {
        if (status === naver.maps.Service.Status.OK && response.v2.addresses.length > 0) {
            const item = response.v2.addresses[0];
            const latlng = new naver.maps.LatLng(item.y, item.x);

            const marker = new naver.maps.Marker({
                position: latlng,
                map: map,
                icon: {
                    content: `<div style="background:${info.color}; width:16px; height:16px; border-radius:50%; border:2px solid white; box-shadow:0 1px 3px rgba(0,0,0,0.5);"></div>`
                }
            });

            const infoWindow = new naver.maps.InfoWindow({
                content: `
                    <div style="padding:10px; min-width:150px; text-align:center;">
                        <div style="font-size:11px; color:#888;">${info.group_name}</div>
                        <div style="font-weight:bold; font-size:13px; margin-bottom:5px;">${address}</div>
                        <button onclick="openRoadView(${item.y}, ${item.x}, '${address}')" 
                                style="background:#0078ff; color:white; border:none; padding:5px 10px; border-radius:4px; cursor:pointer; font-size:11px; margin-top:5px;">
                            로드뷰 보기
                        </button>
                    </div>`,
                backgroundColor: "white",
                borderWidth: 1,
                anchorSize: new naver.maps.Size(10, 10)
            });

            naver.maps.Event.addListener(marker, 'click', () => {
                infoWindow.open(map, marker);
            });

            savedMarkers.push(marker);
            savedInfoWindows[address] = infoWindow;
        }
    });
}

function moveToLocation(address) {
    // 저장된 마커 찾기 (좌표 변환이 비동기라 약간의 딜레이 있을 수 있음, 여기선 단순화)
    // 실제로는 savedMarkers 배열보다는 주소-좌표 매핑이 더 정확하지만, 여기선 geocode 다시 호출
    naver.maps.Service.geocode({ query: address }, function(status, response) {
        if (status === naver.maps.Service.Status.OK && response.v2.addresses.length > 0) {
            const item = response.v2.addresses[0];
            const pt = new naver.maps.LatLng(item.y, item.x);
            map.panTo(pt);
            map.setZoom(17);
        }
    });
}

// ---------------------------------------------------
// 기존 로직 유지 (다각형, 검색, 유효성 검사 등)
// ---------------------------------------------------

async function loadPolygons() {
    try {
        const response = await fetch(`http://localhost:8000/getcoordinates/getPolygon`);
        if (!response.ok) return;
        const data = await response.json();
        if (data.polygons && Array.isArray(data.polygons)) {
            data.polygons.forEach(rawData => {
                let pathData = rawData;
                if (typeof rawData === 'string') {
                    try { pathData = JSON.parse(rawData); } catch (e) { return; }
                }
                if (!Array.isArray(pathData)) return;
                var paths = pathData.map(coord => {
                    if (Array.isArray(coord) && coord.length === 2) {
                        return new naver.maps.LatLng(coord[1], coord[0]);
                    } return null;
                }).filter(p => p !== null);
                if (paths.length >= 3) {
                    new naver.maps.Polygon({
                        map: map, paths: paths,
                        fillColor: '#ff0000', fillOpacity: 0.3,
                        strokeColor: '#ff0000', strokeOpacity: 0.8,
                        strokeWeight: 2, clickable: false
                    });
                }
            });
        }
    } catch (error) { console.error("다각형 로드 중 오류:", error); }
}

function searchCoordinateToAddress(latlng) {
    naver.maps.Service.reverseGeocode({
        coords: latlng,
        orders: [naver.maps.Service.OrderType.ADDR, naver.maps.Service.OrderType.ROAD_ADDR].join(',')
    }, function(status, response) {
        if (status === naver.maps.Service.Status.OK) {
            const items = response.v2.results;
            let address = "주소 없음";
            if (items.length > 0) {
                address = items[0].region.area1.name + " " + items[0].region.area2.name + " " + items[0].region.area3.name;
                if (items[0].land) address += " " + items[0].land.number1 + (items[0].land.number2 ? "-" + items[0].land.number2 : "");
            }
            handleLocationSelection(latlng, address);
        }
    });
}

function searchAddress() {
    var query = document.getElementById('search-address').value;
    if (!query) return alert("주소를 입력해주세요.");

    naver.maps.Service.geocode({ query: query }, function(status, response) {
        if (status !== naver.maps.Service.Status.OK || response.v2.addresses.length === 0) {
            return alert('주소를 찾을 수 없습니다.');
        }
        var item = response.v2.addresses[0];
        var point = new naver.maps.LatLng(item.y, item.x);
        map.setCenter(point);
        map.setZoom(17);
        handleLocationSelection(point, item.roadAddress || item.jibunAddress);
    });
}

async function handleLocationSelection(latlng, address) {
    currentCoords = latlng;
    document.getElementById('add-wish-button').disabled = false;

    if (currentMarker) currentMarker.setMap(null);
    currentMarker = new naver.maps.Marker({
        position: latlng, map: map,
        animation: naver.maps.Animation.DROP
    });

    checkImpossibleZone(latlng, address);
    
    // 주변 상권 다시 그리기
    clearNearbyVisuals();
    if (isNearbyMode) fetchAndDrawNearbyBuildings(latlng.lat(), latlng.lng());
}

async function checkImpossibleZone(latlng, address) {
    try {
        const res = await fetch(`http://localhost:8000/checkImpossible?x=${latlng.lng()}&y=${latlng.lat()}`);
        const data = await res.json();
        const resultText = data.is_inside ? "불가능 구역 (TRUE)" : "가능 구역 (FALSE)";
        updateFooterOverlay(address, resultText, latlng);
    } catch (e) {
        updateFooterOverlay(address, "서버 연결 실패", latlng);
    }
}

function toggleNearbyMode() {
    const toggle = document.getElementById('nearby-toggle');
    isNearbyMode = toggle.checked;
    if (isNearbyMode) {
        if (currentCoords) fetchAndDrawNearbyBuildings(currentCoords.lat(), currentCoords.lng());
        else { alert("위치를 선택해주세요."); toggle.checked = false; isNearbyMode = false; }
    } else {
        clearNearbyVisuals();
    }
}

function clearNearbyVisuals() {
    if (nearbyCircle) { nearbyCircle.setMap(null); nearbyCircle = null; }
    nearbyMarkers.forEach(marker => marker.setMap(null));
    nearbyMarkers = [];
    document.getElementById('nearby-loading').style.display = 'none';
}

async function fetchAndDrawNearbyBuildings(lat, lng) {
    clearNearbyVisuals();
    const loadingDiv = document.getElementById('nearby-loading');
    loadingDiv.style.display = "block";
    loadingDiv.innerText = "로딩중...";

    try {
        const response = await fetch(`http://localhost:8000/building/nearby-buildings?latitude=${lat}&longitude=${lng}`);
        if (!response.ok) throw new Error();
        const data = await response.json();
        loadingDiv.style.display = "none";

        nearbyCircle = new naver.maps.Circle({
            map: map, center: new naver.maps.LatLng(lat, lng), radius: 50,
            fillColor: '#00ff00', fillOpacity: 0.15, strokeColor: '#00ff00', strokeOpacity: 0.8
        });

        if (data.buildings) {
            data.buildings.forEach(building => {
                const bLat = building.location.lat;
                const bLon = building.location.lon;
                let labelHtml = building.stores ? building.stores.map(s => `<div>${s.name}</div>`).join("") : "정보 없음";

                const marker = new naver.maps.Marker({
                    position: new naver.maps.LatLng(bLat, bLon),
                    map: map,
                    icon: {
                        content: `<div style="background:white; border:1px solid green; padding:3px; font-size:10px;">${labelHtml}</div>`
                    }
                });
                nearbyMarkers.push(marker);
            });
        }
    } catch (error) {
        loadingDiv.style.display = "none";
        console.error(error);
    }
}

function updateFooterOverlay(address, statusText, latlng) {
    const footerDiv = document.getElementById('location-footer');
    document.getElementById('footer-address').innerText = address;
    document.getElementById('footer-status').innerText = `유효성: ${statusText}`;
    
    // 로드뷰 버튼 함수 바인딩
    window.openRoadViewFromFooter = function() {
        openRoadView(latlng.lat(), latlng.lng(), address);
    };
    footerDiv.style.display = 'flex';
}

window.openRoadView = function(lat, lng, address) {
    // 2단계: 로드뷰 파노라마 페이지를 새 창으로 열기 (좌표 전달)
    const url = `/panorama?lat=${lat}&lng=${lng}&addr=${encodeURIComponent(address)}`;
    window.open(url, '_blank', 'width=1000,height=800'); 
};

function downloadCSV() {
    // 저장된 데이터가 있는지 확인 (UI 상의 리스트 개수로 판단하거나 서버로 요청)
    if (Object.keys(savedInfoWindows).length === 0) {
        alert("저장된 위시리스트가 없습니다.");
        return;
    }
    // 브라우저를 다운로드 URL로 이동시킴 (파일 다운로드 트리거)
    window.location.href = "/api/wishlist/export";
}