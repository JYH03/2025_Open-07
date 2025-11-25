const express = require("express");
const cors = require("cors");
const path = require("path");
const puppeteer = require("puppeteer");

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.static(path.join(__dirname, "public")));

app.get("/api/musinsa", async (req, res) => {
  const productUrl = req.query.url;

  if (!productUrl) {
    return res.status(400).json({ error: "url 쿼리 파라미터가 필요합니다." });
  }

  if (!productUrl.includes("musinsa.com")) {
    return res.status(400).json({ error: "무신사 상품 URL만 지원합니다." });
  }

  let browser;

  try {
    browser = await puppeteer.launch({
      headless: "new",
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
    });

    const page = await browser.newPage();

    // 🔥 PC 화면 강제 적용
    await page.setViewport({ width: 1920, height: 1080 });

    await page.setUserAgent(
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    );

    await page.goto(productUrl, {
      waitUntil: "networkidle2",
      timeout: 70000,
    });

    // 페이지가 다 로딩될 때까지 대기
    await page.waitForSelector("body", { timeout: 10000 });

    // ===========================
    //   🔥 evaluate 내부 실행
    // ===========================
    const data = await page.evaluate(() => {
      try {
        let ldData = null;
        let title = null;
        let price_final = null;
        let price_original = null;
        let discount_rate = null;
        let image = null;
        let sizes = [];

        // ===========================
        // 1) JSON-LD(구조화 데이터)
        // ===========================
        try {
          const scripts = document.querySelectorAll('script[type="application/ld+json"]');
          for (const script of scripts) {
            const json = JSON.parse(script.innerText.trim());
            if (
              json["@type"] === "Product" ||
              json["@type"] === "https://schema.org/Product"
            ) {
              ldData = json;
              break;
            }
          }
        } catch { }

        // ===========================
        // 2) 무신사 전역 변수(__MSS__)
        // ===========================
        const mssProduct =
          window.__MSS__?.product?.state ||
          window.__MSS__?.product?.data ||
          window.goods ||
          null;

        // ===========================
        // 제목
        // ===========================
        title =
          ldData?.name ||
          mssProduct?.goodsNm ||
          document.querySelector("meta[property='og:title']")?.content ||
          document.title;

        // ===========================
        // 가격
        // ===========================
        if (ldData?.offers) {
          const offer = Array.isArray(ldData.offers)
            ? ldData.offers[0]
            : ldData.offers;
          if (offer?.price) price_final = `${offer.price}원`;
        }

        if (!price_final && mssProduct) {
          price_final = mssProduct.goodsPrice
            ? `${mssProduct.goodsPrice}원`
            : null;
          price_original = mssProduct.consumerPrice
            ? `${mssProduct.consumerPrice}원`
            : null;
        }

        if (!price_final) {
          const priceEl =
            document.querySelector(".product-price") ||
            document.querySelector(".final_price") ||
            document.querySelector(".sale_price");
          if (priceEl) price_final = priceEl.innerText.trim();
        }

        // 할인율 계산
        if (price_final && price_original) {
          const finalNum = parseInt(price_final.replace(/[^0-9]/g, ""));
          const origNum = parseInt(price_original.replace(/[^0-9]/g, ""));
          if (origNum > finalNum) {
            discount_rate =
              Math.round(((origNum - finalNum) / origNum) * 100) + "%";
          }
        }

        // ===========================
        // 이미지
        // ===========================
        image =
          ldData?.image ||
          document.querySelector("meta[property='og:image']")?.content ||
          mssProduct?.goodsImg ||
          null;

        // ===========================
        // 사이즈 — 최신 무신사 구조
        // ===========================
        let sizeButtons = document.querySelectorAll("[data-testid='size-option']");
        if (sizeButtons.length > 0) {
          sizes = [...sizeButtons].map((btn) => btn.innerText.trim());
        }

        // __MSS__ 백업
        if (sizes.length === 0 && mssProduct?.option?.list) {
          sizes = mssProduct.option.list.map((opt) => opt.name);
        }

        // __NEXT_DATA__ 백업
        if (sizes.length === 0) {
          try {
            const nextData = JSON.parse(
              document.getElementById("__NEXT_DATA__")?.innerText || "{}"
            );
            const list =
              nextData.props?.pageProps?.product?.option?.list ||
              nextData.props?.pageProps?.initialState?.product?.option?.list;
            if (list) {
              sizes = list.map((o) => o.name);
            }
          } catch { }
        }

        sizes = [...new Set(sizes)].filter(Boolean);

        return {
          title,
          price_final,
          price_original,
          discount_rate,
          image,
          sizes,
        };
      } catch (err) {
        return { error: "evaluate_failed", detail: err.message };
      }
    });

    if (data.error) {
      console.error("Evaluate 오류:", data.detail);
      return res.status(500).json(data);
    }

    return res.json({ ...data, sourceUrl: productUrl });
  } catch (err) {
    console.error("크롤링 실패:", err.message);
    return res.status(500).json({
      error: "무신사 페이지 크롤링 실패",
      detail: err.message,
    });
  } finally {
    if (browser) await browser.close();
  }
});

app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
