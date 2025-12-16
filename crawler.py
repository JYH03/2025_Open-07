import sys
import json
import re
import time
import requests
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
        ".product_bridge_product__price"
        ".origin_price"
        "strong.price"
        "div[class*='price'] > span"
        "strong[class*='price']"
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
    actualSizes: List[Dict[str, Any]] = field(default_factory=list)  # 🔥 추가
    colors: List[Dict[str, Any]] = field(default_factory=list) 
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
        self._prepare_page()

        data = self._scrape_from_json()
        if not data:
            data = ProductData(site=self.site_name)

        # 1️⃣ 가격 / 이미지 / actual-size API
        self._patch_missing_data(data)

        # 2️⃣ 색상 (DOM 기반, 상품 링크)
        self._collect_color_data(data)

        # 3️⃣ 사이즈 (actualSizes 있으면 HTML 스킵)
        self._collect_size_data(data)

        data.title = Utils.clean_title(data.title)
        return data

    
    def _patch_missing_data(self, data: ProductData):
        print(
            f"[DEBUG] patch_missing_data called",
            file=sys.stderr
        )

        if not data.title:
            data.title = self._get_meta_content(Config.META_TITLE) or self.driver.title

        if not data.image:
            data.image = self._get_meta_content(Config.META_IMAGE)

        if not data.price or data.price == 0:
            data.price = self._find_price_from_html()

    def _scrape_linked_colors(self, data: ProductData) -> bool:
        return False
    
    def _scrape_single_color(self, data: ProductData):
        pass

    def _extract_goods_no(self) -> Optional[str]:
        return None
    
    def _parse_shoe_sizes_from_dom(self) -> dict:
        return {}
    
    def _collect_size_data(self, data: ProductData):
        print("[PY DEBUG] Collect size data start", file=sys.stderr)

        # --------------------------------------------------
        # 1️⃣ goods_no 추출
        # --------------------------------------------------
        goods_no = self._extract_goods_no()
        print(f"[PY DEBUG] goods_no = {goods_no}", file=sys.stderr)

        # --------------------------------------------------
        # 2️⃣ actual-size API (상의 / 하의 / 신발 공통 A안)
        # --------------------------------------------------
        if goods_no:
            actual_json = self._fetch_actual_size(goods_no)
            print(f"[PY DEBUG] actual_json is None? {actual_json is None}", file=sys.stderr)

            if actual_json:
                try:
                    print(
                        "[PY DEBUG] actual_json keys:",
                        list(actual_json.keys()),
                        file=sys.stderr
                    )
                except Exception:
                    print("[PY DEBUG] actual_json keys print failed", file=sys.stderr)

                actual_sizes = self._parse_actual_size(actual_json)
                print(
                    f"[PY DEBUG] parsed actual_sizes = {actual_sizes}",
                    file=sys.stderr
                )

                # 🔥 A안: actual-size가 있으면 여기서 끝
                if actual_sizes:
                    data.actualSizes = actual_sizes

                    # 🔥 여기서 버튼용 sizes 생성
                    data.sizes = [
                        {
                            "name": size_name,
                            "isSoldOut": False  # actual-size API엔 품절 정보 없음
                        }
                        for size_name in actual_sizes.keys()
                    ]

                    print(
                        f"[PY DEBUG] Size source: actual-size API → buttons {data.sizes}",
                        file=sys.stderr
                    )
                    return

        # --------------------------------------------------
        # 3️⃣ 신발 DOM 사이즈 옵션 fallback (A안 확장)
        # --------------------------------------------------
        print("[PY DEBUG] Trying shoe DOM size parsing...", file=sys.stderr)

        shoe_sizes = self._parse_shoe_sizes_from_dom()

        print(
            f"[PY DEBUG] shoe_sizes from DOM = {shoe_sizes}",
            file=sys.stderr
        )

        if shoe_sizes:
            data.actualSizes = shoe_sizes
            data.sizes = [
                {
                    "name": size_name,
                    "isSoldOut": info.get("isSoldOut", False)
                }
                for size_name, info in shoe_sizes.items()
            ]

            print(
                f"[PY DEBUG] Size source: shoe DOM options → buttons {data.sizes}",
                file=sys.stderr
            )
            return
    # --------------------------------------------------
    # 3️⃣ 일반 HTML 버튼/드롭다운 파싱
    # --------------------------------------------------
        #print("[PY DEBUG] Trying General HTML Options parsing...", file=sys.stderr)
        #self._find_options_from_html(data)
        
        #if data.sizes:
            print(f"[PY DEBUG] Sizes found via HTML Options: {len(data.sizes)}", file=sys.stderr)
            return
    # --------------------------------------------------
    # 4️⃣ 최후 fallback (아무것도 못 찾은 경우)
    # --------------------------------------------------
        print("[PY DEBUG] No size information found (final fallback)", file=sys.stderr)
        is_global_soldout = self._check_soldout()
        print(f"[PY DEBUG] Global Soldout: {is_global_soldout}", file=sys.stderr)

        if is_global_soldout:
            print("[PY DEBUG] Product is Globally Soldout. Trying Info Notice fallback...", file=sys.stderr)
            # 품절 상태이므로, 여기서 가져오는 사이즈는 강제로 품절 처리됨
            self._scrape_size_from_info_notice(data)
        else:
            print("[PY DEBUG] Product is Active but no sizes found. Returning empty.", file=sys.stderr)

                
    def _collect_color_data(self, data: ProductData):
        print("[PY DEBUG] Collect color data start", file=sys.stderr)

        buttons = []
        sources = set()
        # 1. 드롭다운 크롤링 시도
        if self._scrape_color_dropdown(data):
            print(f"[PY DEBUG] Found colors via Dropdown: {len(data.colors)}", file=sys.stderr)
            return

        # 2. 다른 색상 연결 제품 확인 (Linked Products)
        # 드롭다운이 없으면 링크형 색상인지 확인
        if self._scrape_linked_colors(data):
            print(f"[PY DEBUG] Found colors via Links: {len(data.colors)}", file=sys.stderr)
            return

        # 3. 품절 여부 확인 (구매 버튼 비활성 여부 등)
        is_global_soldout = self._check_soldout()
        print(f"[PY DEBUG] Global Soldout Status: {is_global_soldout}", file=sys.stderr)

        if is_global_soldout:
            # 4. [품절인 경우] 상품 고시 정보에서 파싱
            print("[PY DEBUG] Product is sold out. Trying Info Notice fallback...", file=sys.stderr)
            self._scrape_color_from_info_notice(data)

        else:
            # 5. [품절 아님 + 위에서 못 찾음] -> '상세정보 확인 불가' 처리
            #    (제목 기반 단일 색상 추출 시도 후 없으면 종료)
            self._scrape_single_color(data)
            
            if not data.colors:
                print("[PY DEBUG] Active product but no color options found. Returning empty.", file=sys.stderr)


    def _scrape_color_dropdown(self, data: ProductData) -> bool:
        """
        STEP 1 & 2: 드롭다운 버튼을 찾아 열고 옵션을 파싱
        """
        try:
            # 1. 드롭다운 트리거 찾기 (제공해주신 HTML 기반)
            # placeholder가 '컬러'인 input 혹은 그 부모/형제 요소
            trigger_selectors = [
                "input[placeholder='컬러']",
                "input[placeholder*='색상']",
                "input[data-button-name*='컬러']",
                "input[data-button-name*='색상']",
                "div[data-mds='DropdownTriggerBox'] input[placeholder*='컬러']"
                "div[data-mds='DropdownTriggerBox'] input[placeholder*='색상']"
            ]

            trigger = None
            for sel in trigger_selectors:
                try:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in els:
                        if el.is_displayed() and el.get_attribute('placeholder') and any(x in el.get_attribute('placeholder') for x in ['컬러', '색상', 'Color']):
                            trigger = el
                            break
                    if trigger: break
                except:
                    continue

            if not trigger:
                return False

            print("[PY DEBUG] Color dropdown trigger found. Clicking...", file=sys.stderr)
            
            # 클릭 (JS로 클릭하는 것이 더 안정적일 때가 많음)
            self.driver.execute_script("arguments[0].click();", trigger)
            time.sleep(0.5) # 애니메이션 대기

            # 2. 옵션 컨테이너 대기 (Radix Portal 내부에 생성됨)
            # data-radix-portal 내부 혹은 role='option'을 찾음
            wait = WebDriverWait(self.driver, 3)
            options = []
            
            try:
                # 드롭다운 메뉴가 렌더링될 때까지 대기
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[role='option'], div[class*='OptionItemContainer']")))
                
                # 옵션 요소 수집
                # 무신사 최신 UI는 role="option" 혹은 특정 class 사용
                option_els = self.driver.find_elements(By.CSS_SELECTOR, "[role='option']")
                if not option_els:
                    option_els = self.driver.find_elements(By.CSS_SELECTOR, "div[class*='SelectOptionItemContainer']")

                options = [el for el in option_els if el.text.strip()]
            except Exception as e:
                print(f"[PY DEBUG] Color options wait failed: {e}", file=sys.stderr)
                return False

            if not options:
                return False

            # 3. 옵션 파싱
            extracted_colors = []
            for el in options:
                text = el.text.strip()
                if not text: continue
                
                # "블랙 (품절)" 등의 텍스트 처리
                # text 자체에 '품절'이 포함되어 있거나, 클래스/속성으로 확인
                is_soldout = False
                if "품절" in text:
                    is_soldout = True
                
                # aria-disabled나 data-disabled 확인
                if el.get_attribute("aria-disabled") == "true" or el.get_attribute("data-disabled") is not None:
                    is_soldout = True

                # 이름 정제 ( [10/15 예약배송] 같은 문구 제거 로직이 필요하면 추가)
                color_name = text.replace("품절", "").strip()
                
                extracted_colors.append({
                    "name": color_name,
                    "isSoldOut": is_soldout
                })

            if extracted_colors:
                data.colors = extracted_colors
                return True

        except Exception as e:
            print(f"[PY DEBUG] Error parsing color dropdown: {e}", file=sys.stderr)
        
        return False


    def _find_color_goods_from_dom(self) -> list:
        colors = []

        anchors = self.driver.find_elements(
            By.CSS_SELECTOR,
            "a[class*='OtherColorGoods__Anchor']"
        )

        current_goods_no = self._extract_goods_no()

        for a in anchors:
            href = a.get_attribute("href")
            if not href:
                continue

            m = re.search(r"/products/(\d+)", href)
            if not m:
                continue

            goods_no = m.group(1)

            colors.append({
                "goodsNo": goods_no,
                "isCurrent": goods_no == current_goods_no
            })

        return colors
    
    def _resolve_color_name(self, goods_no: str) -> tuple[str, str]:
        # 1️⃣ JSON 시도
        color = self._fetch_color_name_from_json(goods_no)
        if color:
            return color, "__NEXT_DATA__"

        # 2️⃣ title fallback
        color = self._fetch_color_name_from_title(goods_no)
        if color:
            return color, "page title"

        return "", "unknown"
    
    def _fetch_color_name_from_json(self, goods_no: str) -> str:
        try:
            script_el = self.driver.find_element(By.ID, "__NEXT_DATA__")
            json_data = json.loads(script_el.get_attribute("innerHTML"))

            page_props = json_data.get("props", {}).get("pageProps", {})

            state = (
                page_props.get("state")
                or page_props.get("initialState")
                or {}
            )

            product = (
                state.get("product")
                or state.get("goods")
                or page_props.get("product")
                or page_props.get("goods")
            )

            if not product:
                return ""

            goods_name = product.get("goodsNm") or product.get("goodsName", "")
            return self._extract_color_from_goods_name(goods_name)

        except Exception:
            return ""
        
    def _fetch_color_name_from_title(self, goods_no: str) -> str:
        try:
            title = self.driver.title
            title = title.replace("| 무신사", "").strip()
            title = re.sub(r'\s*-\s*사이즈\s*&\s*후기\s*$', '', title)

            parts = title.split()
            return parts[-1] if parts else ""

        except Exception:
            return ""
        
    def _extract_color_from_goods_name(self, goods_name: str) -> str:
        if not goods_name:
            return ""

        patterns = [
            r'\(([^)]+)\)\s*$',
            r'_([^_]+)$',
            r'-\s*([^-]+)$'
        ]

        for p in patterns:
            m = re.search(p, goods_name)
            if m:
                return m.group(1).strip()

        return ""

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
    def _scrape_single_color(self, data: ProductData):
    # 색상 정보 단순화: 아무 것도 안 함
        data.colors = []

    def _scrape_linked_colors(self, data: ProductData) -> bool:
        return False

    def _check_soldout(self) -> bool:
        return "품절" in self.driver.page_source
    
    def _prepare_page(self):
        pass

    def _extract_goods_no(self) -> Optional[str]:
        m = re.search(r"/products/(\d+)", self.driver.current_url)
        return m.group(1) if m else None

    def _fetch_actual_size(self, goods_no: str) -> Optional[dict]:
        url = f"https://goods-detail.musinsa.com/api2/goods/{goods_no}/actual-size"
        headers = {
            "User-Agent": Config.USER_AGENT,
            "Referer": f"https://www.musinsa.com/products/{goods_no}"
        }

        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code != 200:
                print(f"[PY DEBUG] actual-size API failed: {r.status_code}", file=sys.stderr)
                return None
            return r.json()
        except Exception as e:
            print(f"[PY DEBUG] actual-size request error: {e}", file=sys.stderr)
            return None
        
    def _parse_actual_size(self, actual_json: dict) -> dict:
        result = {}

        data = actual_json.get("data")
        if not isinstance(data, dict):
            # 아직 해석 불가 (상위 로직에서 판단)
            return result

        # ==================================================
        # 1️⃣ 의류 타입: sizes + items
        # ==================================================
        sizes = data.get("sizes")
        if isinstance(sizes, list):
            for s in sizes:
                size_name = s.get("name")
                if not size_name:
                    continue

                measurements = {}
                for item in s.get("items", []):
                    key = item.get("name")
                    value = item.get("value")

                    if key and value is not None:
                        measurements[key] = value

                # 의류는 measurements가 있을 때만 의미 있음
                if measurements:
                    result[size_name] = measurements

            if result:
                return result

        # ==================================================
        # 2️⃣ 신발 타입: footSize / mm 기반
        # ==================================================
        foot_sizes = data.get("footSize")
        if isinstance(foot_sizes, list):
            for f in foot_sizes:
                size = f.get("size") or f.get("length")
                if size:
                    result[str(size)] = {
                        "mm": size
                    }

        return result



    def _has_actual_size_api(self, goods_no: str) -> bool:
        if not goods_no:
            return False
        url = f"https://goods-detail.musinsa.com/api2/goods/{goods_no}/actual-size"
        try:
            res = requests.get(url, timeout=3)
            return res.status_code == 200 and "sizes" in res.text
        except:
            return False

    def _detect_product_type(self) -> str:
        goods_no = self._extract_goods_no()
        if goods_no and self._has_actual_size_api(goods_no):
            return "TYPE_A_ACTUALSIZE_DOM"

        # DOM에 사이즈 버튼 여러 개면 다중 옵션
        buttons = self.driver.find_elements(By.XPATH, "//button[normalize-space()]")
        texts = [b.text.strip() for b in buttons if b.text.strip()]

        if len(texts) == 1 and texts[0].upper() in ["FREE", "ONE SIZE"]:
            return "TYPE_C_FREE"

        if len(texts) >= 2:
            return "TYPE_D_DOM_MULTI"

        return "UNKNOWN"
    @property
    def site_name(self):
        return "musinsa"

    def _scrape_from_json(self):
        try:
            print("[DEBUG] Start parsing __NEXT_DATA__", file=sys.stderr)

            # 1. __NEXT_DATA__ 존재 여부
            script = self.driver.find_element(By.ID, "__NEXT_DATA__")
            raw_json = script.get_attribute("innerHTML")
            print("[DEBUG] __NEXT_DATA__ found", file=sys.stderr)

            data = json.loads(raw_json)
            print("[DEBUG] JSON loaded successfully", file=sys.stderr)

            # 2. state 접근
            page_props = Utils.safe_get(data, ["props", "pageProps"], {})

            state = (
                page_props.get("state")
                or page_props.get("initialState")
                or page_props
            )

            if not state:
                print("[DEBUG] state is missing or empty", file=sys.stderr)
                return None
            print(f"[DEBUG] state keys: {list(state.keys())}", file=sys.stderr)

            # 3. product / goods 접근
            product = (
                state.get("product")
                or state.get("goods")
                or page_props.get("product")
                or page_props.get("goods")
            )

            if not product:
                print("[DEBUG] product/goods object not found in state", file=sys.stderr)
                return None
            print(f"[DEBUG] product keys: {list(product.keys())}", file=sys.stderr)

            print(
                "[DEBUG] pageProps keys:",
                list(page_props.keys()),
                file=sys.stderr
            )


            # 4. 가격 확인
            price = int(
                product.get("finalPrice")
                or product.get("price")
                or product.get("salePrice")
                or product.get("goodsPrice")
                or 0
            )
            print(f"[DEBUG] extracted price: {price}", file=sys.stderr)

            # 5. ProductData 생성
            pd = ProductData(
                site="musinsa",
                title=product.get("goodsNm", ""),
                price=price,
                image=Utils.ensure_https(product.get("goodsImage", "")),
                status="soldout" if product.get("isSoldOut") else "active",
            )
            print("[DEBUG] ProductData initialized", file=sys.stderr)

            # 6. 옵션 접근
            opts = Utils.safe_get(product, ["goodsOption", "optionValues"], None)
            if opts is None:
                print("[DEBUG] goodsOption.optionValues not found", file=sys.stderr)
                return pd

            print(f"[DEBUG] optionValues found, count = {len(opts)}", file=sys.stderr)

            # 7. 사이즈 루프
            for idx, o in enumerate(opts):
                name = o.get("name")
                soldout = o.get("soldOutYn") == "Y"

                print(
                    f"[DEBUG] option[{idx}] name={name}, soldOut={soldout}",
                    file=sys.stderr
                )

                pd.sizes.append({
                    "name": name,
                    "isSoldOut": soldout,
                })

            print(f"[DEBUG] total sizes extracted: {len(pd.sizes)}", file=sys.stderr)
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

        print("[PY DEBUG] Try A-type static size buttons", file=sys.stderr)

        from selenium.common.exceptions import StaleElementReferenceException

        SIZE_RE = re.compile(
            r"^(XXXS|XXS|XS|S|M|L|XL|XXL|XXXL|FREE|ONE|ONE\s*SIZE|\d{2,3})$",
            re.I
        )

        EXCLUDE_WORDS = [
            "실측", "기준", "입력", "구매", "cm",
            "총장", "어깨", "가슴", "소매",
            "사이즈", "후기"
        ]

        # ✅ OptionBox 고정 노출 사이즈 버튼만 대상
        buttons = self.driver.find_elements(
            By.CSS_SELECTOR,
            "div[class*='OptionBox__SelectOptionItemContainer']"
        )

        for btn in buttons:
            try:
                text = self.driver.execute_script(
                    "return arguments[0].innerText;", btn
                )

                if not text:
                    continue

                text = text.replace("\n", " ").strip()

                # ❌ 가이드 / 입력 버튼 제거
                if any(word in text for word in EXCLUDE_WORDS):
                    continue

                token = text.split()[0].upper()

                # ❌ 사이즈 패턴 아닌 것 제거
                if not SIZE_RE.match(token):
                    continue

                cls = (btn.get_attribute("class") or "").lower()
                is_soldout = (
                    btn.get_attribute("disabled") is not None
                    or "disabled" in cls
                    or "pointer-events-none" in cls
                    or "품절" in text
                )

                data.sizes.append({
                    "name": token,
                    "isSoldOut": is_soldout
                })

            except StaleElementReferenceException:
                print("[PY DEBUG] stale element skipped", file=sys.stderr)
                continue

        # ✅ 하나라도 찾았으면 여기서 종료
        if data.sizes:
            print(f"[PY DEBUG] A-type sizes found: {data.sizes}", file=sys.stderr)
            return



        # ============================================================
        # 0) 🔥 고정 노출 사이즈 (A-2 타입) 먼저 탐색
        # ============================================================
        print("[PY DEBUG] Try static size list parsing", file=sys.stderr)

        static_size_selectors = [
            # 무신사 고정 사이즈 버튼 패턴들
            "div[class*='Size'] button",
            "ul[class*='size'] li button",
            "button[data-size]",
        ]

        static_options = []
        for sel in static_size_selectors:
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                els = [el for el in els if el.text.strip()]
                if els:
                    static_options = els
                    print(f"[PY DEBUG] Static size options found via {sel} ({len(els)})", file=sys.stderr)
                    break
            except:
                continue

        if static_options:
            for el in static_options:
                size = el.text.strip()
                cls = (el.get_attribute("class") or "").lower()
                disabled = el.get_attribute("disabled") is not None

                is_soldout = (
                    disabled
                    or "soldout" in cls
                    or "품절" in el.text
                )

                data.sizes.append({
                    "name": size,
                    "isSoldOut": is_soldout
                })

            return  # 🔥 여기서 끝 (드롭다운 로직 안 탐)


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
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException

        try:
            self.driver.execute_script("arguments[0].click();", trigger)
            print("[PY DEBUG] Dropdown clicked", file=sys.stderr)

            # ✅ 1) "열림"을 너무 좁게 잡지 말고 portal/컨텐츠 래퍼 등장으로 대기
            WebDriverWait(self.driver, 6).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "[data-radix-portal], div[data-mds*='DropdownMenu']")
                )
            )
            print("[PY DEBUG] Dropdown portal/container appeared", file=sys.stderr)

        except Exception as e:
            print(f"[PY DEBUG] Dropdown click or wait failed: {e}", file=sys.stderr)

        # ============================================================
        # 2) Radix DropdownMenuContent 안에서 옵션 탐색
        # ============================================================
        option_selectors = [
            # 🔥 네가 DevTools에서 확인한 진짜 옵션 노드
            "div[class*='OptionBox__SelectOptionItemContainer']",
            # 다른 페이지 변형 대비
            "[role='option']",
        ]

        options = []
        for sel in option_selectors:
            try:
                options = self.driver.find_elements(By.CSS_SELECTOR, sel)
                # 의미 없는 것(공백) 제거
                options = [el for el in options if el.text.strip()]
                if options:
                    print(f"[PY DEBUG] Options found via selector: {sel} ({len(options)})", file=sys.stderr)
                    break
            except Exception as e:
                print(f"[PY DEBUG] selector failed: {sel} ({e})", file=sys.stderr)

        if not options:
            print("[PY DEBUG] No options detected → Free Size", file=sys.stderr)
            data.sizes.append({
                "name": "Free / One Size",
                "isSoldOut": self._check_soldout()
            })
            return



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
            text = el.text.strip()
            if not text:
                continue

            cls = el.get_attribute("class").lower()
            data_disabled = el.get_attribute("data-disabled")

            is_soldout = (
                data_disabled is not None
                or "disabled" in cls
                or "gray-400" in cls
            )

            data.sizes.append({
                "name": text.split()[0],   # S / M / L / 260 등
                "isSoldOut": is_soldout
            })

    def _scrape_size_from_info_notice(self, data: ProductData):
        # 상품 정보 고시(Accordion) 내부의 '치수' 항목을 파싱
        print("[PY DEBUG] Trying to parse Info Notice with Unicode & Click...", file=sys.stderr)
        
        # '치수'의 유니코드: \uce58\uc218
        KEYWORD_SIZE = "\uce58\uc218" 
        
        try:
            # 0. 페이지 하단으로 스크롤
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 1000);")
            time.sleep(1)

            # 1. '상품 고시 정보' 탭 오픈
            # '상품 고시 정보'가 포함된 버튼 찾기 (유니코드: \uc0c1\ud488 \uace0\uc2dc \uc815\ubcf4)
            try:
                toggle_btn = self.driver.find_element(
                    By.XPATH, 
                    "//button[contains(., '\uc0c1\ud488 \uace0\uc2dc \uc815\ubcf4')]" 
                )
                # 닫혀있는지(aria-expanded="false") 확인 후 클릭
                if toggle_btn.get_attribute("aria-expanded") == "false":
                    self.driver.execute_script("arguments[0].click();", toggle_btn)
                    print("[PY DEBUG] Expanded Info Notice Accordion", file=sys.stderr)
                    time.sleep(1)
            except Exception:
                # 버튼 못 찾으면 이미 열려있거나 구조가 다르다고 판단하고 진행
                pass

            # 2. '치수' 항목 찾기 (유니코드 적용된 XPath)
            target_element = self.driver.find_element(
                By.XPATH, 
                f"//dt[.//span[contains(text(), '{KEYWORD_SIZE}')]]/following-sibling::dd[1]"
            )
            
            raw_text = target_element.text.strip()
            print(f"[PY DEBUG] Found Info Notice Text: {raw_text}", file=sys.stderr)

            # 3. 데이터 정제
            if not raw_text or "참조" in raw_text or "이미지" in raw_text:
                return

            import re
            tokens = re.split(r'[,/\n]+', raw_text)
            
            valid_sizes = []
            for t in tokens:
                clean_name = t.strip()
                if clean_name:
                    valid_sizes.append({
                        "name": clean_name,
                        "isSoldOut": True
                    })

            if valid_sizes:
                data.sizes.extend(valid_sizes)
                print(f"[PY DEBUG] Extracted sizes from Info Notice: {len(valid_sizes)}", file=sys.stderr)

        except Exception as e:
            print(f"[PY DEBUG] Info Notice parsing failed: {e}", file=sys.stderr)

    def _scrape_color_from_info_notice(self, data: ProductData):
        print("[PY DEBUG] Trying to parse Color from Info Notice...", file=sys.stderr)

        KEYWORD_COLOR = "\uc0c9\uc0c1"
        collected_colors = []

        try:
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight - 1000);"
            )
            time.sleep(1)

            try:
                toggle_btn = self.driver.find_element(
                    By.XPATH,
                    "//button[contains(., '\uc0c1\ud488 \uace0\uc2dc \uc815\ubcf4')]"
                )
                if toggle_btn.get_attribute("aria-expanded") == "false":
                    self.driver.execute_script(
                        "arguments[0].click();", toggle_btn
                    )
                    time.sleep(1)
            except Exception:
                pass

            target_element = self.driver.find_element(
                By.XPATH,
                f"//dt[.//span[contains(text(), '{KEYWORD_COLOR}')]]/following-sibling::dd[1]"
            )

            raw_text = target_element.text.strip()
            print(f"[PY DEBUG] Found Info Notice Color Text: {raw_text}", file=sys.stderr)

            if not raw_text or "참조" in raw_text or "이미지" in raw_text:
                return False
            
            import re
            tokens = re.split(r'[,/\n]+', raw_text)

            for t in tokens:
                t = t.strip()
                if not t:
                    continue
                

                clean_name = re.sub(r'^[\d]+[\.\)\s]*', '', t)

                if not clean_name: # 번호 지웠더니 빈 문자열이면 스킵
                    continue

                collected_colors.append({
                    "name": clean_name,
                    "isSoldOut": False
                })

        except Exception as e:
            print(f"[PY DEBUG] Color info notice error: {e}", file=sys.stderr)
            return False

        # 중복 제거
        unique_colors = []
        seen = set()
        for c in collected_colors:
            if c["name"] not in seen:
                seen.add(c["name"])
                unique_colors.append(c)

        if unique_colors:
            data.colors = unique_colors
            return True

        return False

    def _parse_shoe_sizes_from_dom(self) -> dict:
        print("[PY DEBUG] Enter _parse_shoe_sizes_from_dom()", file=sys.stderr)

        result = {}

        # --------------------------------------------------
        # 1️⃣ 구매 옵션 영역 후보 찾기
        # --------------------------------------------------
        containers = self.driver.find_elements(
            By.CSS_SELECTOR,
            "section, div"
        )

        for area in containers:
            text = self.driver.execute_script(
                "return arguments[0].innerText;", area
            )

            if not text:
                continue

            # --------------------------------------------------
            # 2️⃣ '구매 옵션 영역'인지 1차 판별
            #   - 사이즈 숫자
            #   - 품절 / 재입고 / 남음 키워드
            # --------------------------------------------------
            if not (
                re.search(r"\b2\d{2}\b", text) and
                ("품절" in text or "재고" in text or "남음" in text)
            ):
                continue

            print(
                "[PY DEBUG] size option container detected (preview):",
                text[:200],
                file=sys.stderr
            )

            # --------------------------------------------------
            # 3️⃣ 줄 단위 파싱 (핵심)
            # --------------------------------------------------
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue

                # ❌ 시즌/연도/평점 등 배제
                if any(x in line for x in ["SS", "FW", "평점", "후기"]):
                    continue

                # 토큰 분리
                tokens = line.replace("(", " ").replace(")", " ").split()

                for token in tokens:
                    # 1️⃣ 숫자 단독만 허용
                    if not re.fullmatch(r"\d{3}", token):
                        continue

                    mm = int(token)

                    # 2️⃣ 신발 사이즈 범위
                    if not (230 <= mm <= 300):
                        continue

                    # 3️⃣ 5mm 단위만 허용
                    if mm % 5 != 0:
                        continue

                    is_soldout = (
                        "품절" in line or
                        "재입고" in line
                    )

                    result[str(mm)] = {
                        "mm": mm,
                        "isSoldOut": is_soldout
                    }

            # 👉 첫 번째로 인식된 구매 옵션 영역만 사용
            if result:
                break

        print(
            f"[PY DEBUG] shoe_sizes from DOM (filtered) = {result}",
            file=sys.stderr
        )

        return result


    def _normalize_shoe_size_to_mm(self, raw: str) -> str:
        if not raw:
            return ""

        s = raw.strip().lower().replace("mm", "").replace("cm", "").strip()

        # 1) 3자리 mm (230~320 정도)
        if re.fullmatch(r"\d{3}", s):
            return s

        # 2) cm (정수/소수) → mm 변환
        if re.fullmatch(r"\d{2}(\.\d)?", s):
            cm = float(s)
            mm = int(round(cm * 10))
            # 신발 범위 sanity check (너무 튀면 변환 취소)
            if 200 <= mm <= 350:
                return str(mm)

        return ""



# ==========================================
# 7. NAVER SCRAPER (REVISED)
# ==========================================
class NaverScraper(BaseScraper):
    @property
    def site_name(self):
        return "naver"
    
    def _prepare_page(self):

        max_retries = 10  # 10번 시도
        interval = 2      # 2초 간격 (총 20초 대기)
        
        for i in range(max_retries):
            # 1. JSON 데이터가 로드되었는지 확인
            try:
                is_json_ready = self.driver.execute_script(
                    "return (window.__PRELOADED_STATE__ || window.__APOLLO_STATE__) !== undefined;"
                )
                if is_json_ready:
                    print(f"[PY DEBUG] JSON State detected! (Attempt {i+1})", file=sys.stderr)
                    return
            except:
                pass

            # 2. HTML 요소(가격/제목)가 화면에 떴는지 확인 (JSON 없는 페이지 대비)
            try:
                for sel in Config.NAVER_PRICE + Config.NAVER_TITLE:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if els and els[0].is_displayed():
                        print(f"[PY DEBUG] HTML Element detected! (Attempt {i+1})", file=sys.stderr)
                        return
            except:
                pass
            # 3. 아직 준비 안 됨 -> 대기
            print(f"[PY DEBUG] Page not ready yet... waiting ({i+1}/{max_retries})", file=sys.stderr)
            time.sleep(interval)

        print("[PY DEBUG] Timeout: Failed to detect valid product data.", file=sys.stderr)

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
