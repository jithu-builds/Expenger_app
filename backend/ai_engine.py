"""
Groq AI engine — llama-3.3-70b-versatile & llama-3.1-8b-instant (groq SDK)

Three responsibilities:
  1. extract_transactions_from_markdown() — bank statement → JSON transactions
  2. generate_spending_insights()         — spending analysis, predictions, recommendations
  3. answer_finance_question()            — follow-up chat
"""

import json
import os
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, date

from groq import Groq, RateLimitError
from dotenv import load_dotenv

load_dotenv()


def _secret(key: str) -> str:
    """Read from st.secrets (Streamlit Cloud) or fall back to os.getenv (.env)."""
    try:
        import streamlit as st
        return st.secrets.get(key) or os.getenv(key, "")
    except Exception:
        return os.getenv(key, "")


GROQ_API_KEY: str = _secret("GROQ_API_KEY")
_MODEL_VERSATILE = "llama-3.3-70b-versatile"
_MODEL_FAST = "llama-3.1-8b-instant"

_groq_client = None

VALID_CATEGORIES = [
    "Food & Dining", "Transport", "Shopping", "Entertainment",
    "Utilities", "Rent & Housing", "Healthcare", "Income",
    "Transfer", "Subscriptions", "Other",
]


def _get_client():
    global _groq_client
    if _groq_client is None:
        if not GROQ_API_KEY:
            raise EnvironmentError("GROQ_API_KEY is not set in your .env file.")
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def _is_transient_error(exc: Exception) -> bool:
    msg = str(exc)
    return "503" in msg or "UNAVAILABLE" in msg or "502" in msg or "timeout" in msg.lower()


def _generate(prompt: str, model_name: str = _MODEL_VERSATILE, temperature: float = 0.3, max_retries: int = 3) -> str:
    client = _get_client()
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            content = response.choices[0].message.content
            return unicodedata.normalize('NFKC', content)
        except Exception as exc:
            last_exc = exc
            if _is_transient_error(exc) and attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 1s, then 2s before retrying
                continue
            raise
    raise last_exc


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _is_quota_error(exc: Exception) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    msg = str(exc)
    return "429" in msg or "quota" in msg.lower() or "rate" in msg.lower() or "RESOURCE_EXHAUSTED" in msg


# ─── 1. Transaction Extraction ────────────────────────────────────────────────

def _sanitize_date(date_str: str) -> str | None:
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    
    # 1. Try standard ISO-like formats first
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%m-%d-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
            
    # 2. Try parsing with month names (e.g. "13 Jun 2026", "June 13, 2026")
    for fmt in ("%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%Y-%b-%d", "%Y-%B-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    # 3. Custom digit-based parser to correct swapped month/day (e.g. "2026-13-03")
    try:
        parts = re.split(r'[-/.]', date_str)
        if len(parts) != 3:
            nums = re.findall(r'\d+', date_str)
            if len(nums) == 3:
                parts = nums
            else:
                return None
                
        year = None
        other_parts = []
        for p in parts:
            if len(p) == 4 and p.isdigit():
                year = int(p)
            elif p.isdigit():
                other_parts.append(int(p))
                
        if year is None:
            # If no 4-digit year, try to guess from 2-digit years
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                p0, p1, p2 = int(parts[0]), int(parts[1]), int(parts[2])
                if p2 >= 0 and p2 <= 99:
                    year = 2000 + p2
                    other_parts = [p0, p1]
                elif p0 >= 0 and p0 <= 99:
                    year = 2000 + p0
                    other_parts = [p1, p2]
                else:
                    return None
            else:
                return None
                
        if len(other_parts) != 2:
            return None
            
        val1, val2 = other_parts[0], other_parts[1]
        year_first = (parts[0].isdigit() and int(parts[0]) == year)
        
        # Swapping logic for invalid month values
        if val1 > 12 and val2 <= 12:
            day, month = val1, val2
        elif val2 > 12 and val1 <= 12:
            day, month = val2, val1
        elif val1 <= 12 and val2 <= 12:
            if year_first:
                month, day = val1, val2
            else:
                day, month = val1, val2
        else:
            return None
            
        d = datetime(year, month, day)
        return d.strftime("%Y-%m-%d")
    except Exception:
        return None


def _extract_chunk(markdown_text: str) -> list[dict]:
    cats = ", ".join(VALID_CATEGORIES)
    prompt = f"""You are a financial data extraction assistant.

Extract EVERY transaction from the bank statement below.

CRITICAL DATE PARSING RULE:
1. Scan the entire statement first to deduce the date format (usually DD/MM/YYYY or MM/DD/YYYY).
2. Look for separator patterns and numbers > 12 (e.g. "13/03/2026", "23-03-2026") to identify whether the day is first or the month is first.
3. Apply this format CONSISTENTLY to all transactions in the document.
   - For example: if you find "13/03/2026" (March 13) and "03/04/2026", then "03/04/2026" MUST be March 4 (2026-03-04), NOT April 3 (2026-04-03).
   - If the day and month are ambiguous because all values are <= 12, check other transactions in the statement to determine the layout format.

Output fields per transaction:
  - "date"        : YYYY-MM-DD (strictly based on the deduced format)
  - "description" : merchant/payee, clean, max 60 chars
  - "amount"      : numeric; NEGATIVE = debit/expense, POSITIVE = credit/income
  - "category"    : one of: {cats}

RULES: Output ONLY a valid JSON array. No markdown, no explanation, no code fences.

Bank statement:
─────────────────
{markdown_text}
─────────────────
JSON array:"""

    try:
        raw = _generate(prompt, model_name=_MODEL_FAST, temperature=0.1)
    except Exception as exc:
        raise RuntimeError(f"Groq API call failed: {exc}") from exc

    cleaned = _strip_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Groq returned invalid JSON.\nError: {exc}\nRaw (500 chars): {cleaned[:500]}"
        ) from exc

    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data).__name__}.")

    for t in data:
        t["date"] = _sanitize_date(t.get("date"))
        try:
            t["amount"] = float(t.get("amount") or 0)
        except (TypeError, ValueError):
            t["amount"] = 0.0

    return data



def extract_transactions_from_markdown(markdown_text: str) -> list[dict]:
    # Set chunk size to 16,000 characters (approx 4,000 tokens)
    # This is safe for both Groq's TPM limits and context windows
    max_chunk_chars = 16000
    
    if len(markdown_text) <= max_chunk_chars:
        return _extract_chunk(markdown_text)
    
    # Split text into line-based chunks
    chunks = []
    current_chunk = []
    current_len = 0
    for line in markdown_text.splitlines():
        line_len = len(line) + 1
        if current_len + line_len > max_chunk_chars:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_len = line_len
        else:
            current_chunk.append(line)
            current_len += line_len
    if current_chunk:
        chunks.append("\n".join(current_chunk))
        
    all_transactions = []
    for i, chunk in enumerate(chunks):
        txns = _extract_chunk(chunk)
        all_transactions.extend(txns)
        # Sleep briefly between chunks to avoid hitting the rate limit window
        if i < len(chunks) - 1:
            time.sleep(1.5)
            
    return all_transactions


# ─── 2. Spending Insights ─────────────────────────────────────────────────────

def generate_spending_insights(transactions: list[dict], budgets: list[dict]) -> dict:
    import pandas as pd

    if not transactions:
        return {
            "summary": "No transactions found. Upload a bank statement to get insights.",
            "health_score": 0,
            "alerts": [],
            "predictions": [],
            "recommendations": [],
        }

    df = pd.DataFrame(transactions)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    expenses = df[df["amount"] < 0].copy()
    expenses["amount_abs"] = expenses["amount"].abs()

    today = datetime.now()
    days_elapsed = today.day
    days_in_month = 30

    try:
        expenses["date"] = pd.to_datetime(expenses["date"], errors="coerce")
        current_month_exp = expenses[
            (expenses["date"].dt.month == today.month) &
            (expenses["date"].dt.year == today.year)
        ]
    except Exception:
        current_month_exp = expenses

    cat_actual = (
        current_month_exp.groupby("category")["amount_abs"].sum().to_dict()
        if not current_month_exp.empty
        else expenses.groupby("category")["amount_abs"].sum().to_dict()
    )

    cat_alltime = expenses.groupby("category")["amount_abs"].sum().to_dict()
    budget_map = {b["category"]: float(b["monthly_limit"]) for b in budgets}

    recent_txns = (
        df.sort_values("date", ascending=False)
        .head(20)[["date", "description", "amount", "category"]]
        .to_string(index=False)
    )

    desc_counts = expenses["description"].value_counts().head(10).to_dict()
    recurring = [f"{k} (×{v})" for k, v in desc_counts.items()]

    budget_lines = "\n".join(
        f"  {cat}: spent ${cat_actual.get(cat, 0):.2f} / budget ${lim:.2f}"
        for cat, lim in budget_map.items()
    ) if budget_map else "  No budgets set yet."

    context = f"""
Today: {today.strftime('%B %d, %Y')} (day {days_elapsed} of {days_in_month})
Total transactions: {len(transactions)}
Total expenses (all time): ${sum(cat_alltime.values()):.2f}

This month — Actual vs Budget:
{budget_lines}

Recurring merchants (all time):
  {', '.join(recurring) if recurring else 'None detected'}

Last 20 transactions:
{recent_txns}
"""

    prompt = f"""You are a personal finance AI that gives sharp, specific insights.

Analyse the spending data below and return a JSON object with EXACTLY these keys:

{{
  "summary": "<2-3 sentence plain-English summary of spending health>",
  "health_score": <integer 0-100; 100=perfectly on budget, 0=severely over>,
  "alerts": [
    {{
      "category": "<category name>",
      "message": "<specific alert, e.g. '85% of budget used with 12 days left'>",
      "severity": "high|medium|low"
    }}
  ],
  "predictions": [
    {{
      "category": "<category>",
      "spent_so_far": <number>,
      "predicted_monthly_total": <number>,
      "budget": <number or null>,
      "will_exceed": <true|false>,
      "reason": "<short reason for prediction>"
    }}
  ],
  "recommendations": [
    {{
      "title": "<specific actionable title, e.g. 'Skip the cinema this weekend'>",
      "detail": "<1-2 sentences with specific context from their actual transactions>",
      "estimated_savings": <number>,
      "category": "<category>"
    }}
  ]
}}

RULES:
- Be SPECIFIC — reference actual merchants, amounts, and patterns from the data.
- Recommendations must be concrete (e.g. "You visited Starbucks 8 times this month — switching to home coffee saves ~$32").
- If no budgets are set, still generate predictions and recommendations from spending patterns alone.
- Output ONLY the JSON object. No markdown, no explanation.

Spending data:
{context}

JSON:"""

    try:
        raw = _generate(prompt, model_name=_MODEL_VERSATILE, temperature=0.4)
    except Exception as exc:
        if _is_quota_error(exc):
            return {
                "summary": (
                    "⚠️ AI insights are temporarily unavailable — your free Groq API quota "
                    "has been reached. Insights will work again once the quota resets. "
                    "Your transaction data is safe and fully visible in the Dashboard."
                ),
                "health_score": -1,
                "alerts": [],
                "predictions": [],
                "recommendations": [],
                "_rate_limited": True,
            }
        raise RuntimeError(f"Groq insights call failed: {exc}") from exc

    cleaned = _strip_fences(raw)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "summary": raw[:300],
            "health_score": 50,
            "alerts": [],
            "predictions": [],
            "recommendations": [],
        }

    return result


# ─── 3. Budget Suggestions ────────────────────────────────────────────────────

def suggest_budgets(transactions: list[dict]) -> list[dict]:
    import pandas as pd

    if not transactions:
        return []

    df = pd.DataFrame(transactions)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    expenses = df[df["amount"] < 0].copy()
    expenses["amount_abs"] = expenses["amount"].abs()

    cat_avg = expenses.groupby("category")["amount_abs"].sum()

    try:
        expenses["date"] = pd.to_datetime(expenses["date"], errors="coerce")
        unique_months = expenses["date"].dt.to_period("M").nunique()
        months = max(1, unique_months)
    except Exception:
        months = 1

    monthly_avgs = (cat_avg / months).round(2).to_dict()
    avg_lines = "\n".join(f"  {cat}: ${amt:.2f}/month avg" for cat, amt in monthly_avgs.items())

    prompt = f"""Based on this user's average monthly spending by category, suggest realistic monthly budget limits.

Average monthly spending:
{avg_lines}

Return a JSON array:
[
  {{
    "category": "<category>",
    "suggested_limit": <number — slightly above average to be realistic but encourage saving>,
    "reasoning": "<one sentence explaining the suggestion>"
  }}
]

Output ONLY the JSON array. No markdown or explanation."""

    try:
        raw = _generate(prompt, model_name=_MODEL_VERSATILE, temperature=0.2)
        data = json.loads(_strip_fences(raw))
        return data if isinstance(data, list) else []
    except Exception:
        return []


# ─── 4. Follow-up Chat ────────────────────────────────────────────────────────

def answer_finance_question(
    question: str,
    transactions: list[dict],
    chat_history: list[dict] | None = None,
) -> str:
    import pandas as pd

    if not transactions:
        return "No transactions found yet. Upload a bank statement from the Dashboard first."

    df = pd.DataFrame(transactions)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # 1. All-time stats
    all_time_spent  = df[df["amount"] < 0]["amount"].sum()
    all_time_income = df[df["amount"] > 0]["amount"].sum()
    all_time_cat_totals = (
        df[df["amount"] < 0].groupby("category")["amount"].sum().abs()
        .sort_values(ascending=False).to_dict()
    )
    all_time_cat_lines = "\n".join(f"  • {c}: ${a:,.2f}" for c, a in all_time_cat_totals.items())

    # 2. Current Month stats (based on current system time)
    from datetime import datetime
    today = datetime.now()
    current_month_df = df[
        (df["date"].dt.month == today.month) &
        (df["date"].dt.year == today.year)
    ]
    
    current_month_spent = current_month_df[current_month_df["amount"] < 0]["amount"].sum()
    current_month_income = current_month_df[current_month_df["amount"] > 0]["amount"].sum()
    current_month_cat_totals = (
        current_month_df[current_month_df["amount"] < 0].groupby("category")["amount"].sum().abs()
        .sort_values(ascending=False).to_dict()
    )
    current_month_cat_lines = "\n".join(f"  • {c}: ${a:,.2f}" for c, a in current_month_cat_totals.items())

    # 3. Recent 15 transactions
    recent_df = df.sort_values("date", ascending=False).head(15).copy()
    recent_df["date_str"] = recent_df["date"].dt.strftime("%Y-%m-%d")
    recent = recent_df[["date_str", "description", "amount", "category"]].to_string(index=False)

    system_prompt = f"""You are a concise personal finance advisor.
Always write in standard English plain text with standard spacing. Never use mathematical italic Unicode symbols (like 𝑎, 𝑏, 𝑐) for formatting or emphasis. Use standard alphanumeric characters and Markdown.

Current Time: {today.strftime('%B %d, %Y')}

=== CURRENT MONTH SUMMARY ({today.strftime('%B %Y')}) ===
  Total Income   : ${current_month_income:,.2f}
  Total Expenses : ${abs(current_month_spent):,.2f}
  Net Savings    : ${(current_month_income + current_month_spent):,.2f}

By Category (Current Month):
{current_month_cat_lines if current_month_cat_lines else "  No expenses this month."}

=== ALL-TIME SUMMARY ===
  Total Transactions : {len(transactions)}
  Total Income       : ${all_time_income:,.2f}
  Total Expenses     : ${abs(all_time_spent):,.2f}
  Net                : ${(all_time_income + all_time_spent):,.2f}

By Category (All-time):
{all_time_cat_lines if all_time_cat_lines else "  No expenses recorded."}

=== RECENT 15 TRANSACTIONS ===
{recent}"""

    # Build standard messages list for chat models
    messages = [{"role": "system", "content": system_prompt}]

    if chat_history:
        # Append last 6 turns (representing 3 exchanges)
        for msg in chat_history[-6:]:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})

    messages.append({"role": "user", "content": question})

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=_MODEL_VERSATILE,
            messages=messages,
            temperature=0.7,
        )
        content = response.choices[0].message.content
        return unicodedata.normalize('NFKC', content).strip()
    except Exception as exc:
        if _is_quota_error(exc):
            return (
                "⚠️ I'm temporarily unavailable — the free Groq API quota has been reached. "
                "Please try again in a moment. Your transaction data is still fully visible in the Dashboard."
            )
        raise RuntimeError(f"Groq API call failed: {exc}") from exc
