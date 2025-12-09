import sys
import json
import re
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

sys.stdout.reconfigure(encoding='utf-8')

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ==========================================
# 1. CONFIG
# ==========================================
class Config:
    WINDOW_SIZE = "1920,1080"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    META_TITLE = "meta[property='og:title']"
    META_IMAGE = "meta[property='og:image']"

    MUSINSA_PRICE = [
        "span[class*='Price__']",
        "span[class*='CalculatedPrice']",
        "span[class*='text-title']",
        "span[class*='Price']",
    ]

    MUSINSA_OPTS_BTN = ["#option1 option", ".option1 button", ".opt-list li button"]
    MUSINSA_OPTS_LIST = [".option_list li", "#size_list li", ".goods_opt_list li"]

    NAVER_PRICE = [
        "._1LY7DqCnwR",
        "span._1LY7DqCnwR",
        ".product_price .price",
        ".lowest-price",
        "span._22kNQuPmbq",
        ".price_num",
        "strong.price",
        "span.cwq0ZTei2a",
        ".lowest .price",
    ]

    NAVER_TITLE = [
        "h3._22kNQuPmbq",
        "._22kNQuPmbq",
        "h3.cp-card__name",
        ".ABroB09L7j",
        "h3",
    ]


# ==========================================
# 2. PRODUCT DATA MODEL
# ==========================================
@dataclass
class ProductData:
    site: str
    title: str = ""
    price: int = 0
    image: str = ""
    sizes: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "active"
    couponPrice: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.couponPrice is None:
            result.pop("couponPrice")
        return result


# ==========================================
# 3. UTILITIES
# ==========================================
class Utils:
    @staticmethod
    def extract_number(text: Any) -> int:
        if not text:
            return 0
        clean = str(text).replace(",", "").replace("원", "")
        nums = re.findall(r"\d+", clean)
        return int(nums[0]) if nums else 0

    @staticmethod
    def ensure_https(url: str) -> str:
        return f"https:{url}" if url and url.startswith("//") else url

    @staticmethod
    def clean_title(title: str) -> str:
        if not title:
            return ""
        title = title.replace("\n", " ")
        title = re.sub(r"^\[.*?\]\s*", "", title)
        return title.strip()

    @staticmethod
    def safe_get(d: Dict, keys: List[str], default=None):
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k, {})
            else:
                return default
        return d if d else default


# ==========================================
# 4. SELENIUM DRIVER
# ==========================================
class DriverFactory:
    @staticmethod
    def create_driver() -> WebDriver:
        options = Options()
        #options.add_argument("--headless=new")
        options.add_argument(f"--window-size={Config.WINDOW_SIZE}")
        options.add_argument(f"user-agent={Config.USER_AGENT}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options,
        )

        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            },
        )
        return driver


# ==========================================
# 5. BASE SCRAPER
# ==========================================
class BaseScraper(ABC):
    def __init__(self, driver: WebDriver):
        self.driver = driver

    def scrape(self, url: str) -> ProductData:
        self.driver.get(url)
        time.sleep(2)

        data = self._scrape_from_json()
        if not data:
            data = ProductData(site=self.site_name)

        self._patch_missing_data(data)
        data.title = Utils.clean_title(data.title)

        if len(data.sizes) == 0:
            data.sizes.append({
                "name": "Free / One Size",
                "isSoldOut": self._check_soldout()
            })

        return data

    def _patch_missing_data(self, data: ProductData):
        if not data.title:
            data.title = self._get_meta_content(Config.META_TITLE) or self.driver.title

        if not data.image:
            data.image = self._get_meta_content(Config.META_IMAGE)

        if not data.price or data.price == 0:
            data.price = self._find_price_from_html()

        if not data.sizes:
            self._find_options_from_html(data)

    def _find_price_from_html(self) -> int:
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span[class*='Price']"))
            )
        except:
            print("[DEBUG] Price wait failed", file=sys.stderr)

        for sel in Config.MUSINSA_PRICE:
            elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elements:
                txt = el.text.strip()
                price = Utils.extract_number(txt)
                if price > 100:
                    print(f"[DEBUG] Price found: {price}", file=sys.stderr)
                    return price

        print("[DEBUG] Price not found", file=sys.stderr)
        return 0

    @property
    @abstractmethod
    def site_name(self): ...

    @abstractmethod
    def _scrape_from_json(self): ...

    @abstractmethod
    def _find_title_from_html(self): ...

    @abstractmethod
    def _find_options_from_html(self, data: ProductData): ...

    @abstractmethod
    def _check_soldout(self) -> bool: ...

    def _get_meta_content(self, selector: str) -> str:
        try:
            return self.driver.find_element(By.CSS_SELECTOR, selector).get_attribute("content")
        except:
            return ""


# ==========================================
# 6. MUSINSA SCRAPER
# ==========================================
class MusinsaScraper(BaseScraper):
    @property
    def site_name(self):
        return "musinsa"

    def _scrape_from_json(self):
        try:
            script = self.driver.find_element(By.ID, "__NEXT_DATA__")
            data = json.loads(script.get_attribute("innerHTML"))

            state = Utils.safe_get(data, ["props", "pageProps", "state"])
            product = state.get("product") or state.get("goods")

            if not product:
                print("[DEBUG] JSON product missing", file=sys.stderr)
                return None

            price = int(
                product.get("finalPrice")
                or product.get("price")
                or product.get("salePrice")
                or product.get("goodsPrice")
                or 0
            )

            pd = ProductData(
                site="musinsa",
                title=product.get("goodsNm", ""),
                price=price,
                image=Utils.ensure_https(product.get("goodsImage", "")),
                status="soldout" if product.get("isSoldOut") else "active",
            )

            opts = Utils.safe_get(product, ["goodsOption", "optionValues"], [])
            for o in opts:
                pd.sizes.append({
                    "name": o.get("name"),
                    "isSoldOut": o.get("soldOutYn") == "Y",
                })
            return pd

        except Exception as e:
            print(f"[DEBUG] JSON parse error: {e}", file=sys.stderr)
            return None

    def _find_title_from_html(self):
        return ""

    def _find_options_from_html(self, data: ProductData):
        print("[PY DEBUG] Option parsing start", file=sys.stderr)

        # JSON에서 이상한 값 오염되었으면 초기화
        if any(not s.get("name") for s in data.sizes):
            data.sizes = []

        # JSON으로 이미 옵션을 가져왔다면 굳이 HTML 안 뒤짐
        if data.sizes:
            print("[PY DEBUG] JSON options already available", file=sys.stderr)
            return

        wait = WebDriverWait(self.driver, 5)

        # ============================================================
        # 1) Radix Dropdown 트리거(옵션박스 클릭)
        # ============================================================
        trigger_selectors = [
            "div[class*='DropdownTrigger']",             # 가장 안정적
            "input[class*='DropdownTriggerInput']",      # v2 구조
            "div[class*='OptionBox__SelectContainer']",  # 예전 + 일부 최신
            "input[placeholder*='옵션']", 
            "input[readonly]"
        ]

        trigger = None
        for sel in trigger_selectors:
            try:
                trigger = self.driver.find_element(By.CSS_SELECTOR, sel)
                print(f"[PY DEBUG] Trigger found: {sel}", file=sys.stderr)
                break
            except:
                continue

        if not trigger:
            print("[PY DEBUG] No dropdown trigger found", file=sys.stderr)
            return

        # 클릭하여 옵션 메뉴 열기
        try:
            self.driver.execute_script("arguments[0].click();", trigger)
            time.sleep(0.8)
            print("[PY DEBUG] Dropdown opened", file=sys.stderr)
        except Exception as e:
            print(f"[PY DEBUG] Dropdown click failed: {e}", file=sys.stderr)

        # ============================================================
        # 2) Radix DropdownMenuContent 안에서 옵션 탐색
        # ============================================================
        option_selectors = [
            # 최신 무신사 (Radix UI)
            "div[class*='DropdownMenuContent'] button",
            "div[class*='DropdownMenuContent'] div[data-state] button",

            # Radix 내부 구성요소
            "div[class*='OptionBox__SelectOptionItemContainer'] button",

            # 예전 구조
            "ul[class*='OptionList'] li button",
            "ul.option_list li button"
        ]

        options = []
        for sel in option_selectors:
            try:
                options = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if options:
                    print(f"[PY DEBUG] Options found via selector: {sel} ({len(options)})", file=sys.stderr)
                    break
            except:
                continue

        # ============================================================
        # 3) 만약 아직도 못 찾았다면 Radix portal 내부를 다시 검사
        # ============================================================
        if not options:
            print("[PY DEBUG] No options found → retrying portal...", file=sys.stderr)
            time.sleep(0.5)

            try:
                portal = self.driver.find_elements(By.CSS_SELECTOR, "[data-radix-portal]")
                if portal:
                    options = portal[0].find_elements(By.CSS_SELECTOR, "button")
                    print(f"[PY DEBUG] Portal options: {len(options)}", file=sys.stderr)
            except:
                pass

        # 그래도 없음 → Free 처리
        if not options:
            print("[PY DEBUG] No options detected → Free Size", file=sys.stderr)
            data.sizes.append({
                "name": "Free / One Size",
                "isSoldOut": self._check_soldout()
            })
            return

        # ============================================================
        # 4) 파싱
        # ============================================================
        for el in options:
            text = el.text.replace("\n", " ").strip()
            if not text:
                continue

            parts = text.split()
            size = parts[0]  # S, M, L, 42, 260 등

            cls = el.get_attribute("class").lower()
            is_disabled = el.get_attribute("disabled") is not None
            soldout_text = ("품절" in text)

            is_soldout = is_disabled or soldout_text or "disabled" in cls

            data.sizes.append({
                "name": size,
                "isSoldOut": is_soldout
            })

        print(f"[PY DEBUG] Final parsed sizes: {data.sizes}", file=sys.stderr)



    def _check_soldout(self) -> bool:
        return "품절" in self.driver.page_source or "soldout" in self.driver.page_source.lower()


# ==========================================
# 7. NAVER SCRAPER
# ==========================================
class NaverScraper(BaseScraper):
    @property
    def site_name(self):
        return "naver"

    def _scrape_from_json(self):
        try:
            html = self.driver.page_source
            match = re.search(r"window\.__PRELOADED_STATE__\s*=\s*({.*?});", html)
            if not match:
                print("[DEBUG] NAVER JSON missing", file=sys.stderr)
                return None

            state = json.loads(match.group(1))
            product = Utils.safe_get(state, ["product", "A"])

            if not product:
                return None

            return ProductData(
                site="naver",
                title=product.get("name", ""),
                price=product.get("discountedPrice")
                or product.get("salePrice")
                or product.get("price", 0),
            )
        except Exception as e:
            print(f"[DEBUG] NAVER JSON error: {e}", file=sys.stderr)
            return None

    def _find_title_from_html(self):
        for sel in Config.NAVER_TITLE:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.text.strip():
                    return el.text.strip()
            except:
                continue
        return ""

    def _find_options_from_html(self, data: ProductData):
        pass

    def _check_soldout(self):
        return "품절" in self.driver.page_source


# ==========================================
# 8. MAIN
# ==========================================
def main():
    url = sys.argv[1] if len(sys.argv) > 1 else input("URL: ")

    driver = DriverFactory.create_driver()

    scraper = None
    if "musinsa.com" in url:
        scraper = MusinsaScraper(driver)
    elif "naver" in url or "smartstore" in url:
        scraper = NaverScraper(driver)

    if not scraper:
        print(json.dumps({"error": "Unsupported URL"}, ensure_ascii=False))
        return

    result = scraper.scrape(url)
    print(json.dumps(result.to_dict(), ensure_ascii=False))

    driver.quit()


if __name__ == "__main__":
    main()
