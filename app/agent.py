
"""LLM only decides WHAT to look up (SQL or a named ratio).
Python performs all arithmetic.
"""

import json
import re
import time

from google import genai
from google.genai import types

from app.db import record_llm_usage
from app.ratios import RATIOS
from app.retrieval import retrieve_document_chunks
from app.service import ratio_series
from app.sqlguard import UnsafeSQL, run_readonly

REQUEST_TIMEOUT_MS = 30000
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1


SYSTEM = f"""You help a bank credit analyst query a database of textile-company annual report facts.

Database table:
facts(company, fiscal_year, basis, metric, value, unit, source_file,
      page_no, extraction_method, needs_review).

Rules:
- Only use facts where needs_review = 0.
- Always include source_file, page_no, and unit in SQL results.
- Units may be INR_lakhs, INR_crore, INR_thousands, INR, or UNKNOWN.
- Never assume all values are INR crore.
- Never perform arithmetic. Python calculates all named ratios.
- Available metrics: revenue, net_profit, pbt, finance_cost,
  depreciation, borrowings_lt, borrowings_st, equity, materials_cost.
- Company names:
  kpr_mill, lakshmi_machine_works, rajapalayam_mills,
  ambika_cotton_mills, precot.
- The fiscal_year column stores integer values such as 2024, 2025, 2026.
- Never use labels like 'FY2024' in SQL filters.
- Use 2024, 2025, 2026 instead.
Document question rules:
- For qualitative questions about annual report content, return {{"documents": true}}.
- Use document retrieval for management discussion, company strategy,
  risks, operations, governance, business overview and similar topics.
- Use SQL for questions asking for structured financial facts.
- Use ratio for named financial ratio questions.
- Do not use SQL for document questions.

Return exactly ONE JSON object without Markdown or explanation.

Allowed response formats:

{{"sql": "SELECT ..."}}

{{"documents": true}}

{{"ratio": "<name>", "companies": ["company_name"]}}

{{"unanswerable": "<reason>"}}

SQL rules:
- Only one read-only SELECT statement.
- Query only the facts table.
- Include source_file, page_no, and unit in the SELECT list.
- Include needs_review = 0 in the WHERE clause.
- Never use INSERT, UPDATE, DELETE, DROP, or PRAGMA.
- Never calculate ratios in SQL.

For ratio requests, use only these available names:
{sorted(RATIOS)}
"""


def _is_retryable(exc: Exception) -> bool:
    """Check whether an error may be temporary."""

    status = (
        getattr(exc, "status_code", None)
        or getattr(exc, "code", None)
    )

    if status is not None:
        try:
            if int(status) in (408, 429, 500, 502, 503, 504):
                return True
        except (TypeError, ValueError):
            pass

    return isinstance(
        exc,
        (TimeoutError, ConnectionError, OSError),
    ) or any(
        word in type(exc).__name__.lower()
        for word in ("timeout", "connection", "transport")
    )


def _generate_plan(client, question: str, model: str) -> dict:
    """Generate a plan and capture token usage from Gemini."""

    stream = client.models.generate_content_stream(
        model=model,
        contents=(
            SYSTEM
            + "\n\nAnalyst question:\n"
            + question
            + "\n\nReturn only one JSON object."
        ),
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )

    content = ""
    usage_metadata = None

    for chunk in stream:
        if chunk.text:
            content += chunk.text

        # The final streaming chunk may contain usage metadata.
        if getattr(chunk, "usage_metadata", None) is not None:
            usage_metadata = chunk.usage_metadata

    if not content.strip():
        raise ValueError("Gemini returned an empty response.")

    cleaned = content.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)

    if not match:
        raise ValueError(
            f"Gemini returned no JSON object: {content[:1000]}"
        )

    try:
        plan = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini returned invalid JSON: {exc}"
        ) from exc

    if not isinstance(plan, dict):
        raise ValueError("Gemini plan must be a JSON object.")

    usage = None

    if usage_metadata is not None:
        input_tokens = getattr(
            usage_metadata, "prompt_token_count", None
        )
        output_tokens = getattr(
            usage_metadata, "candidates_token_count", None
        )
        total_tokens = getattr(
            usage_metadata, "total_token_count", None
        )

        if (
            input_tokens is not None
            or output_tokens is not None
            or total_tokens is not None
        ):
            usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            }

    return {
        "_plan": plan,
        "_usage": usage,
        "_model": model,
    }


def _llm(
    question: str,
    api_key: str,
    model: str,
    fallback_model: str | None = None,
) -> dict:
    """Generate a plan with retries and fallback model."""

    if not api_key or not api_key.strip():
        raise ValueError(
            "GEMINI_API_KEY is empty. Add your Gemini API key to .env."
        )

    if not model or not model.strip():
        raise ValueError("LLM_MODEL is empty. Set it in .env.")

    try:
        client = genai.Client(
            api_key=api_key.strip(),
            http_options=types.HttpOptions(
                timeout=REQUEST_TIMEOUT_MS,
            ),
        )
    except Exception as exc:
        raise ValueError(
            f"Could not initialize Gemini client: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    models = [model.strip()]

    if fallback_model and fallback_model.strip():
        fallback = fallback_model.strip()

        if fallback not in models:
            models.append(fallback)

    errors = []

    for selected_model in models:
        for attempt in range(MAX_RETRIES):
            try:
                return _generate_plan(
                    client,
                    question,
                    selected_model,
                )

            except Exception as exc:
                errors.append(
                    f"{selected_model}, attempt {attempt + 1}: "
                    f"{type(exc).__name__}: {exc}"
                )

                if not _is_retryable(exc):
                    break

                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY_SECONDS * (2 ** attempt)
                    time.sleep(delay)

    raise RuntimeError(
        "All Gemini model attempts failed: "
        + " | ".join(errors)
    )


def answer(
    question: str,
    db_path: str,
    api_key: str,
    model: str,
    llm=_llm,
    fallback_model: str | None = None,
    input_price_per_million: float | None = None,
    output_price_per_million: float | None = None,
) -> dict:
    """Generate a plan, record LLM usage, and execute it safely."""

    if not question or not question.strip():
        return {"error": "Question cannot be empty."}

    if not api_key and llm is _llm:
        return {
            "error": "GEMINI_API_KEY not set",
            "details": (
                "Add your Gemini API key to your local .env file. "
                "Never share the key."
            ),
        }

    # 1. Generate the LLM plan.
    try:
        if llm is _llm:
            response = llm(
                question.strip(),
                api_key,
                model,
                fallback_model,
            )
        else:
            # Compatibility with existing custom test LLMs.
            response = llm(
                question.strip(),
                api_key,
                model,
            )

    except Exception as exc:
        return {
            "error": f"Gemini call failed: {exc}"
        }

    if not isinstance(response, dict):
        return {"error": "LLM returned an invalid plan."}

    # 2. Extract plan and usage metadata.
    if "_plan" in response:
        plan = response["_plan"]
        usage = response.get("_usage")
        used_model = response.get("_model", model)
    else:
        # Normal dictionary returned by a custom/test LLM.
        plan = response
        usage = None
        used_model = model

    if not isinstance(plan, dict):
        return {"error": "LLM returned an invalid plan."}

    # 3. Extract token counts when available.
    input_tokens = usage.get("input_tokens") if usage else None
    output_tokens = usage.get("output_tokens") if usage else None
    total_tokens = usage.get("total_tokens") if usage else None

    # 4. Calculate estimated cost only when prices and token counts
    # are available.
    estimated_cost = None

    if (
        input_tokens is not None
        and output_tokens is not None
        and input_price_per_million is not None
        and output_price_per_million is not None
    ):
        estimated_cost = (
            input_tokens * input_price_per_million
            + output_tokens * output_price_per_million
        ) / 1_000_000

    # 5. Record every successful LLM response.
    print("DEBUG: answer() reached usage logging")
    print("DEBUG DB PATH:", db_path)
    print("DEBUG MODEL:", used_model)
    print("DEBUG USAGE:", usage)
    try:
        record_llm_usage(
            db_path=db_path,
            model=used_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
        )
        print("DEBUG: record_llm_usage completed successfully")

        print(
            f"LLM usage recorded: model={used_model}, "
            f"input={input_tokens}, output={output_tokens}"
        )

    except Exception as exc:
        # Usage logging failure must not break the analyst's answer.
        print(f"LLM usage logging failed: {exc}")

    # 6. Validate the generated plan.
    plan_types = [
        key
        for key in ("sql", "ratio","documents", "unanswerable")
        if key in plan
    ]

    if len(plan_types) != 1:
        return {
            "error": "Unrecognised or ambiguous plan",
            "plan": plan,
        }

    if "unanswerable" in plan:
        return {
            "answer": None,
            "reason": str(plan["unanswerable"]),
        }
    
    
    if "documents" in plan:
        try:
            chunks = retrieve_document_chunks(question, limit=5)

            if not chunks:
                return {
                    "answer": None,
                    "reason": (
                        "No document chunks are available. "
                        "Run document ingestion first."
                    ),
                    "citations": [],
                }

            context_parts = []
            citations = []

            for chunk in chunks:
                source = chunk["source_file"]
                page = chunk["page_no"]

                context_parts.append(
                    f"Source: {source}, Page: {page}\n"
                    f"Heading: {chunk['heading']}\n"
                    f"Content:\n{chunk['chunk_text']}"
                )

                citation = {
                    "document": source,
                    "page": page,
                }

                if citation not in citations:
                    citations.append(citation)

            context = "\n\n".join(context_parts)

            client = genai.Client(api_key=api_key.strip())

            response = client.models.generate_content(
                model=model,
                contents=(
                    "You are a bank credit analyst. Answer the question "
                    "using ONLY the supplied annual report excerpts.\n"
                    "Do not invent facts or use outside knowledge.\n"
                    "If the excerpts do not contain enough information, "
                    "clearly say so.\n"
                    "Cite supporting statements using "
                    "[document filename, page number].\n\n"
                    f"Question:\n{question}\n\n"
                    f"Annual report excerpts:\n{context}"
                ),
            )

                        
            answer_text = response.text or ""

            # Only allow citations from the retrieved document chunks.
            available_citations = {
                (str(chunk["source_file"]), int(chunk["page_no"]))
                for chunk in chunks
            }

            answer_citations = []

            # Extract citations written in the answer:
            # [kpr_mill_FY25.pdf, page 3]
            citation_pattern = re.compile(
                r"\[([^,\[\]]+),\s*page\s+(\d+)\]",
                re.IGNORECASE,
            )

            for match in citation_pattern.finditer(answer_text):
                document = match.group(1).strip()
                page = int(match.group(2))

                citation = (document, page)

                if citation in available_citations and citation not in answer_citations:
                    answer_citations.append(citation)

            return {
                "answer": answer_text,
                "citations": [
                    {
                        "document": document,
                        "page": page,
                    }
                    for document, page in answer_citations
                ],
            }


        except Exception as exc:
            return {
                "error": f"Document retrieval failed: {exc}"
            }

    # 7. Execute the plan safely.
    
    try:

        if "ratio" in plan:
            ratio_name = plan["ratio"]
            companies = plan.get("companies", [])

            if not isinstance(companies, list):
                return {
                    "plan": plan,
                    "error": "companies must be a list",
                }

            if not all(isinstance(c, str) for c in companies):
                return {
                    "plan": plan,
                    "error": "Company names must be strings",
                }

            if len(companies) > 3:
                return {
                    "plan": plan,
                    "error": "Choose at most 3 companies",
                }

            result = ratio_series(
                db_path,
                ratio_name,
                companies,
            )

            return {
                "plan": plan,
                "result": result,
            }

        sql = plan["sql"]

        if not isinstance(sql, str):
            return {
                "plan": plan,
                "error": "SQL must be a string",
            }

        rows = run_readonly(db_path, sql)

        return {
            "plan": plan,
            "rows": rows,
        }

    except (UnsafeSQL, ValueError, KeyError) as exc:
        return {
            "plan": plan,
            "error": str(exc),
        }
