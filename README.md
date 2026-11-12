# Shop Insights: an AI sales advisor for online shops

Upload your shop's order history (CSV or Excel) and get:

1. **Products to promote**: sales are growing.
2. **Dying products**: sales dropped hard or almost stopped.
3. **Bought together**: pairs that often share an order, as bundle ideas (support, confidence, lift).
4. **Forecast**: weekly sales for the next 4 weeks for the top products.
5. **Restock list**: what to reorder and **how many units** (optional current-stock upload).
6. **AI summary**: a short plain-English summary written by Google Gemini (optional).
7. **Proof**: a backtest that hides the last month, recommends from the earlier data only, and
   compares every recommendation with a simple baseline. The numbers are reported honestly,
   including where the baseline wins.

Built with **Python** (pandas, NumPy, SciPy, scikit-learn, FastAPI, pytest) and **React + Vite**.
The demo data is the public [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
dataset: about 1 million real order lines from a UK online gift shop, Dec 2009 to Dec 2011.

## Screenshots

_Screenshots coming soon._ To add them, save PNGs of each tab into `docs/screenshots/` and
uncomment the lines below in this README.

<!--
![Overview](docs/screenshots/overview.png)
![Proof (backtest)](docs/screenshots/proof.png)
![Restock list](docs/screenshots/restock.png)
![Forecast](docs/screenshots/forecast.png)
-->

---

---

## Run it locally (Windows PowerShell)

Requirements: Python 3.11+ and Node.js 20+.

```powershell
# 1. Backend: virtual env + packages
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Data: download the dataset (~45 MB, not stored in git), then clean it into Parquet
python -m scripts.download_data
python -m scripts.prepare_data

# 3. (Optional) AI summary: copy the example env file and paste your free Gemini key
Copy-Item .env.example .env      # then edit .env: GEMINI_API_KEY=...

# 4. Start the API on http://localhost:8000 (interactive docs at /docs)
uvicorn api.main:app --reload
```

In a **second** PowerShell window:

```powershell
cd frontend
npm install
npm run dev        # open http://localhost:5173
```

Click **Run demo analysis**, or upload your own file. To try the restock upload, use
`data/sample/SAMPLE_current_stock.csv`. Those stock numbers are made up: see
[data/sample/README.md](data/sample/README.md).

Other useful commands (from `backend/`, with the venv active):

```powershell
python -m pytest                    # 33 tests
python -m scripts.run_analysis      # every step on the full dataset: prints timings + backtest, writes docs/results.json
python -m scripts.make_sample_stock # regenerate the SAMPLE stock file
```

If `Activate.ps1` is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

---

## Project structure

```
backend/
  shop_insights/            # all analysis logic: plain, testable functions, no web code
    data/                   # download, load (CSV/Excel + column aliases), cleaning, summary
    analysis/
      weekly.py             # product x week tables anchored on a cutoff date (no future data)
      trends.py             # promote / dying
      basket.py             # bought together (sparse matrices)
      forecast.py           # global gradient-boosting forecast + baselines
      restock.py            # needed stock, safety stock, stock-file parsing
      backtest.py           # hidden-month backtest of everything vs baselines
    pipeline.py             # runs every analysis -> one JSON-ready dict
    ai_summary.py           # Gemini prompt built only from computed numbers
  api/                      # FastAPI: routes, upload limits, hash-keyed cache
  scripts/                  # download, prepare, run_analysis, make_sample_stock
  tests/                    # pytest (synthetic data with known answers)
frontend/src/               # React: upload page, results tabs, SVG charts
data/sample/                # SAMPLE stock file (made-up, clearly labelled)
docs/results.json           # backtest numbers + timings written by scripts/run_analysis
```

---

## How it works

### Data cleaning (`backend/shop_insights/data/cleaning.py`)

| Step | Rows removed (full dataset) |
|---|---:|
| Exact duplicate lines | 34,335 |
| Cancellations **and the orders they cancelled** | 25,437 |
| Bookkeeping adjustments (invoice starting with "A") | 6 |
| Zero/negative quantity or price | 6,013 |
| Non-product codes (postage, fees, vouchers, manual, tests…) | 4,463 |
| **Kept** | **997,117 of 1,067,371** |

Cancellations are matched back to the original order (same customer, product and quantity,
the latest one before the cancellation). Otherwise a cancelled 80,995-unit order would stay
in the data as if it had happened. Missing descriptions are filled with the product's most
common name. Codes and text columns are stored as `category`, and the clean table is saved
as Parquet. It reloads in about 0.1 s and takes 47 MB of memory.

### Promote and dying (`trends.py`)

Each product's **last 8 weeks** are compared with the **8 weeks before**.

- **Promote:** units up by 25% or more, **and** more order lines than before (so one huge
  order isn't a "trend"), **and** a positive weekly slope. Small products are excluded
  (under 50 units). Ranked by extra units sold.
- **Dying:** sold 50+ units before, then fell by 50% or more, or got 2 or fewer orders recently.
- Every row also shows **the same weeks last year**. If last year moved the same way, the
  reason says "likely seasonal". In Nov–Dec most rising products are Christmas items.

### Bought together (`basket.py`)

For each pair A, B (last 52 weeks):

- **support** = share of all orders containing both;
- **confidence A→B** = share of A's orders that also contain B;
- **lift** = confidence A→B ÷ share of orders with B. A lift of 1 means chance; 100 means
  the pair appears together 100 times more often than chance.

Efficient version: only products in 100+ orders are kept. They go into a **sparse** 0/1
orders × products matrix `X` (SciPy), and **`Xᵀ·X`** gives every pair's co-occurrence count
in one multiplication. That's 0.4–0.7 s instead of building a 40,000 × 4,000 dense table.

### Forecast (`forecast.py`)

- **One global model** (scikit-learn `HistGradientBoostingRegressor`, Poisson loss), trained
  in a single batch on the **top 300 products** of the last 12 weeks, plus any product in an
  uploaded stock file. It is not one model per product.
- Each product's weekly sales are **divided by its own recent level**, so a pattern learned
  on a big seller transfers to a small one.
- Features: last 4 weeks, 4- and 12-week averages, variability, how many recent weeks had
  sales, **the same week last year** and last year's change, product size, week of year,
  horizon.
- **Direct multi-horizon:** the horizon (1–4 weeks ahead) is a feature, so we never feed
  predictions back in.
- Baselines: *average of the last 4 weeks* and *same weeks last year*.

The shop closes over Christmas. The model learned that from last year's same weeks, so the
week ending 30 Dec is forecast at almost zero.

### Restock (`restock.py`)

The sales data has no stock levels, so the plan starts from forecast demand:

```
protection window = lead time + coverage        (default 2 + 2 = 4 weeks; both adjustable)
expected demand   = forecast units summed over the window
safety stock      = z × weekly variation × √(window weeks)       z = 1.65 ≈ 95% no stock-out
needed stock      = expected demand + safety stock
units to order    = max(0, needed stock − current stock)         (if a stock file is uploaded)
weeks of stock    = current stock ÷ expected weekly demand
```

- **Why lead time + coverage?** Stock you order today has to last until the *next* delivery:
  the wait for this delivery, plus the time it should last afterwards.
- **Why √weeks?** Random good and bad weeks partly cancel out. The uncertainty over 4 weeks
  is about √4 = 2 times one week's, not 4 times.
- **Weekly variation** is measured robustly: 1.4826 × the median absolute deviation of the
  last 12 weeks. That equals the standard deviation for normal data, but one 5,000-unit
  wholesale order can't blow it up.
- **With a stock file:** only products below the needed level are listed, most urgent first.
  The row is flagged **URGENT** when stock runs out before a new delivery could arrive.
  **Without one:** you get the recommended stock level for each product.

---

## The backtest: does it work?

**Setup:** the cutoff is **2011-11-11**. Everything after it (to 2011-12-09, 4 weeks) is
hidden. Every recommender receives only `orders_until(cutoff)`, and the hidden weeks are only
used for scoring. A unit test checks this: adding fake sales after the cutoff must not change
any prediction. Model settings were fixed before the hidden month was scored. The forecast
is also scored on the **month before** as a stability check.

All numbers below come from `python -m scripts.run_analysis` (saved in
[docs/results.json](docs/results.json)).

### Forecast: 300 products × 4 weeks (346,612 real units)

| Method | Hidden month WAPE | Hidden month bias | Month before WAPE | Month before bias |
|---|---:|---:|---:|---:|
| **Model** | 52.9% | +5.3% | **60.7%** | −22.1% |
| Average of last 4 weeks | **49.1%** | −2.0% | 66.0% | −1.2% |
| Same weeks last year | 83.5% | −23.1% | 88.3% | −19.6% |

WAPE = total units we were off by ÷ total units sold (lower is better).
**Honest result:** the model beat the 4-week average in the month before (60.7% vs 66.0%),
but **lost in the hidden month** (52.9% vs 49.1%). It was better on only 44% of products there.
Weekly sales of single gift products are very noisy, and a 4-week average is a strong
baseline. The model is not clearly better.

### Promote list (top 20)

A "hit" means the product **gained share** of the shop's sales in the hidden month. The whole
shop grew 8.8% in that month (Christmas), so "sales went up" would be true for almost anything.

| List | Hit rate | Median growth |
|---|---:|---:|
| **Model's promote list** | **50%** | **+8.5%** |
| Last month's best sellers (baseline) | 35% | −2.7% |

### Dying list (top 20)

A "hit" means the product sold **less than half of its earlier normal month** in the hidden month.

| List | Hit rate | Earlier normal month (units) |
|---|---:|---:|
| Model's dying list | 60% | 22,895 |
| **Last month's worst sellers (baseline)** | **85%** | 3,099 |

**The baseline wins here.** The model's list covers much bigger products, and some of them are
seasonal items that recovered. (A first version of this metric used "lost share". That is
impossible for products already at zero, so the baseline scored 0% by construction. I
replaced it before reporting.)

### Bought-together pairs (top 20)

| Pairs | Seen in hidden month | Still bought together (lift > 1) | Median lift | Median confidence |
|---|---:|---:|---:|---:|
| **Model (highest lift)** | 16 / 20 | 93.8% | **99.3×** | **63.4%** |
| Most common pairs (baseline) | 20 / 20 | 100% | 8.4× | 56.9% |

The high-lift pairs held up on new orders. The baseline pairs are more common, but they are
mostly best sellers that appear together by volume.

### Restock: 300 products, lead time 2 + coverage 2 weeks

"Stock held" = the recommended level at the cutoff, compared with real sales in the 4 hidden weeks.

| Strategy | Ran out | Fill rate | Units short | Units left over | Overstocked (>1.5× demand) |
|---|---:|---:|---:|---:|---:|
| **Model + safety stock** | **40 (13.3%)** | **92.2%** | **26,992** | 164,963 | 155 |
| Model forecast only | 110 (36.7%) | 83.4% | 57,387 | 76,038 | 87 |
| Same as last month (baseline) | 153 (51.0%) | 81.4% | 64,385 | **57,546** | **62** |

Safety stock is a **trade-off**: far fewer stock-outs, but more stock left over.
Change history (also reported honestly): the first version used a plain standard deviation.
It ran out on only 30 products (10.0%, fill rate 95.7%) but held 557,770 units, with 226,038
left over. A live run then gave a 40-unit-a-week product 855 units of safety stock, because
of one wholesale order. Switching to the robust measure cut leftovers by 61k units, at the
cost of 10 more stock-outs.

### Known limitations

- **Forecast vs baseline:** not clearly better than a 4-week average (see above).
- **Seasonal safety stock:** for an item at the end of its season, the last 12 weeks include
  the whole seasonal ramp-up. Its "weekly variation" is then large, and so is its safety
  stock (e.g. 1,133 units for ~40/week). The proper fix is to base safety stock on the
  model's own past forecast errors. I didn't add it, because tuning again against the same
  hidden month would overfit the test.
- **One test month:** the backtest is a single 4-week window (plus one extra forecast month)
  in the Christmas season. Rolling backtests over many months would give firmer numbers.
- The restock backtest assumes you start the month holding the recommended level, with no
  other deliveries in between.

---

## Performance

Measured on the full dataset (997k clean rows) with `python -m scripts.run_analysis` on a
laptop (Intel i7-13620H, plugged in):

| Step | Time |
|---|---:|
| Read Excel (calamine engine) + clean + save Parquet (`prepare_data`, once) | 14.4 s |
| Load cleaned Parquet | 0.07 s |
| Promote + dying | 0.17 s |
| Bought together (sparse) | 0.44 s |
| Forecast: build features, train, predict (300 products) | 3.6 s |
| Restock (with stock file) | 0.02 s |
| Full backtest (trends, bundles, restock, forecast at 2 cutoffs) | 7.8 s |

Through the API: the demo analysis took **14.2 s** the first time and **0.22 s** when repeated
(cache). Uploading the original 45 MB Excel file took **31.8 s**, then **0.46 s** when uploaded
again, since the file is only hashed. On battery power-saving the same laptop ran about 3–4×
slower, so measure while plugged in.

How it stays fast:
- vectorized pandas/NumPy everywhere: `groupby`/`unstack` for weekly tables, one matrix
  product for all trend slopes;
- sparse `Xᵀ·X` for basket pairs;
- one batched global forecast model instead of 300 small ones;
- `category` dtypes and Parquet;
- API results cached by a SHA-256 hash of file + stock file + settings. Cleaned orders are
  cached by the file hash, so changing the lead time doesn't re-clean.
- The frontend fetches once, has no chart library, and ships 76 KB of gzipped JS.

---

## API

| Method | Path | What it does |
|---|---|---|
| `POST` | `/api/analyses` | multipart: `sales_file` (.csv/.xlsx, ≤100 MB), optional `stock_file`, `lead_time_weeks` (0–8), `coverage_weeks` (1–8). Returns every result in one response, plus an `id`. |
| `POST` | `/api/analyses/demo` | Same, on the bundled dataset. `use_sample_stock=true` adds the SAMPLE stock file. |
| `GET` | `/api/analyses/{id}` | The full cached result. |
| `GET` | `/api/analyses/{id}/{section}` | One part: `promote`, `dying`, `bundles`, `forecast`, `restock`, `backtest`, `data`, `timings_seconds`. |
| `GET` | `/api/analyses/{id}/summary` | Gemini summary, generated on first request and cached. Returns `available: false` with a message if there's no key. |
| `GET` | `/api/health` | Status, and whether the AI summary is configured. |

Errors are plain messages: `400` for a bad or unreadable file or missing columns, `413` for
a file over the size limit, `422` for invalid settings, `404` for an unknown id.

---

## Deployment

The backend and frontend deploy separately.

**Backend** (any Python host, e.g. Render, Railway, Fly.io):

1. Root directory: `backend`.
2. Build command:
   `pip install -r requirements.txt && python -m scripts.download_data && python -m scripts.prepare_data`.
   This is only needed for the demo dataset.
3. Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`.
4. Environment variables: `GEMINI_API_KEY` (optional), `CORS_ORIGINS=https://your-frontend-url`,
   `MAX_UPLOAD_MB` (lower it on small instances).
5. Memory: parsing a 1M-row Excel file needs about 1 GB of RAM. On a 512 MB free tier, use
   CSV uploads or a lower `MAX_UPLOAD_MB`. The cache lives in memory, so it resets when the
   server restarts. Use Redis if you run several instances.

**Frontend** (any static host, e.g. Netlify, Vercel, Cloudflare Pages):

1. Root directory: `frontend`, build command `npm run build`, output folder `dist`.
2. Environment variable: `VITE_API_URL=https://your-backend-url`.

Never commit `.env` files or API keys. Set them in the host's dashboard instead.

---

## Data licence

UCI Online Retail II, by Daqing Chen, is licensed under CC BY 4.0. The raw file is downloaded
by `scripts/download_data.py` and is not stored in this repository.
