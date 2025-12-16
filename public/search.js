/**
 * ==========================================
 * Smart Outfit Viewer - search.js (Final)
 * ==========================================
 */
console.log("[DEBUG] search.js loaded");

const CONFIG = {
    API_URL: 'http://localhost:3000/api/scrape',
    SITES: {
        musinsa: { name: 'MUSINSA', badge: 'badge-musinsa' },
        naver: { name: 'NAVER', badge: 'badge-naver' },
        default: { name: 'SHOP', badge: 'badge-etc' }
    }
};

const CONSTANTS = {
    SELECTORS: {
        INPUT: 'url-input',
        BTN: 'add-btn',
        CLEAR_BTN: 'clear-btn',      // 전체 삭제 버튼
        LOADING: 'loading',
        CONTAINER: 'grid-container',
        EMPTY_STATE: 'empty-state'   // 빈 화면 안내 문구
    },
    MESSAGES: {
        URL_REQUIRED: '상품 URL을 입력해주세요!',
        SCRAPE_ERROR: '상품 정보를 가져오는데 실패했습니다.',
        CONFIRM_CLEAR: '정말 모든 상품을 삭제하시겠습니까? (되돌릴 수 없습니다)'
    }
};


/**
 * ==========================================
 * 2. Utilities
 * ==========================================
 */
const Utils = {
    escapeHtml(text) {
        if (!text) return "";
        return text.replace(/[&<>"']/g, m => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        })[m]);
    },

    getSiteInfo(url) {
        if (url.includes("musinsa")) return CONFIG.SITES.musinsa;
        if (url.includes("naver") || url.includes("smartstore") || url.includes("brand.naver")) return CONFIG.SITES.naver;
        return CONFIG.SITES.default;
    },

    openWindow(url) {
        if (url) window.open(url, '_blank');
    }
};


/**
 * ==========================================
 * 3. API Service
 * ==========================================
 */
const ApiService = {
    async fetchProduct(url) {
        console.log("[DEBUG] Fetching product:", url);
        try {
            const res = await fetch(`${CONFIG.API_URL}?url=${encodeURIComponent(url)}`);
            const data = await res.json();

            if (!res.ok || data.error) {
                throw new Error(data.detail || data.error || CONSTANTS.MESSAGES.SCRAPE_ERROR);
            }
            return data;
        } catch (err) {
            console.error("[API ERROR]", err);
            throw err;
        }
    }
};


/**
 * ==========================================
 * 4. UI Renderer
 * ==========================================
 */
const Renderer = {

    price(data) {
        const { priceFormatted, couponPriceFormatted, couponPrice } = data;
        const hasCoupon = couponPrice && couponPrice > 0;

        if (hasCoupon) {
            return `
                <div class="price-container">
                    <span class="final-price">${couponPriceFormatted}</span>
                    <span class="original-price">${priceFormatted}</span>
                </div>`;
        }
        return `
            <div class="price-container">
                <span class="final-price">${priceFormatted}</span>
            </div>`;
    },

    options(items, label, isClickable = true, groupName = '') {
        if (!items || items.length === 0) {
            return { html: '', hasSoldOut: false };
        }

        let hasSoldOut = false;

        const chips = items.map(item => {
            if (item.isSoldOut) hasSoldOut = true;

            // 태그 및 속성 설정
            const tagName = 'button';
            const typeAttr = 'type="button"';

            let classAttr = `size-chip ${item.isSoldOut ? 'soldout' : ''}`;
            let disabledAttr = item.isSoldOut ? 'disabled' : '';

            // 모든 칩에 액션 부여 (클릭 이벤트 처리를 위해)
            let actionAttr = 'data-action="select-option"';

            return `
                <${tagName} 
                    ${typeAttr} 
                    class="${classAttr}"
                    ${actionAttr}
                    data-group="${groupName}"
                    data-option-name="${Utils.escapeHtml(item.name)}"
                    data-option-status="${item.isSoldOut ? 'soldout' : 'available'}"
                    ${disabledAttr}
                >
                    ${Utils.escapeHtml(item.name)}
                </${tagName}>
            `;
        }).join('');

        return {
            html: `
                <div class="size-container">
                    <div class="size-label">${label}</div>
                    <div class="size-chips">${chips}</div>
                </div>
            `,
            hasSoldOut
        };
    },

    restockBtn(hasSoldOut) {
        if (!hasSoldOut) return '';
        return `
            <button class="restock-btn" data-action="restock">
                🔔 Notify me when restocked
            </button>
        `;
    },

    createCard(data) {
        const siteInfo = Utils.getSiteInfo(data.sourceUrl);
        const priceHtml = this.price(data);

        // 조합 데이터 저장
        const combinations = data.combinations || [];
        const combinationsJson = JSON.stringify(combinations);

        // 옵션 HTML 생성
        const colorData = this.options(data.colors, "Options / Colors", true, "color");
        const sizeData = this.options(data.sizes, "Options / Sizes", false, "size");

        // 품절 여부 판단 (조합 데이터 우선 확인)
        let isAnySoldOut = false;
        if (combinations.length > 0) {
            isAnySoldOut = combinations.some(combo => combo.isSoldOut);
        } else {
            isAnySoldOut = colorData.hasSoldOut || sizeData.hasSoldOut;
        }

        const restockBtnHtml = this.restockBtn(isAnySoldOut);

        return `
            <div class="product-card" data-url="${data.sourceUrl}" data-combinations='${combinationsJson}'>
                <div class="site-badge ${siteInfo.badge}">
                    ${siteInfo.name}
                </div>

                <button class="delete-btn" data-action="delete">✕</button>

                <div class="card-image"
                     style="background-image: url('${data.image}')">
                </div>

                <div class="card-body">
                    <h3 class="card-title">
                        <a href="${data.sourceUrl}" target="_blank">
                            ${Utils.escapeHtml(data.title)}
                        </a>
                    </h3>

                    ${priceHtml}
                    ${colorData.html}
                    ${sizeData.html}

                    <div class="card-actions">
                        ${restockBtnHtml}
                    </div>
                </div>
            </div>
        `;
    }
};


/**
 * ==========================================
 * 5. Main Application Logic
 * ==========================================
 */
const App = {
    elements: {},
    savedProducts: [],

    init() {
        console.log("[DEBUG] App initialized");
        this.cacheElements();
        this.bindEvents();
        this.loadFromStorage();
        this.checkUrlParams();
    },

    cacheElements() {
        this.elements = {
            input: document.getElementById(CONSTANTS.SELECTORS.INPUT),
            btn: document.getElementById(CONSTANTS.SELECTORS.BTN),
            clearBtn: document.getElementById(CONSTANTS.SELECTORS.CLEAR_BTN), // [복구] 전체삭제 버튼
            loading: document.getElementById(CONSTANTS.SELECTORS.LOADING),
            container: document.getElementById(CONSTANTS.SELECTORS.CONTAINER),
            emptyState: document.getElementById(CONSTANTS.SELECTORS.EMPTY_STATE) // [복구] 빈 화면
        };
    },

    loadFromStorage() {
        const data = localStorage.getItem("my_wishlist");
        if (data) {
            this.savedProducts = JSON.parse(data);
            this.savedProducts.forEach(productData => {
                const cardHtml = Renderer.createCard(productData);
                this.elements.container.insertAdjacentHTML("beforeend", cardHtml);
            });
        }
        this.updateUIState(); // [복구] UI 상태 업데이트
    },

    saveToStorage() {
        localStorage.setItem("my_wishlist", JSON.stringify(this.savedProducts));
        this.updateUIState(); // [복구] 저장할 때마다 UI 업데이트
    },

    // [복구] 화면 상태 관리 함수 (버튼 숨김/표시)
    updateUIState() {
        const hasItems = this.savedProducts.length > 0;

        // 빈 화면 메시지 제어
        if (this.elements.emptyState) {
            this.elements.emptyState.style.display = hasItems ? 'none' : 'block';
        }

        // 전체 삭제 버튼 제어
        if (this.elements.clearBtn) {
            this.elements.clearBtn.style.display = hasItems ? 'inline-block' : 'none';
        }
    },

    bindEvents() {
        const { btn, input, container, clearBtn } = this.elements;

        // 추가 버튼
        if (btn) btn.addEventListener("click", () => this.handleAddProduct());

        // 인풋 엔터키
        if (input) {
            input.addEventListener("keypress", (e) => {
                if (e.key === "Enter") this.handleAddProduct();
            });
        }

        // [복구] 전체 삭제 버튼 이벤트
        if (clearBtn) {
            clearBtn.addEventListener("click", () => this.handleClearAll());
        }

        // 카드 내부 버튼 클릭 이벤트 (위임)
        if (container) {
            container.addEventListener("click", (e) => {
                const target = e.target;
                const button = target.closest("button");
                if (!button) return;

                const action = button.dataset.action;
                const card = button.closest(".product-card");

                // select-option은 card가 필수지만, 나머지는 아닐 수도 있음
                if (!card && action === "select-option") return;

                if (action === "delete") {
                    // 개별 삭제
                    const urlToDelete = card.dataset.url;
                    card.remove();
                    this.savedProducts = this.savedProducts.filter(p => p.sourceUrl !== urlToDelete);
                    this.saveToStorage();
                }
                else if (action === "restock") {
                    Utils.openWindow(card.dataset.url);
                }
                else if (action === "select-option") {
                    this.handleOptionSelect(button, card);
                }
            });
        }
    },

    // [복구] 옵션 선택 로직 분리
    handleOptionSelect(button, card) {
        const group = button.dataset.group;
        const parent = button.parentElement;

        // 선택 스타일 토글
        parent.querySelectorAll('.size-chip').forEach(el => el.classList.remove('selected'));
        button.classList.add('selected');

        // 컬러 선택 시 사이즈 재고 연동
        if (group === "color") {
            const selectedColor = button.dataset.optionName;
            const combinations = JSON.parse(card.dataset.combinations || "[]");
            const sizeButtons = card.querySelectorAll('[data-group="size"]');

            sizeButtons.forEach(sizeBtn => {
                const sizeName = sizeBtn.dataset.optionName;
                const combo = combinations.find(c => c.color === selectedColor && c.size === sizeName);

                if (combo) {
                    if (combo.isSoldOut) {
                        sizeBtn.disabled = true;
                        sizeBtn.classList.add('soldout');
                        sizeBtn.classList.remove('selected');
                    } else {
                        sizeBtn.disabled = false;
                        sizeBtn.classList.remove('soldout');
                    }
                }
            });
        }
    },

    // [복구] 전체 삭제 처리 함수
    handleClearAll() {
        if (confirm(CONSTANTS.MESSAGES.CONFIRM_CLEAR)) {
            // 1. 데이터 초기화
            this.savedProducts = [];
            // 2. 저장소 삭제
            localStorage.removeItem("my_wishlist");

            // 3. 화면에서 카드만 삭제 (empty-state는 남겨야 함)
            const cards = this.elements.container.querySelectorAll('.product-card');
            cards.forEach(c => c.remove());

            // 4. UI 상태 업데이트
            this.updateUIState();
        }
    },

    checkUrlParams() {
        const params = new URLSearchParams(window.location.search);
        const urlParam = params.get("url");
        if (urlParam && this.elements.input) {
            this.elements.input.value = urlParam;
            this.handleAddProduct();
        }
    },

    setLoading(isLoading) {
        const { input, btn, loading } = this.elements;
        if (input) input.disabled = isLoading;
        if (btn) btn.disabled = isLoading;
        if (loading) loading.style.display = isLoading ? "block" : "none";
    },

    async handleAddProduct() {
        const url = this.elements.input.value.trim();
        if (!url) return alert(CONSTANTS.MESSAGES.URL_REQUIRED);

        // 중복 체크
        if (this.savedProducts.some(p => p.sourceUrl === url)) {
            alert("이미 추가된 상품입니다!");
            this.elements.input.value = "";
            return;
        }

        this.setLoading(true);

        try {
            const data = await ApiService.fetchProduct(url);
            const cardHtml = Renderer.createCard(data);

            // 화면 맨 앞에 추가 (빈 화면 안내 뒤, 혹은 컨테이너 시작)
            // empty-state가 있다면 그 뒤에 추가되지 않도록 주의
            // insertAdjacentHTML 'afterbegin'은 자식 요소 중 가장 위에 붙음
            this.elements.container.insertAdjacentHTML("afterbegin", cardHtml);

            this.savedProducts.unshift(data);
            this.saveToStorage();

            this.elements.input.value = "";
        } catch (err) {
            alert(`${CONSTANTS.MESSAGES.SCRAPE_ERROR}\n${err.message}`);
        } finally {
            this.setLoading(false);
            this.elements.input.focus();
        }
    }
};

// Start App
document.addEventListener("DOMContentLoaded", () => App.init());