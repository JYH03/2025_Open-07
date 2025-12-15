const express = require("express");
const cors = require("cors");
const path = require("path");
const { spawn } = require("child_process"); // 파이썬 실행을 위한 모듈

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

// =======================================================
// ★ 중요: 아까 성공했던 파이썬 실행 파일의 "절대 경로" ★
// (백슬래시 \ 를 두 번씩 \\ 써야 오류가 안 납니다)
// =======================================================
const PYTHON_PATH = "python";
console.log("[Node.js] server.js loaded");

app.get("/test", (req, res) => {
  console.log("[Node.js] test endpoint hit");
  res.send("OK");
});

app.get("/api/scrape", (req, res) => {
  console.log("[Node.js] crawl endpoint hit");
  const productUrl = req.query.url;

  if (!productUrl) {
    return res.status(400).json({ error: "URL이 필요합니다." });
  }

  console.log(`[Node.js] 크롤링 요청 받음: ${productUrl}`);

  // 1. 파이썬 스크립트 실행 (crawler.py에게 URL을 전달)
  const pythonProcess = spawn(PYTHON_PATH, ["crawler.py", productUrl]);

  let resultData = "";
  let errorData = "";

  // 2. 파이썬이 출력(print)하는 데이터를 받아옴
  pythonProcess.stdout.on("data", (data) => {
    resultData += data.toString();
  });

  // 3. 파이썬 에러 로그 받기e 
  pythonProcess.stderr.on("data", (data) => {
    console.error("[PY DEBUG]", data.toString());  // 🔥 로그 출력  
    errorData += data.toString();
  });

  // 4. 파이썬 작업이 끝나면 실행되는 부분
  pythonProcess.on("close", (code) => {
    if (code !== 0) {
      console.error(`[Python Error] Exit Code: ${code}, Error: ${errorData}`);
      return res.status(500).json({ error: "크롤링 실패", details: errorData });
    }

    try {
      // 파이썬이 준 JSON 문자열을 실제 객체로 변환
      // (가끔 파이썬 로그가 섞일 수 있어서 JSON 부분만 찾는게 안전하지만, 
      // 현재 crawler.py는 깔끔하게 JSON만 뱉도록 짜여있음)
      const parsedResult = JSON.parse(resultData);

      // 가격 포맷팅 (프론트엔드 편의용)
      const format = (p) => p ? parseInt(p).toLocaleString() + "원" : "가격 정보 없음";
      parsedResult.priceFormatted = format(parsedResult.price);
      parsedResult.couponPriceFormatted = format(parsedResult.couponPrice);
      parsedResult.sourceUrl = productUrl;

      console.log("============== [Node.js PRICE DEBUG] ==============");
      console.log("원본 price 값:", parsedResult.price);
      console.log("포맷된 priceFormatted:", parsedResult.priceFormatted);
      console.log("원본 couponPrice:", parsedResult.couponPrice);
      console.log("포맷된 couponPriceFormatted:", parsedResult.couponPriceFormatted);
      console.log("====================================================");
      console.log(`[Node.js] 성공적으로 데이터 반환 완료`);
      res.json(parsedResult);

    } catch (e) {
      console.error("[Node.js] JSON 파싱 에러:", e);
      console.error("받은 데이터:", resultData);
      res.status(500).json({ error: "데이터 처리 실패", raw: resultData });
    }
  });
});

app.listen(PORT, () => {
  console.log(`🚀 Server running on http://localhost:${PORT}`);
  console.log(`🐍 Using Python at: ${PYTHON_PATH}`);
});