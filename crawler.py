import sys
import json
import re
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

# 윈도우 한글 깨짐 방지
sys.stdout.reconfigure(encoding='utf-8')

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager


# ==========================================
# 1. 설정 및 상수
# ==========================================
class Config:
    WINDOW_SIZE = "1920,1080"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    
    # [공통] 메타 태그
    META_TITLE = "meta[property='og:title']"
    META_IMAGE = "meta[property='og:image']"
    META_PRICE = "meta[property='product:sale_price:amount']"

    # [무신사] 가격 선택자 (강력함)
    MUSINSA_PRICE = [
        "#goods_price", ".product_article_price", "#list_price", 
        ".product_price", ".price", ".price_num", 
        "span.txt_price_member" 
    ]
    MUSINSA_OPTS_BTN = ["#option1 option", ".option1 button", ".opt-list li button"]
    MUSINSA_OPTS_LIST = [".option_list li", "#size_list li", ".goods_opt_list li"]

    # [네이버] 가격 선택자 (매우 다양함)
    NAVER_PRICE = [
        "._1LY7DqCnwR", "span._1LY7DqCnwR", # 스마트스토어 표준
        ".product_price .price", ".lowest-price", 
        "span._22kNQuPmbq", ".price_num", "strong.price",
        "span.cwq0ZTei2a", ".lowest .price" # 쇼핑윈도/브랜드스토어
    ]
    # 네이버 제목 선택자
    NAVER_TITLE = [
        "h3._22kNQuPmbq", "._22kNQuPmbq", "h3.cp-card__name", 
        ".ABroB09L7j", "h3"
    ]
    NAVER_OPT_BTN = ["a[aria-haspopup='listbox']", "div[role='combobox']", "a[role='button']._3-9gA-gL-k"]
    NAVER_OPT_LIST = ["ul[role='listbox'] li", "._2-aCU009jQ", "ul._3k4406ksnE li"]


# ==========================================
# 2. 데이터 모델
# ==========================================
@dataclass
class ProductData:
    site: str
    title: str = ""
    price: int = 0
    image: str = ""
    sizes: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "판매중"
    couponPrice: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.couponPrice is None:
            result.pop('couponPrice')
        return result


# ==========================================
# 3. 유틸리티 (제목 청소 & 가격 추출 강화)
# ==========================================
class Utils:
    @staticmethod
    def extract_number(text: Any) -> int:
        """문자열에서 숫자만 추출"""
        if not text: return 0
        clean_text = str(text).replace(',', '').replace('원', '')
        nums = re.findall(r'\d+', clean_text)
        return int(nums[0]) if nums else 0

    @staticmethod
    def ensure_https(url: str) -> str:
        if not url: return ""
        return f"https:{url}" if url.startswith("//") else url

    @staticmethod
    def clean_title(title: str) -> str:
        """제목에서 쓸데없는 문구 제거 (핵심 로직)"""
        if not title: return ""
        
        # 1. 추천 문구 제거
        garbage = ["이런 상품 어때요?", "함께 보면 좋은 상품", "추천 상품"]
        for g in garbage:
            title = title.replace(g, "")
            
        # 2. [스토어명] 제거
        title = re.sub(r'^\[.*?\]\s*', '', title)
        
        # 3. 줄바꿈 제거
        title = title.replace("\n", " ").strip()
        return title

    @staticmethod
    def safe_get(data: Dict, keys: List[str], default: Any = None) -> Any:
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key, {})
            else:
                return default
        return data if data else default


# ==========================================
# 4. 드라이버 팩토리
# ==========================================
class DriverFactory:
    @staticmethod
    def create_driver() -> WebDriver:
        options = Options()
        options.add_argument("--headless=new") 
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        options.add_argument(f"--window-size={Config.WINDOW_SIZE}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--log-level=3")
        options.add_argument(f"user-agent={Config.USER_AGENT}")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
        })
        return driver


# ==========================================
# 5. 스크래퍼 베이스
# ==========================================
class BaseScraper(ABC):
    def __init__(self, driver: WebDriver):
        self.driver = driver

    def scrape(self, url: str) -> ProductData:
        self.driver.get(url)
        time.sleep(2.0) # 페이지 로딩 대기

        # 1. JSON 시도
        data = self._scrape_from_json()
        if not data:
            data = ProductData(site=self.site_name)

        # 2. HTML 백업 (강력한 가격 찾기 포함)
        self._patch_missing_data(data)

        # 3. 최종 보정 (제목 청소 등)
        data.title = Utils.clean_title(data.title)

        # 4. 옵션 기본값
        if not data.sizes:
            data.sizes = [{"name": "Free / One Size", "isSoldOut": self._check_soldout()}]

        return data

    def _patch_missing_data(self, data: ProductData):
        """누락된 정보 채워넣기"""
        
        # 제목
        if not data.title or "이런 상품" in data.title:
            # HTML 태그 우선 시도
            html_title = self._find_title_from_html()
            if html_title: 
                data.title = html_title
            else:
                # 메타 태그 시도
                data.title = self._get_meta_content(Config.META_TITLE) or self.driver.title

        # 이미지
        if not data.image:
            data.image = self._get_meta_content(Config.META_IMAGE)
            
        # 가격 (0원이면 무조건 재검색)
        if data.price == 0:
            data.price = self._find_price_from_html()
            
        # 옵션
        if not data.sizes:
            self._find_options_from_html(data)

    def _find_price_from_html(self) -> int:
        """가격 찾기 (선택자 -> 메타태그 -> 텍스트 검색 순)"""
        
        # 1. 등록된 선택자들 순회
        for sel in self.html_price_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elements:
                    p = Utils.extract_number(el.text)
                    if p > 0: return p
            except: continue
        
        # 2. 메타 태그 백업
        try:
            p = Utils.extract_number(self._get_meta_content(Config.META_PRICE))
            if p > 0: return p
        except: pass

        # 3. [최후의 수단] 페이지 전체에서 "12,345원" 형식 찾기 (속도 느림, 최후에만 사용)
        try:
            # 상품 정보 영역으로 추정되는 곳의 텍스트만 가져옴
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            prices = re.findall(r'([\d,]+)원', body_text)
            for p_str in prices:
                p = Utils.extract_number(p_str)
                # 너무 작거나(100원 이하) 너무 큰 숫자는 제외 (오탐 방지)
                if 100 < p < 10000000: 
                    return p
        except: pass
        
        return 0

    # --- 추상 메서드 ---
    @property
    @abstractmethod
    def site_name(self) -> str: pass

    @property
    @abstractmethod
    def html_price_selectors(self) -> List[str]: pass
    
    @abstractmethod
    def _find_title_from_html(self) -> str: pass

    @abstractmethod
    def _scrape_from_json(self) -> Optional[ProductData]: pass

    @abstractmethod
    def _find_options_from_html(self, data: ProductData): pass

    @abstractmethod
    def _check_soldout(self) -> bool: pass

    # --- 헬퍼 ---
    def _get_meta_content(self, selector: str) -> str:
        try: return self.driver.find_element(By.CSS_SELECTOR, selector).get_attribute("content")
        except: return ""

    def _safe_find_text(self, selectors: List[str]) -> str:
        for sel in selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.text.strip(): return el.text.strip()
            except: continue
        return ""


# ==========================================
# 6. 무신사 스크래퍼
# ==========================================
class MusinsaScraper(BaseScraper):
    @property
    def site_name(self) -> str: return "musinsa"
    @property
    def html_price_selectors(self) -> List[str]: return Config.MUSINSA_PRICE

    def _scrape_from_json(self) -> Optional[ProductData]:
        try:
            script_el = self.driver.find_elements(By.ID, "__NEXT_DATA__")
            if not script_el: return None
            json_data = json.loads(script_el[0].get_attribute("innerHTML"))
            
            props = json_data.get("props", {})
            state = Utils.safe_get(props, ["pageProps", "state"]) or \
                    Utils.safe_get(props, ["pageProps", "initialState"]) or \
                    Utils.safe_get(props, ["pageProps"])
            product = state.get("product") or state.get("goods")
            if not product: return None

            data = ProductData(
                site=self.site_name,
                title=product.get("goodsNm") or product.get("goodsName", ""),
                price=int(product.get("goodsPrice") or product.get("salePrice", 0)),
                image=Utils.ensure_https(product.get("goodsImage") or product.get("goodsImg", "")),
                status="품절" if product.get("isSoldOut") else "판매중"
            )
            # 옵션
            opts = Utils.safe_get(product, ["goodsOption", "optionValues"]) or \
                   Utils.safe_get(product, ["option", "list"]) or []
            for o in opts:
                is_out = (o.get("stockQty", 1) == 0) or (o.get("soldOutYn", "N") == "Y")
                data.sizes.append({"name": o.get("name") or o.get("nm", ""), "isSoldOut": is_out})
            return data
        except: return None

    def _find_title_from_html(self) -> str:
        # 무신사는 메타태그가 정확한 편이라 메타태그 우선
        return "" 

    def _find_options_from_html(self, data: ProductData):
        if "쿠폰적용가" in self.driver.page_source:
            match = re.search(r'쿠폰적용가\s*([\d,]+)', self.driver.page_source)
            if match: data.couponPrice = Utils.extract_number(match.group(1))

        for sel in Config.MUSINSA_OPTS_BTN:
            btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
            for btn in btns:
                txt = btn.text.strip()
                if txt and "선택" not in txt:
                    data.sizes.append({"name": txt.replace("(품절)", "").strip(), "isSoldOut": "품절" in txt})
            if data.sizes: return

        for sel in Config.MUSINSA_OPTS_LIST:
            lis = self.driver.find_elements(By.CSS_SELECTOR, sel)
            for li in lis:
                txt = li.text.strip()
                if txt: data.sizes.append({"name": txt.replace("(품절)", "").strip(), "isSoldOut": "품절" in txt})
            if data.sizes: return

    def _check_soldout(self) -> bool:
        return "btn_soldout" in self.driver.page_source


# ==========================================
# 7. 네이버 스크래퍼
# ==========================================
class NaverScraper(BaseScraper):
    @property
    def site_name(self) -> str: return "naver"
    @property
    def html_price_selectors(self) -> List[str]: return Config.NAVER_PRICE

    def _scrape_from_json(self) -> Optional[ProductData]:
        try:
            html = self.driver.page_source
            match = re.search(r'window\.__PRELOADED_STATE__\s*=\s*({.*?});', html)
            if not match: return None
            state = json.loads(match.group(1))
            product = Utils.safe_get(state, ["product", "A"])
            if not product: return None

            data = ProductData(
                site=self.site_name,
                title=product.get("name", ""),
                price=product.get("discountedPrice") or product.get("salePrice") or product.get("price", 0),
            )
            if product.get("productImages"):
                data.image = product["productImages"][0].get("url", "")
            
            # 옵션
            options = Utils.safe_get(product, ["option", "simpleOptions"]) or \
                      Utils.safe_get(product, ["option", "optionCombos"]) or []
            for opt in options:
                name = opt.get("name")
                if not name:
                    name = f"{opt.get('optionName1','')} {opt.get('optionName2','')}"
                data.sizes.append({"name": name.strip(), "isSoldOut": opt.get("stockQuantity", 0) == 0})
            return data
        except: return None

    def _find_title_from_html(self) -> str:
        # 네이버 제목 선택자 순회
        return self._safe_find_text(Config.NAVER_TITLE)

    def _find_options_from_html(self, data: ProductData):
        try:
            # 콤보박스 클릭 시도
            for btn_sel in Config.NAVER_OPT_BTN:
                try:
                    self.driver.find_element(By.CSS_SELECTOR, btn_sel).click()
                    time.sleep(0.3)
                    for list_sel in Config.NAVER_OPT_LIST:
                        opts = self.driver.find_elements(By.CSS_SELECTOR, list_sel)
                        if opts:
                            for opt in opts:
                                txt = opt.text.replace("\n", " ").strip()
                                if txt: data.sizes.append({"name": txt, "isSoldOut": "품절" in txt})
                            return
                except: continue
        except: pass

    def _check_soldout(self) -> bool:
        return "품절" in self.driver.page_source


# ==========================================
# 8. 메인 실행
# ==========================================
def main():
    target_url = sys.argv[1] if len(sys.argv) > 1 else input("URL: ")
    driver = None
    try:
        driver = DriverFactory.create_driver()
        scraper: Optional[BaseScraper] = None
        if "musinsa.com" in target_url:
            scraper = MusinsaScraper(driver)
        elif "naver.com" in target_url or "smartstore" in target_url:
            scraper = NaverScraper(driver)

        if not scraper:
            print(json.dumps({"error": "지원하지 않는 사이트"}, ensure_ascii=False))
            return

        result = scraper.scrape(target_url)
        print(json.dumps(result.to_dict(), ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"error": str(e), "title": "Error"}, ensure_ascii=False))
    
    finally:
        if driver:
            try: driver.quit()
            except: pass

if __name__ == "__main__":
    main()