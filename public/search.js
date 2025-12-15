/**
 * ==========================================
 * 1. Config
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
        LOADING: 'loading',
        CONTAINER: 'grid-container',
        DELETE_BTN: '.delete-btn',
        RESTOCK_BTN: '.restock-btn'
    },
    MESSAGES: {
        URL_REQUIRED: 'Please enter a product URL!',
        SERVER_ERROR: 'A server communication error occurred.',
        SCRAPE_ERROR: 'Failed to retrieve product information.'
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
        if (url.includes("naver") || url.includes("smartstore")) return CONFIG.SITES.naver;
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
        console.log("[DEBUG] Fetching product from server:", url);
        try {
            const res = await fetch(`${CONFIG.API_URL}?url=${encodeURIComponent(url)}`);
            const data = await res.json();

            if (!res.ok || data.error) {
                throw new Error(data.detail || data.error || CONSTANTS.MESSAGES.SCRAPE_ERROR);
            }

            console.log("[DEBUG] API fetch success");
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

    /* ---------- 가격 ---------- */
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

    /* ---------- 옵션 공통 렌더러 (버튼으로 변경됨) ---------- */
    options(items, label) {
        if (!items || items.length === 0) {
            return { html: '', hasSoldOut: false };
        }

        let hasSoldOut = false;

        const chips = items.map(item => {
            if (item.isSoldOut) hasSoldOut = true;

            // <span> -> <button> 변경
            // type="button"을 명시해야 form submit이 발생하지 않음
            return `
                <button 
                    type="button" 
                    class="size-chip ${item.isSoldOut ? 'soldout' : ''}"
                    data-action="select-option"
                    data-option-name="${Utils.escapeHtml(item.name)}"
                    data-option-status="${item.isSoldOut ? 'soldout' : 'available'}"
                >
                    ${Utils.escapeHtml(item.name)}
                </button>
            `;
        }).join('');

        return {
            html: `
                <div class="size-container">
                    <div class="size-label">${label}</div>
                    <div class="size-chips">
                        ${chips}
                    </div>
                </div>
            `,
            hasSoldOut
        };
    },

    /* ---------- 재입고 버튼 ---------- */
    restockBtn(hasSoldOut) {
        if (!hasSoldOut) return '';
        return `
            <button class="restock-btn" data-action="restock">
                🔔 Notify me when restocked
            </button>
        `;
    },

    /* ---------- 카드 생성 ---------- */
    createCard(data) {
        const siteInfo = Utils.getSiteInfo(data.sourceUrl);
        const priceHtml = this.price(data);

        // 옵션 렌더링
        const colorData = this.options(data.colors, "Options / Colors");
        const sizeData = this.options(data.sizes, "Options / Sizes");

        const restockBtnHtml = this.restockBtn(
            colorData.hasSoldOut || sizeData.hasSoldOut
        );

        return `
            <div class="product-card" data-url="${data.sourceUrl}">
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

    init() {
        console.log("[DEBUG] App initialized");
        this.cacheElements();
        this.bindEvents();
        this.checkUrlParams();
    },

    cacheElements() {
        this.elements = {
            input: document.getElementById(CONSTANTS.SELECTORS.INPUT),
            btn: document.getElementById(CONSTANTS.SELECTORS.BTN),
            loading: document.getElementById(CONSTANTS.SELECTORS.LOADING),
            container: document.getElementById(CONSTANTS.SELECTORS.CONTAINER)
        };
    },

    bindEvents() {
        const { btn, input, container } = this.elements;

        // 추가 버튼 클릭
        btn?.addEventListener("click", () => this.handleAddProduct());

        // 인풋창 엔터키
        input?.addEventListener("keypress", (e) => {
            if (e.key === "Enter") this.handleAddProduct();
        });

        // ⭐ 카드 내부 이벤트 위임 (삭제, 재입고, 옵션선택)
        container?.addEventListener("click", (e) => {
            const target = e.target;

            // 버튼 내부 아이콘 등을 클릭했을 때를 대비해 closest 사용
            // select-option 버튼이나 delete-btn 등을 찾음
            const button = target.closest("button");
            if (!button) return;

            const action = button.dataset.action;
            const card = button.closest(".product-card");

            if (!card) return;

            if (action === "delete") {
                // 카드 삭제
                card.remove();

            } else if (action === "restock") {
                // 재입고 알림 (새창 열기)
                Utils.openWindow(card.dataset.url);

            } else if (action === "select-option") {
                // ⭐ [수정됨] 옵션 선택 (토글 방식)

                // 1. 품절 체크
                if (button.dataset.optionStatus === 'soldout') {
                    return; // 품절된 상품은 클릭 무시
                }

                // 2. 같은 그룹 내 형제 버튼들 찾기 (.size-chips 안의 버튼들)
                const parent = button.parentElement;
                const siblings = parent.querySelectorAll('.size-chip');

                // 3. 현재 버튼이 이미 선택되어 있었는지 확인
                const wasSelected = button.classList.contains('selected');

                // 4. 모든 형제 버튼의 선택 상태 초기화 (라디오 버튼 처럼 하나만 선택되게)
                siblings.forEach(el => el.classList.remove('selected'));

                // 5. 이전에 선택되지 않았던 경우에만 선택 상태 추가 (토글 On)
                // (이미 선택된 걸 눌렀다면 4번 과정에서 꺼진 상태로 유지됨 -> 토글 Off)
                if (!wasSelected) {
                    button.classList.add('selected');
                    console.log(`[Selected] ${button.dataset.optionName}`);
                }
            }
        });
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
        input.disabled = isLoading;
        btn.disabled = isLoading;
        loading.style.display = isLoading ? "block" : "none";
    },

    async handleAddProduct() {
        const url = this.elements.input.value.trim();
        if (!url) return alert(CONSTANTS.MESSAGES.URL_REQUIRED);

        this.setLoading(true);

        try {
            const data = await ApiService.fetchProduct(url);
            const cardHtml = Renderer.createCard(data);
            this.elements.container.insertAdjacentHTML("afterbegin", cardHtml);
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