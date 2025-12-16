document.addEventListener('DOMContentLoaded', () => {
    // 1. DOM 요소 가져오기
    const elements = {
        input: document.getElementById('search-input'), // HTML의 id와 일치해야 함
        form: document.getElementById('search-form')
    };

    // 요소가 없으면 중단 (오류 방지)
    if (!elements.input || !elements.form) {
        console.error("[DEBUG] 필수 요소를 찾을 수 없습니다. HTML ID를 확인해주세요.");
        return;
    }

    // 2. 폼 제출 이벤트 핸들러
    elements.form.addEventListener('submit', (e) => {
        e.preventDefault(); // 브라우저의 기본 제출 동작 막기 (URL을 우리가 직접 통제하기 위함)

        const value = elements.input.value.trim();

        if (value) {
            // A. 입력값이 있을 때 -> 상품 추가 모드로 이동
            // 예: search.html?url=https://naver.com...
            console.log("[DEBUG] 상품 추가 모드로 이동:", value);
            window.location.href = `search.html?url=${encodeURIComponent(value)}`;
        } else {
            // B. 입력값이 없을 때 -> 그냥 장바구니(비교함) 페이지로 이동
            // 예: search.html
            console.log("[DEBUG] 저장된 목록 페이지로 이동");
            window.location.href = "search.html";
        }
    });
});