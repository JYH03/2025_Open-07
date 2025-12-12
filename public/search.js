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

    /* ---------- 옵션 공통 렌더러 (⭐ 핵심 추가) ---------- */
    options(items, label) {
        if (!items || items.length === 0) {
            return { html: '', hasSoldOut: false };
        }

        let hasSoldOut = false;

        const chips = items.map(item => {
            if (item.isSoldOut) hasSoldOut = true;

            return `
                <span class="size-chip ${item.isSoldOut ? 'soldout' : ''}">
                    ${Utils.escapeHtml(item.name)}
                </span>
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

        btn?.addEventListener("click", () => this.handleAddProduct());

        input?.addEventListener("keypress", (e) => {
            if (e.key === "Enter") this.handleAddProduct();
        });

        container?.addEventListener("click", (e) => {
            const target = e.target;
            const action = target.dataset.action;
            const card = target.closest(".product-card");

            if (!card) return;

            if (action === "delete") {
                card.remove();
            } else if (action === "restock") {
                Utils.openWindow(card.dataset.url);
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
