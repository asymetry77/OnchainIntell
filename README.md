# ONCHAIN NEVER LIES
### Accountability Journalism Pipeline — Dokumentasi Lengkap

---

## SETUP

```bash
# 1. Clone / extract project
unzip onchain-never-lies.zip
cd onchain-never-lies

# 2. Install dependencies
pip install -r requirements.txt

# 3. Isi API keys
cp .env.example .env
nano .env   # isi ARKHAM_API_KEY dan MIMO_API_KEY

# 4. Test koneksi
python main.py token trending
```

---

## STRUKTUR PROJECT

```
onchain-never-lies/
│
├── config/
│   ├── settings.py          → API keys, thresholds, scoring weights
│   └── entities.py          → Semua entity slugs, CEX list, token list
│
├── core/
│   ├── arkham_client.py     → Wrapper semua Arkham API endpoint
│   └── mimo_client.py       → MiMo AI client untuk format caption
│
├── scanners/
│   ├── daily_scanner.py     → Orchestrator 5-step daily scan (bearish)
│   └── bullish_scanner.py   → Orchestrator 3-step bullish scan
│
├── detectors/               → BEARISH signals
│   ├── insider_dump.py      → Type 1: Team wallet dump ke exchange
│   ├── pre_dump_warning.py  → Type 2: Labeled wallet masuk exchange
│   ├── silent_accumulation.py → Type 4: 3+ wallet beli bertahap
│   │
│   │                        → BULLISH signals (baru)
│   ├── exchange_outflow_surge.py → Type 5: Token keluar massal dari CEX
│   ├── whale_buy.py         → Type 6: Single whale/VC beli besar
│   └── dex_accumulation.py  → Type 7: VC swap di DEX (conviction buy)
│
├── investigators/
│   └── investigation_engine.py → 9-step deep investigation workflow
│
├── formatters/
│   └── caption_generator.py → MiMo prompts untuk semua 7 content types
│
├── utils/
│   └── helpers.py           → Timestamp, USD format, evidence scoring
│
├── reports/                 ← OUTPUT: semua JSON report tersimpan di sini
├── logs/                    ← OUTPUT: log file harian
│
└── main.py                  → CLI entry point
```

---

## OUTPUT — KEMANA HASILNYA?

### 1. Terminal (Real-time)
Setiap command menampilkan hasil langsung di terminal dengan format tabel Rich:
```
python main.py scan
→ Tabel flag + panel "TOP PRIORITY"

python main.py bullish-scan
→ Tabel semua bullish signals + top signal

python main.py detect-dump --slug some-project
→ Panel detected/not detected + evidence score
```

### 2. File JSON di `/reports/`
Setiap scan & investigasi otomatis menyimpan report ke folder `reports/`:

```
reports/
├── daily_scan_20240115_093045.json       ← dari: python main.py scan
├── 20240115_094122_insider_dump_a16z.json   ← dari: investigate
├── 20240115_100033_whale_buy_pepe.json      ← dari: investigate
└── ...
```

Format JSON report `investigate`:
```json
{
  "target_slug": "some-project",
  "event_type": "insider_dump",
  "evidence_score": 82,
  "ready_to_post": true,
  "entity_profile": { ... },
  "portfolio_timeline": {
    "delta_30d_usd": -2400000,
    "delta_30d_pct": -67.3
  },
  "exchange_activity": {
    "binance": { "count": 3, "total_usd": 1800000 },
    "coinbase": { "count": 1, "total_usd": 600000 }
  },
  "evidence_package": {
    "entity": "Project Name",
    "token": "TOKEN",
    "amount_usd": 2400000,
    "tx_hashes": ["0x...", "0x..."],
    ...
  },
  "mimo_output": {
    "hook_line": "🚨 PROJECT NAME INSIDER DUMP DETECTED",
    "thread": [
      "tweet 1 teks...",
      "tweet 2 teks...",
      "tweet 3 teks...",
      "tweet 4 teks..."
    ],
    "verifiable_facts": ["Fact + tx hash 1", "Fact + tx hash 2"],
    "disclaimer": "DYOR. Bukan financial advice."
  },
  "review_checklist": [
    "□ All TX hashes verified on blockchain explorer",
    "□ Wallet attribution confirmed via Arkham label",
    ...
  ]
}
```

### 3. Log File di `/logs/`
Log harian otomatis tersimpan:
```
logs/
└── onchain_20240115.log    ← semua INFO/WARNING/ERROR dari hari itu
```

---

## SEMUA COMMAND

### SCANNING (Daily Routine)
```bash
# Jalankan full daily scan (bearish — 5 steps)
python main.py scan

# Jalankan full bullish scan (outflow + whale buy + dex)
python main.py bullish-scan

# Bullish scan untuk token spesifik
python main.py bullish-scan --tokens bitcoin,ethereum,pepe

# Bullish scan + monitor wallet tertentu
python main.py bullish-scan --wallets 0x1234...,0x5678...
```

### DETECTORS — BEARISH
```bash
# Type 1: Insider dump (team wallet keluar ke exchange)
python main.py detect-dump --slug project-slug
python main.py detect-dump --slug project-slug --time-last 30d
python main.py detect-dump --slug project-slug --threshold 50000

# Type 2: Pre-dump warning (labeled wallet masuk exchange)
python main.py detect-warning --token pepe
python main.py detect-warning --token pepe --exchange coinbase --hours 12

# Type 4: Silent accumulation (3+ wallet beli bertahap)
python main.py detect-accumulation --token bitcoin
python main.py detect-accumulation --token ethereum --time-last 30d --min-buyers 5
```

### DETECTORS — BULLISH
```bash
# Type 5: Exchange outflow surge (token keluar dari CEX massal)
python main.py detect-outflow --token bitcoin
python main.py detect-outflow --token ethereum --time-last 30d

# Type 6: Whale buy (single large named wallet entry)
python main.py detect-whale-buy --token pepe
python main.py detect-whale-buy --token arbitrum --hours 48 --min-usd 1000000

# Type 7: DEX accumulation (VC / smart money swap di DEX)
python main.py detect-dex                        # scan semua VC
python main.py detect-dex --entity a16z          # scan VC tertentu
python main.py detect-dex --entity paradigm-xyz --chain ethereum
```

### INVESTIGATION
```bash
# Full 9-step investigation dari entity slug
python main.py investigate --slug project-slug --type insider_dump
python main.py investigate --slug a16z --type silent_accumulation --name "a16z"

# Catch the lie — butuh klaim publik yang akan di-fact-check
python main.py investigate \
  --slug project-slug \
  --type catch_the_lie \
  --claim "Kami tidak akan jual token selama 1 tahun" \
  --claim-date 2024-01-01
```

### CAPTION GENERATION
```bash
# Generate X thread dari report yang sudah disimpan
python main.py caption --report reports/20240115_094122_insider_dump_project.json
```

### LOOKUP TOOLS
```bash
# Lookup wallet address
python main.py wallet 0x1234567890abcdef...

# Entity profile + recent transfers
python main.py entity a16z
python main.py entity binance --transfers

# Token tools
python main.py token trending
python main.py token top --order-by outflow --timeframe 24h
python main.py token top --order-by inflow --timeframe 7d
python main.py token holders --slug pepe
python main.py token flow --slug bitcoin --timeframe 24h
python main.py token search --query "pendle"
```

---

## FULL PIPELINE — TYPICAL WORKFLOW

### WORKFLOW HARIAN (30-45 menit)

```
PAGI:
  1. python main.py scan              → lihat flag bearish
  2. python main.py bullish-scan      → lihat flag bullish

JIKA ADA FLAG MENARIK:
  3. python main.py investigate \
       --slug [target] \
       --type [event_type]
     → Report JSON tersimpan di reports/

  4. Buka report JSON → cek mimo_output.thread
  5. Verify semua tx_hashes di Etherscan / blockchain explorer
  6. Cek review_checklist di report
  7. Jika ready_to_post: true → post ke X
```

### WORKFLOW INVESTIGASI MENDALAM

```
  1. Temukan target dari daily scan
  2. python main.py entity [slug]          → profile lengkap
  3. python main.py wallet [address]       → cek wallet spesifik
  4. python main.py investigate --slug ... → full 9-step
  5. Buka reports/[timestamp]_[type]_[entity].json
  6. Copy mimo_output.thread ke X (setelah manual review)
```

---

## SIGNAL TYPES — REFERENSI CEPAT

| Type | Command | Signal | Trigger Emosi |
|---|---|---|---|
| 1 | `detect-dump` | Team wallet → Exchange | MARAH (anger) |
| 2 | `detect-warning` | Labeled wallet → Exchange (< 6 jam) | TAKUT (fear) |
| 3 | `investigate --type catch_the_lie` | Klaim publik vs data | OUTRAGE |
| 4 | `detect-accumulation` | 3+ wallet beli bertahap | FOMO |
| 5 | `detect-outflow` | Token keluar massal dari CEX | FOMO (bullish) |
| 6 | `detect-whale-buy` | Single VC/whale beli besar | FOMO + trust |
| 7 | `detect-dex` | VC swap berulang di DEX | FOMO (conviction) |

---

## EVIDENCE SCORE — CARA BACA

Score 0–100 menentukan kekuatan evidence sebelum posting.

| Score | Status | Aksi |
|---|---|---|
| 85–100 | ✅ Strong — ready to post | Post setelah manual review |
| 60–84  | ⚠️ Medium — butuh lebih | Cari corroborating data dulu |
| < 60   | ❌ Weak — jangan post | Kumpulkan lebih banyak evidence |

**Faktor yang menaikkan score:**
- Wallet terkonfirmasi berlabel di Arkham (+30)
- Transfer > $100K (+15) atau > $1M (+10)
- Destination adalah CEX (+20)
- Terjadi dalam 24 jam terakhir (+10)
- Ada volume spike di histogram (+10)
- 3+ transaksi dengan pola sama (+5)

---

## LEGAL & ETHICAL REMINDERS

```
✅ AMAN:
  "Wallet berlabel [ENTITY] transfer $2M ke Binance [TX HASH]"
  Selalu sertakan tx hash untuk verifikasi mandiri
  Bedakan DATA vs INTERPRETASI dengan jelas

❌ HINDARI:
  "Project X adalah SCAM" — tanpa evidence chain yang sangat kuat
  Atribusi wallet ke orang tanpa konfirmasi Arkham
  "HARGA PASTI DUMP/PUMP" — onchain adalah signal, bukan oracle
  Post tanpa manual review checklist
```

---

*"Onchain data tidak bisa dipalsukan. Itu adalah moat yang sesungguhnya."*
