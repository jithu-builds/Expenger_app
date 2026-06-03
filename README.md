# 💡 Expenger — AI Personal Finance Tracker

Expenger is an AI-powered personal finance tracker that reads your bank statements, categorises your spending, tracks your budgets, and gives you intelligent insights — all in one place.

---

## What It Does

| Feature | Description |
|---|---|
| **PDF Import** | Upload your bank statement PDF and Expenger extracts every transaction automatically |
| **AI Categorisation** | Expenger AI reads the transactions and assigns categories like Food, Transport, Shopping |
| **Dashboard** | Visual breakdown of your spending with pie charts, bar charts, and monthly trends |
| **Budget Tracker** | Set monthly limits per category and see how your actual spending compares |
| **AI Budget Suggestions** | Expenger AI analyses your history and suggests realistic budget limits for you |
| **AI Insights** | Get a spending health score, end-of-month predictions, and specific recommendations like "Skip the cinema this weekend — you've already spent $45 on entertainment" |
| **Secure Auth** | Login and signup powered by Supabase — your data is isolated to your account only |

---

## Tech Stack

- **Frontend** — [Streamlit](https://streamlit.io)
- **Database & Auth** — [Supabase](https://supabase.com)
- **PDF Parsing** — [Reducto API](https://reducto.ai)
- **AI** — [Groq](https://groq.com) (branded as Expenger AI)
- **Language** — Python 3.9+

---

## Project Structure

```
├── app.py                        # Main entry point and page router
├── requirements.txt              # Python dependencies
├── .env                          # API keys (never commit this)
│
├── components/
│   ├── auth.py                   # Login / Signup UI and session management
│   └── session_store.py          # Shared cookie manager instance
│
├── frontend/
│   ├── dashboard.py              # PDF upload, charts, transaction table
│   ├── budgeting.py              # Budget vs actual spending tracker
│   └── chat_ai.py                # AI Insights page
│
├── backend/
│   ├── supabase_client.py        # All database and auth queries
│   ├── document_parser.py        # Reducto API — PDF to Markdown
│   └── ai_engine.py              # Groq — transaction extraction and insights
│
└── .streamlit/
    └── config.toml               # App theme configuration
```

---

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/your-username/Personal_finance_app.git
cd Personal_finance_app
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up your API keys

Fill in the `.env` file in the project root:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
GROQ_API_KEY=your-groq-api-key
REDUCTO_API_KEY=your-reducto-api-key
```

| Key | Where to get it |
|---|---|
| `SUPABASE_URL` / `SUPABASE_KEY` | [supabase.com](https://supabase.com) → your project → Settings → API |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com/keys) → Get API Key |
| `REDUCTO_API_KEY` | [reducto.ai](https://reducto.ai) → Dashboard |

### 4. Set up the Supabase database

Go to your **Supabase project → SQL Editor** and run the following scripts in order.

#### 4a. Create tables

```sql
-- Transactions table
CREATE TABLE IF NOT EXISTS public.transactions (
    id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID          NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    date        DATE,
    description TEXT,
    amount      NUMERIC(12, 2),
    category    TEXT,
    source_file TEXT,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- Budgets table
CREATE TABLE IF NOT EXISTS public.budgets (
    id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID          NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    category      TEXT          NOT NULL,
    monthly_limit NUMERIC(12, 2) NOT NULL,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, category)
);
```

#### 4b. Add deduplication constraint

```sql
-- Prevents the same transaction being imported twice from the same statement
ALTER TABLE public.transactions
    ADD CONSTRAINT uq_transaction
    UNIQUE (user_id, date, description, amount);
```

#### 4c. Enable Row Level Security

```sql
-- Enable RLS so users can only access their own rows
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.budgets      ENABLE ROW LEVEL SECURITY;

-- Transactions policy
CREATE POLICY "transactions: owner access"
    ON public.transactions
    FOR ALL
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Budgets policy
CREATE POLICY "budgets: owner access"
    ON public.budgets
    FOR ALL
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
```

> **Note:** `gen_random_uuid()` is available in PostgreSQL 13+ (all Supabase projects). If you're on an older project still using `uuid-ossp`, replace `gen_random_uuid()` with `uuid_generate_v4()`.

### 5. Run the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## How to Use

1. **Sign up** with your email and password
2. Go to **Dashboard** and upload a PDF bank statement
3. Expenger will extract and categorise all transactions automatically
4. Go to **Budgeting** → click **Get AI Budget Suggestions** to set limits
5. Go to **AI Insights** to see your spending health score, predictions, and recommendations

---

## Notes

- Your session stays active across browser refreshes (stored in cookies)
- Uploading the same PDF twice is safe — duplicate transactions are blocked at the database level
- Row Level Security (RLS) is enabled — users can only ever see their own data
- The PDF must contain selectable text (not a scanned image) for Reducto to extract it
