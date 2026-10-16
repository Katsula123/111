# MOTOR DAILY｜車壇日報

一個針對台灣讀者設計的免費汽機車新聞網站：深色雜誌風、四個分類、獨立文章頁，使用 Python + RSS + GitHub Actions + GitHub Pages。

> **重要：不是 AI 自動撰寫完整新聞。** 免費版僅依合法可用的新聞中繼資料與摘要，呈現可確認的內容。來源不充足時只刊登簡短消息，不編造售價、馬力、交通新制實施時間，也不隨意使用媒體圖片。

## 新手上線：GitHub Pages

1. 到 [github.com/new](https://github.com/new) 建立**公開（Public）**儲存庫，建議名稱為 `motor-daily`，預設分支 `main`。
2. 把 `motor-daily.zip` 在電腦上**解壓縮**。進入解壓後的 `motor-daily` 資料夾，將裡面所有檔案和資料夾（**包括隱藏的 `.github` 資料夾**）上傳到儲存庫根目錄。不要只上傳 ZIP。
3. 打開儲存庫 **Settings → Actions → General → Workflow permissions**，選 **Read and write permissions** 並儲存。組織政策可能限制此設定；若無法修改，可請管理員協助。
4. 到 **Settings → Pages → Build and deployment → Source** 選擇 **GitHub Actions**。
5. 進入儲存庫 **Actions**，選「更新車壇新聞並發布網站」→ **Run workflow** → **Run workflow**。或者初次上傳至 main 的 push 已可能啟動流程。
6. 等待頁面顯示綠色勾勾後，進入 **Settings → Pages** 查看網站網址（通常是 `https://你的帳號.github.io/motor-daily/`）。
7. 日後排程將在台灣時間 00:17、03:17、06:17、09:17、12:17、15:17、18:17、21:17 左右檢查更新；GitHub 不保證準點執行。

**注意：** 第一版包含 4 篇明確標示的「示範文章」，只是為了讓你在上線前就能看到版面。第一次成功抓到新新聞後就會移除示範文章；如果 RSS 來源在你的網路環境失效，則會保留示範內容並記錄錯誤。

## 本地預覽

安裝 Python 3.11 以上後，在專案資料夾執行：

```bash
pip install -r requirements.txt
python scripts/build.py
python -m http.server 8000 --directory dist
```

瀏覽器開啟 `http://localhost:8000/`。

想手動更新新聞（需要網路）：

```bash
python scripts/update_news.py
python scripts/build.py
```

## 資料來源與文章品質

- `config/feeds.json`：目前包含 Google News RSS 關鍵字搜尋及公路局 RSS。Google News 僅是**新聞發現工具**，RSS 標題不能被視為官方事實查核；閱讀詳細報導仍應點擊「原始來源」。RSS 源可能改版、限制取用或暫時失效，可由此檔調整。
- `scripts/update_news.py`：每次擷取最新項目，篩掉不相關與重複標題，保留最近 15 天的新項目，長期保存最多 120 篇；若取不到資訊便保留既有新聞。
- `data/articles.json`：新聞資料與最後成功更新時間；GitHub Actions 會提交更新以保存歷史文章。
- 標題與有限的公開描述不足時，**只發布較短摘要**。此版不依賴付費 AI 或任意爬取新聞全文，不能保證每篇都有 300～500 字。
- 交通新聞不根據標題推定法律已生效，只標示標題可能反映的階段與核對提醒。
- 禁止把未確認的傳聞、車款規格與日期補進文章。

### 如何設定圖片

為避免圖片車型錯誤與侵權，網站會**保守地**嘗試從 Wikimedia Commons 搜尋可合法再利用且檔名符合明確「車廠＋車型」的照片，會檢查可用的授權資訊；若新聞含年份，還要求檔名對應該年份。搜尋結果不符或無法確認就使用本站製作的「**主題概念 SVG 插畫**」，它們**不是實際新聞車款照片**。圖片自動比對仍非完美，發布者應定期檢查圖片車款、年份、作者及授權。可在 `config/settings.json` 關閉自動圖片搜尋。

若找到已確認與報導車款／年份相符、且確實允許本網站使用的車款照片，請修改 `config/image_map.json`，例如：

```json
{
  "Toyota GR86": {
    "url": "https://example.org/your-licensed-image.jpg",
    "page": "https://example.org/photo-license-page",
    "credit": "照片作者／來源名稱",
    "license": "CC BY-SA 4.0"
  }
}
```

以上網址只是**格式範例**，不能直接使用。圖片 URL、授權頁、作者與條款必須真實且已確認。標題含相同車型字串時會套用圖片；**仍應確認年式及版本是否符合**。需長期儲存或大量使用前，請核對來源授權並避免依賴會失效的外部圖床。

### 站內文章頁說明

每篇都有 `article/<ID>/index.html`，分類頁在 `category/<分類>/index.html`，可直接分享獨立網址。網站使用靜態 HTML，沒有伺服器後端，也不需要網站訪客使用 Python。

## 檔案結構

```text
motor-daily/
├─ .github/workflows/publish.yml   自動更新與部署
├─ assets/                         CSS、SVG 通用示意插畫
├─ config/feeds.json               RSS 來源
├─ config/image_map.json           已確認授權的圖片對照
├─ config/settings.json            Wikimedia 圖片開關
├─ data/articles.json              文章資料
├─ scripts/update_news.py          更新新聞
├─ scripts/build.py                產生網站
├─ templates/                     HTML 模板
├─ tests/                         基本測試
├─ requirements.txt
└─ dist/                            本地產生，GitHub Actions 部署用
```

## 免費限制與維護

- GitHub Pages 和 Actions 使用各自的免費額度及服務政策；若 GitHub 改變方案、流量或儲存庫限制，需依當時規則調整。
- 排程可能延後；公開儲存庫在長期沒有活動時，排程可能被 GitHub 停用。請偶爾確認 Actions 執行情況。
- RSS、Google News 和政府網站均可能變動。若來源無法正常取得，日後可能需要更新 URL 或擷取規則。
- 新聞整理品質受可公開使用的資料限制。這份專案重視「不編造」高於長度，適合資訊導覽與來源索引，不應當作已獨立查證的深度新聞報導。

GitHub 參考文件：
- [使用自訂工作流程部署 Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [GitHub Actions 排程與時區](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule)
- [公路局 RSS 訂閱](https://www.thb.gov.tw/cp.aspx?n=219)
