
import json
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    StreamingResponse,
)

from app.agent import answer
from app.config import Settings, get_settings
from app.db import connect, get_llm_usage
from app.ratios import RATIOS
from app.schemas import AskRequest
from app.service import ratio_series


app = FastAPI(title="LoomLedger", version="0.3.0")

SettingsDep = Annotated[
    Settings,
    Depends(get_settings),
]


@app.get("/health")
def health(settings: SettingsDep) -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }


@app.get("/ratios")
def ratios() -> dict:
    return {
        key: {
            "inputs": value[0],
            "unit": value[2],
        }
        for key, value in RATIOS.items()
    }


@app.get("/facts")
def facts(
    settings: SettingsDep,
    company: str | None = None,
    metric: str | None = None,
) -> list[dict]:

    con = connect(settings.db_path, read_only=True)

    try:
        query = "SELECT * FROM facts WHERE needs_review=0"
        params = []

        for column, value in (
            ("company", company),
            ("metric", metric),
        ):
            if value:
                query += f" AND {column}=?"
                params.append(value)

        rows = con.execute(
            query + " ORDER BY company, fiscal_year LIMIT 500",
            params,
        )

        return [dict(row) for row in rows]

    finally:
        con.close()


@app.get("/companies")
def companies(settings: SettingsDep) -> dict:

    con = connect(settings.db_path, read_only=True)

    try:
        rows = con.execute(
            """
            SELECT DISTINCT company
            FROM facts
            WHERE needs_review = 0
            ORDER BY company
            """
        ).fetchall()

        return {
            "companies": [row["company"] for row in rows]
        }

    finally:
        con.close()


@app.get("/ratio")
def ratio(
    settings: SettingsDep,
    name: str,
    companies: Annotated[list[str], Query()],
    basis: str = "standalone",
) -> dict:

    if len(companies) > 3:
        raise HTTPException(400, "Pick at most 3 companies")

    try:
        return ratio_series(
            settings.db_path,
            name,
            companies,
            basis,
        )

    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/usage")
def usage(settings: SettingsDep) -> dict:
    """Return recorded LLM token usage and estimated costs."""

    return get_llm_usage(settings.db_path)


@app.get("/pdf/{name}")
def pdf(name: str, settings: SettingsDep):

    root = Path(settings.raw_dir).resolve()
    path = (root / name).resolve()

    if (
        path.parent != root
        or path.suffix.lower() != ".pdf"
        or not path.is_file()
    ):
        raise HTTPException(404, "Not found")

    return FileResponse(
        path,
        media_type="application/pdf",
    )


def run_answer(req: AskRequest, settings: Settings) -> dict:

    return answer(
        question=req.question,
        db_path=settings.db_path,
        api_key=settings.gemini_api_key,
        model=settings.llm_model,
        fallback_model=settings.llm_fallback_model,
        input_price_per_million=settings.gemini_input_price_per_million,
        output_price_per_million=settings.gemini_output_price_per_million,
    )


@app.post("/ask")
def ask(
    req: AskRequest,
    settings: SettingsDep,
) -> dict:

    return run_answer(req, settings)


@app.post("/ask/stream")
def ask_stream(
    req: AskRequest,
    settings: SettingsDep,
):

    def event_stream():

        yield (
            "event: status\n"
            + "data: "
            + json.dumps({
                "message": "Processing your question..."
            })
            + "\n\n"
        )

        try:
            result = run_answer(req, settings)

            yield (
                "event: result\n"
                + "data: "
                + json.dumps(result, default=str)
                + "\n\n"
            )

        except Exception as exc:

            yield (
                "event: error\n"
                + "data: "
                + json.dumps({"error": str(exc)})
                + "\n\n"
            )

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/", response_class=HTMLResponse)
@app.get("/chart", response_class=HTMLResponse)
def chart() -> str:

    return (
        Path(__file__).parent / "chart.html"
    ).read_text(encoding="utf-8")
