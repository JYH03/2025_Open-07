/**
 * ==========================================
 * 1. 상수 및 설정 (Configuration)
 * ==========================================
 */
const CONFIG = {
    API_URL: 'http://localhost:3000/api/scrape',
    SITES: {
        musinsa: { name: 'MUSINSA', badge: 'badge-musinsa' },
        naver: { name: 'NAVER', badge: 'badge-naver' },
        default: { name: '쇼핑몰', badge: 'badge-etc' }
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
        URL_REQUIRED: 'URL을 입력해주세요!',
        SERVER_ERROR: '서버와 통신 중 오류가 발생했습니다.',
        SCRAPE_ERROR: '상품 정보를 가져오지 못했습니다.'
    }
};

/**
 * ==========================================
 * 2. 유틸리티 (Utilities)
 * ==========================================
 */
const Utils = {
    escapeHtml: (text) => {
        if (!text) return "";
        return text.replace(/[&<>"']/g, m => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
        })[m]);
    },

    getSiteInfo: (url) => {
        if (url.includes("musinsa")) return CONFIG.SITES.musinsa;
        if (url.includes("naver") || url.includes("smartstore")) return CONFIG.SITES.naver;
        return CONFIG.SITES.default;
    },

    openWindow: (url) => {
        if (url) window.open(url, '_blank');
    }
};

/**
 * ==========================================
 * 3. API 서비스 (API Service)
 * ==========================================
 */
const ApiService = {
    async fetchProduct(url) {
        try {
            const res = await fetch(`${CONFIG.API_URL}?url=${encodeURIComponent(url)}`);
            const data = await res.json();

            if (!res.ok || data.error) {
                throw new Error(data.detail || data.error || CONSTANTS.MESSAGES.SCRAPE_ERROR);
            }
            return data;
        } catch (err) {
            console.error('[API Error]', err);
            throw err;
        }
    }
};

/**
 * ==========================================
 * 4. UI 렌더러 (UI Renderer)
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
        return `<div class="price-container"><span class="final-price">${priceFormatted}</span></div>`;
    },

    sizes(sizes) {
        if (!sizes || sizes.length === 0) {
            return { html: `<div class="size-label">옵션 정보 없음</div>`, hasSoldOut: false };
        }

        let hasSoldOut = false;
        const chips = sizes.map(item => {
            if (item.isSoldOut) hasSoldOut = true;

            const displayName = item.color
                ? `<b>${Utils.escapeHtml(item.color)}</b> : ${Utils.escapeHtml(item.size)}`
                : Utils.escapeHtml(item.name);

            return `<span class="size-chip ${item.isSoldOut ? 'soldout' : ''}">${displayName}</span>`;
        }).join('');

        return { html: `<div class="size-chips">${chips}</div>`, hasSoldOut };
    },

    restockBtn(hasSoldOut) {
        if (!hasSoldOut) return '';
        return `
            <button class="restock-btn" data-action="restock">
                🔔 품절 옵션 재입고 알림 신청
            </button>`;
    },

    createCard(data) {
        const siteInfo = Utils.getSiteInfo(data.sourceUrl);
        const priceHtml = this.price(data);
        const sizeData = this.sizes(data.sizes);
        const restockBtnHtml = this.restockBtn(sizeData.hasSoldOut);

        // data-* 속성을 사용하여 이벤트 위임 시 데이터를 쉽게 찾도록 함
        return `
            <div class="product-card" data-url="${data.sourceUrl}">
                <div class="site-badge ${siteInfo.badge}">${siteInfo.name}</div>
                <button class="delete-btn" title="삭제" data-action="delete">✕</button>
                
                <div class="card-image" style="background-image: url('${data.image}')"></div>
                
                <div class="card-body">
                    <h3 class="card-title">
                        <a href="${data.sourceUrl}" target="_blank">${Utils.escapeHtml(data.title)}</a>
                    </h3>
                    
                    ${priceHtml}
                    
                    <div class="size-container">
                        <div class="size-label">옵션 / 사이즈</div>
                        ${sizeData.html}
                    </div>

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
 * 5. 메인 앱 로직 (Main Application)
 * ==========================================
 */
const App = {
    elements: {},

    init() {
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

        btn?.addEventListener('click', () => this.handleAddProduct());

        input?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.handleAddProduct();
        });

        // [이벤트 위임] 컨테이너 하나에만 이벤트를 걸어서 삭제/재입고 버튼 처리
        container?.addEventListener('click', (e) => {
            const target = e.target;
            const card = target.closest('.product-card');
            const action = target.dataset.action; // data-action 속성 확인

            if (!card) return;

            if (action === 'delete') {
                card.remove();
            } else if (action === 'restock') {
                Utils.openWindow(card.dataset.url);
            }
        });
    },

    checkUrlParams() {
        const urlParams = new URLSearchParams(window.location.search);
        const initialUrl = urlParams.get('url');
        if (initialUrl && this.elements.input) {
            this.elements.input.value = initialUrl;
            this.handleAddProduct();
        }
    },

    setLoading(isLoading) {
        const { input, btn, loading } = this.elements;
        if (input) input.disabled = isLoading;
        if (btn) btn.disabled = isLoading;
        if (loading) loading.style.display = isLoading ? 'block' : 'none';
    },

    async handleAddProduct() {
        const url = this.elements.input.value.trim();
        if (!url) return alert(CONSTANTS.MESSAGES.URL_REQUIRED);

        this.setLoading(true);

        try {
            const data = await ApiService.fetchProduct(url);

            // HTML 문자열을 생성하여 insertAdjacentHTML로 삽입 (성능상 createElement보다 유리할 수 있음)
            const cardHtml = Renderer.createCard(data);
            this.elements.container.insertAdjacentHTML('afterbegin', cardHtml);

            this.elements.input.value = '';
        } catch (err) {
            alert(`${CONSTANTS.MESSAGES.SCRAPE_ERROR}\n${err.message}`);
        } finally {
            this.setLoading(false);
            this.elements.input.focus();
        }
    }
};

// 앱 시작
document.addEventListener('DOMContentLoaded', () => App.init());