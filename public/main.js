document.addEventListener('DOMContentLoaded', () => {
    // 1. DOM 요소 가져오기
    const elements = {
        input: document.getElementById('search-input'),
        form: document.getElementById('search-form'),
        suggestions: document.getElementById('tag-suggestions'),
        mode: document.getElementById('search-mode')
    };

    if (!elements.input || !elements.form || !elements.mode) return;

    // 2. 상수 및 데이터 설정
    const CATEGORIES = {
        gender: ["men", "women", "unisex"],
        color: ["white", "black", "gray", "navy", "beige"],
        top: ["tshirt", "hoodie", "shirt", "sweater"],
        bottom: ["pants", "jeans", "shorts", "skirt"],
        outer: ["coat", "jacket", "blazer", "cardigan"]
    };

    // 하나만 선택 가능한 카테고리
    const EXCLUSIVE_CATEGORIES = ["gender", "top", "bottom", "outer"];

    // 검색용 전체 태그 리스트 생성 (@붙임)
    const ALL_TAGS = Object.values(CATEGORIES)
        .flat()
        .map(tag => `@${tag}`);

    // =========================================
    // 3. 헬퍼 함수들
    // =========================================

    // 태그가 어떤 카테고리에 속하는지 찾기
    function findCategoryForTag(tag) {
        return Object.keys(CATEGORIES).find(category =>
            CATEGORIES[category].includes(tag)
        );
    }

    // 입력값에서 마지막 단어(현재 타이핑 중인 것) 추출
    function getLastWord(value) {
        return value.split(/\s+/).pop();
    }

    // 현재 입력창에 있는 유효한 태그들만 배열로 반환
    function getCurrentTags() {
        return elements.input.value
            .trim()
            .split(/\s+/)
            .map(word => word.replace("@", "").toLowerCase())
            .filter(word => {
                // 실제 존재하는 카테고리 단어인지 확인
                return Object.values(CATEGORIES).flat().includes(word);
            });
    }

    // =========================================
    // 4. 핵심 로직 (자동완성 필터링)
    // =========================================
    function filterTagsByKeyword(keyword) {
        const currentTags = getCurrentTags();

        // 현재 선택된 태그들이 차지하고 있는 카테고리들 (예: ['gender', 'top'])
        const occupiedCategories = currentTags.map(tag => findCategoryForTag(tag));

        return ALL_TAGS.filter(tag => {
            // A. 키워드 매칭 확인
            if (!tag.toLowerCase().startsWith(keyword)) return false;

            const tagWithoutAt = tag.replace("@", "").toLowerCase();
            const categoryName = findCategoryForTag(tagWithoutAt);

            if (!categoryName) return true;

            // B. 이미 입력된 태그는 제외
            if (currentTags.includes(tagWithoutAt)) return false;

            // C. 배타적 카테고리 체크 (성별, 상의 등은 하나만 선택 가능)
            if (EXCLUSIVE_CATEGORIES.includes(categoryName)) {
                if (occupiedCategories.includes(categoryName)) return false;
            }

            return true;
        });
    }

    // =========================================
    // 5. UI 조작 함수들 (제안창 표시/숨김)
    // =========================================
    function showSuggestions(tags) {
        elements.suggestions.innerHTML = "";

        if (tags.length === 0) {
            hideSuggestions();
            return;
        }

        tags.forEach(tag => {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = tag;
            button.className = "tag-suggestion";
            button.addEventListener("click", () => insertTag(tag));
            elements.suggestions.appendChild(button);
        });

        elements.suggestions.style.display = "block";
    }

    function hideSuggestions() {
        elements.suggestions.style.display = "none";
    }

    function insertTag(tag) {
        const words = elements.input.value.trim().split(/\s+/);
        words.pop(); // 방금 치던 불완전한 단어 제거
        words.push(tag); // 완성된 태그 추가
        elements.input.value = `${words.join(" ")} `;
        elements.input.focus();
        hideSuggestions();
    }

    // =========================================
    // 6. 이벤트 핸들러
    // =========================================

    // 입력창 타이핑 시
    function handleInputChange() {
        // 링크 모드면 자동완성 안 함
        if (elements.mode.value === 'url') {
            hideSuggestions();
            return;
        }

        const lastWord = getLastWord(elements.input.value);

        if (lastWord.startsWith("@")) {
            const matches = filterTagsByKeyword(lastWord.toLowerCase());
            showSuggestions(matches);
        } else {
            hideSuggestions();
        }
    }

    // 폼 제출 시 (검색 버튼 엔터)
    function handleFormSubmit(e) {
        e.preventDefault();
        const value = elements.input.value.trim();
        const mode = elements.mode.value;

        if (!value) return;

        const paramName = mode === 'url' ? 'url' : 'keyword';
        window.location.href = `search.html?${paramName}=${encodeURIComponent(value)}`;
    }

    // 모드 변경 시 (링크 <-> 키워드)
    function handleModeChange() {
        elements.input.value = "";
        hideSuggestions();

        const isUrlMode = elements.mode.value === 'url';
        elements.input.placeholder = isUrlMode
            ? "상품 페이지(링크)를 여기에 붙여넣으세요"
            : "원하는 스타일을 입력하세요 (예: @men @coat)";

        elements.input.focus();
    }

    // 외부 클릭 시 제안창 닫기
    document.addEventListener("click", (e) => {
        if (!elements.input.contains(e.target) && !elements.suggestions.contains(e.target)) {
            hideSuggestions();
        }
    });

    // 이벤트 리스너 등록
    elements.input.addEventListener("input", handleInputChange);
    elements.form.addEventListener("submit", handleFormSubmit);
    elements.mode.addEventListener("change", handleModeChange);
});