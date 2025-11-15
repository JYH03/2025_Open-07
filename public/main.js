// DOM 요소
const elements = {
    input: document.getElementById('search-input'),
    form: document.getElementById('search-form'),
    suggestions: document.getElementById('tag-suggestions')
};

// 카테고리 설정 추후 추가 예정
const CATEGORIES = {
    gender: ["men", "women", "unisex"],
    color: ["white", "black", "gray", "navy", "beige"],
    top: ["tshirt", "hoodie", "shirt", "sweater"],
    bottom: ["pants", "jeans", "shorts", "skirt"],
    outer: ["coat", "jacket", "blazer", "cardigan"]
};
//중복되면 안되는 태그
const EXCLUSIVE_CATEGORIES = ["top", "bottom", "outer"];

// 모든 태그를 @ 접두사와 함께 생성
const ALL_TAGS = Object.values(CATEGORIES)
    .flat()
    .map(tag => `@${tag}`);

/**
 * 태그 문자열을 파싱하여 카테고리별로 분류
 * @param {string} tagString - 공백으로 구분된 태그 문자열
 * @returns {Object} 카테고리별로 분류된 태그 객체
 */
function parseTags(tagString) {
    const tags = getUniqueTags(tagString);
    const selected = initializeSelectedTags();

    tags.forEach(tag => {
        const categoryName = findCategoryForTag(tag);
        if (categoryName) {
            addTagToCategory(selected, categoryName, tag);
        }
    });

    return selected;
}

/**
 * 문자열에서 중복 제거된 태그 배열 추출
 */
function getUniqueTags(tagString) {
    return [...new Set(
        tagString
            .trim()
            .split(/\s+/)
            .map(tag => tag.replace("@", "").toLowerCase())
    )];
}

/**
 * 선택된 태그 객체 초기화
 */
function initializeSelectedTags() {
    return {
        gender: [],
        color: [],
        top: null,
        bottom: null,
        outer: null
    };
}

/**
 * 태그가 속한 카테고리 찾기
 */
function findCategoryForTag(tag) {
    return Object.keys(CATEGORIES).find(category =>
        CATEGORIES[category].includes(tag)
    );
}

/**
 * 카테고리에 태그 추가 (배타적 카테고리는 중복 체크)
 */
function addTagToCategory(selected, categoryName, tag) {
    if (EXCLUSIVE_CATEGORIES.includes(categoryName)) {
        if (selected[categoryName]) {
            console.warn(`중복된 ${categoryName} 태그: '${selected[categoryName]}'와 '${tag}'`);
            return;
        }
        selected[categoryName] = tag;
    } else {
        selected[categoryName].push(tag);
    }
}

/**
 * 입력값에서 마지막 단어 추출
 */
function getLastWord(value) {
    return value.split(" ").pop();
}

/**
 * 키워드로 시작하는 태그 필터링
 */
function filterTagsByKeyword(keyword) {
    return ALL_TAGS.filter(tag => tag.toLowerCase().startsWith(keyword));
}

/**
 * 자동완성 제안 표시
 */
function showSuggestions(tags) {
    elements.suggestions.innerHTML = "";

    if (tags.length === 0) {
        hideSuggestions();
        return;
    }

    tags.forEach(tag => {
        const button = createSuggestionButton(tag);
        elements.suggestions.appendChild(button);
    });

    elements.suggestions.style.display = "block";
}

/**
 * 제안 버튼 생성
 */
function createSuggestionButton(tag) {
    const button = document.createElement("button");
    button.textContent = tag;
    button.className = "tag-suggestion";
    button.addEventListener("click", () => insertTag(tag));
    return button;
}

/**
 * 자동완성 제안 숨기기
 */
function hideSuggestions() {
    elements.suggestions.style.display = "none";
}

/**
 * 선택된 태그를 입력창에 삽입
 */
function insertTag(tag) {
    const words = elements.input.value.trim().split(" ");
    words.pop(); // 마지막 단어(입력 중인 @키워드) 제거
    words.push(tag); // 선택된 태그 추가
    elements.input.value = `${words.join(" ")} `;
    elements.input.focus();
    hideSuggestions();
}

/**
 * 검색 폼 제출 처리
 */
function handleFormSubmit(e) {
    e.preventDefault();
    const value = elements.input.value.trim();

    if (!value) return;

    window.location.href = `search.html?url=${encodeURIComponent(value)}`;
}

/**
 * 입력창 변경 처리
 */
function handleInputChange() {
    const lastWord = getLastWord(elements.input.value);

    if (lastWord.startsWith("@")) {
        const matches = filterTagsByKeyword(lastWord.toLowerCase());
        showSuggestions(matches);
    } else {
        hideSuggestions();
    }
}

// 이벤트 리스너 등록
elements.input.addEventListener("input", handleInputChange);
elements.form.addEventListener("submit", handleFormSubmit);

// 외부 클릭 시 자동완성 숨기기
document.addEventListener("click", (e) => {
    if (!elements.input.contains(e.target) && !elements.suggestions.contains(e.target)) {
        hideSuggestions();
    }
});