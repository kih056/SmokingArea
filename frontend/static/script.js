const BASE_URL = "http://localhost:5050"; // API 서버 (위시리스트용)
const DATA_URL = "http://localhost:8000"; // [수정] 데이터 서버 포트 8000번 고정

// 전역 변수
var map = null;
var currentMarker = null;
var currentCoords = null;
var nearbyCircle = null;
var nearbyMarkers = [];
var isNearbyMode = false;

// 위시리스트 마커 관리용
var savedMarkers = [];
var savedInfoWindows = {};

window.onload = function() {
    initMap();
    loadWishlist(); // 초기 로드
    
    // [추가] 겹치는 다각형 구멍 뚫림 방지용 CSS 주입 (Turf 없이 해결하는 핵심)
    const style = document.createElement('style');
    style.innerHTML = `
        #map svg path {
            fill-rule: nonzero !important;
        }
    `;
    document.head.appendChild(style);
};

function initMap() {
    var mapOptions = {
        
        center: new naver.maps.LatLng(37.3004799, 127.039381),
        zoom: 15
    };
    map = new naver.maps.Map('map', mapOptions);
    
    // 1. 다각형 데이터 로드
    loadPolygons();

    // 2. 지도 클릭 이벤트
    naver.maps.Event.addListener(map, 'click', function(e) {
        searchCoordinateToAddress(e.coord);
    });
}

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
// 위시리스트 로직
// ---------------------------------------------------

async function loadWishlist() {
    const container = document.getElementById('wishlist-container');
    const groupList = document.getElementById('group-list');
    
    try {
        const res = await fetch('/api/wishlist'); // 상대 경로 사용
        const data = await res.json();
        
        // 초기화
        savedMarkers.forEach(m => m.setMap(null));
        savedMarkers = []; savedInfoWindows = {};
        container.innerHTML = '';
        groupList.innerHTML = '';

        const groupedData = {};
        const groupSet = new Set();

        for (const [addr, info] of Object.entries(data)) {
            addSavedMarker(addr, info); 

            const gName = info.group_name || '기본';
            if (!groupedData[gName]) groupedData[gName] = [];
            groupedData[gName].push({ address: addr, ...info });
            groupSet.add(gName);
        }

        groupSet.forEach(g => {
            const opt = document.createElement('option');
            opt.value = g;
            groupList.appendChild(opt);
        });

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

async function saveCurrentLocation() {
    if (!currentCoords) return alert("저장할 위치를 선택해주세요.");
    
    const address = document.getElementById('footer-address').innerText;
    const group = document.getElementById('wishlist-group').value || "기본";
    const color = document.getElementById('wishlist-color').value;
    const note = document.getElementById('wishlist-note').value;

    try {
        await fetch('/api/wishlist', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ address, group_name: group, color, note })
        });
        
        document.getElementById('wishlist-note').value = '';
        alert("저장되었습니다.");
        loadWishlist(); 
    } catch (e) { alert("저장 실패: " + e); }
}

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
// [수정 1] 라이브러리 없이 네이버 공식 MultiPolygon 사용
// ---------------------------------------------------
async function loadPolygons() {
    try {
        // [수정] 통신 포트를 8000으로 명시하여 오류 해결
        const response = await fetch(`${DATA_URL}/getcoordinates/getPolygon`); 
        if (!response.ok) return;
        const data = await response.json();
        
        if (data.polygons && Array.isArray(data.polygons)) {
            let allPaths = []; // 모든 경로를 여기에 모음 (하나의 배열로 합치기)

            data.polygons.forEach(rawData => {
                let pathData = rawData;
                if (typeof rawData === 'string') {
                    try { pathData = JSON.parse(rawData); } catch (e) { return; }
                }
                if (!Array.isArray(pathData)) return;
                
                // 좌표 변환
                var path = pathData.map(coord => {
                    if (Array.isArray(coord) && coord.length === 2) {
                        return new naver.maps.LatLng(coord[1], coord[0]);
                    } return null;
                }).filter(p => p !== null);

                if (path.length >= 3) {
                    allPaths.push(path); // 개별 다각형 경로를 전체 배열에 추가
                }
            });

            // 네이버 지도 공식 기능: paths에 '배열의 배열'을 넣으면 멀티 폴리곤이 됨
            // 중요: window.onload에서 주입한 'fill-rule: nonzero' CSS 덕분에 구멍이 안 뚫림
            if (allPaths.length > 0) {
                new naver.maps.Polygon({
                    map: map,
                    paths: allPaths, 
                    fillColor: '#ff0000',
                    fillOpacity: 0.3,
                    strokeColor: '#ff0000',
                    strokeOpacity: 0.0,
                    strokeWeight: 0,
                    clickable: false
                });
            }
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

// ---------------------------------------------------
// [수정 2 & 3] 유효성 텍스트 및 말풍선 색상 처리
// ---------------------------------------------------
async function checkImpossibleZone(latlng, address) {
    try {
        // [수정] 데이터 서버 포트 8000 사용
        const res = await fetch(`${DATA_URL}/checkImpossible?x=${latlng.lng()}&y=${latlng.lat()}`);
        const data = await res.json();
        
        const isInside = data.is_inside; 
        const resultText = isInside ? "불가능 구역" : "가능 구역"; // True/False 텍스트 제거

        updateFooterOverlay(address, resultText, latlng, isInside); 
    } catch (e) {
        updateFooterOverlay(address, "서버 연결 실패", latlng, true);
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
        // [수정] 데이터 서버 포트 8000 사용
        const response = await fetch(`${DATA_URL}/building/nearby-buildings?latitude=${lat}&longitude=${lng}`);
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

// ---------------------------------------------------
// [수정 3] 하단 오버레이 스타일 (배경색 변경)
// ---------------------------------------------------
function updateFooterOverlay(address, statusText, latlng, isImpossible) {
    const footerDiv = document.getElementById('location-footer');
    const statusSpan = document.getElementById('footer-status');
    const addressSpan = document.getElementById('footer-address');
    
    addressSpan.innerText = address;
    statusSpan.innerText = `${statusText}`; // "유효성:" 글자 제거하고 깔끔하게 표시
    
    // 색상 변경 로직
    if (isImpossible) {
        // 불가능 -> 빨간색 배경
        footerDiv.style.backgroundColor = "#ff4d4f"; 
        footerDiv.style.color = "white";
        statusSpan.style.color = "#ffecece"; 
        statusSpan.style.fontWeight = "bold";
    } else {
        // 가능 -> 초록색 배경
        footerDiv.style.backgroundColor = "#2db400"; 
        footerDiv.style.color = "white";
        statusSpan.style.color = "#e8fcf2"; 
        statusSpan.style.fontWeight = "bold";
    }

    // 로드뷰 버튼 스타일도 배경에 맞춰 조정 (흰색 버튼)
    const btn = document.getElementById('footer-roadview-btn');
    btn.style.backgroundColor = "white";
    btn.style.color = isImpossible ? "#ff4d4f" : "#2db400";

    // 로드뷰 버튼 함수 바인딩
    window.openRoadViewFromFooter = function() {
        openRoadView(latlng.lat(), latlng.lng(), address);
    };
    footerDiv.style.display = 'flex';
}

window.openRoadView = function(lat, lng, address) {
    const url = `/panorama?lat=${lat}&lng=${lng}&addr=${encodeURIComponent(address)}`;
    window.open(url, '_blank', 'width=1000,height=800'); 
};

function downloadCSV() {
    if (Object.keys(savedInfoWindows).length === 0) {
        alert("저장된 위시리스트가 없습니다.");
        return;
    }
    window.location.href = "/api/wishlist/export";
}