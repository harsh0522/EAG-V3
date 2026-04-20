import asyncio
import json
import os
import time
from typing import AsyncGenerator

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

from usage_tracker import tracker
from tools import (
    get_fear_greed_index,
    get_geopolitical_news,
    get_oil_prices,
    get_youtube_videos,
    predict_oil_trend,
)

MAX_ITERATIONS = 12

TOOL_DECLARATIONS = Tool(
    function_declarations=[
        FunctionDeclaration(
            name="get_geopolitical_news",
            description="Fetch recent geopolitical news and headlines for a specific region or country from Google News RSS.",
            parameters={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "The region, country, or area name to search news for (e.g. 'Middle East', 'Ukraine', 'Taiwan')",
                    }
                },
                "required": ["region"],
            },
        ),
        FunctionDeclaration(
            name="get_fear_greed_index",
            description="Fetch the current global crypto/market Fear & Greed Index score, which reflects overall market sentiment.",
            parameters={"type": "object", "properties": {}},
        ),
        FunctionDeclaration(
            name="get_oil_prices",
            description="Fetch current WTI crude oil futures price, previous close, and percentage change from Yahoo Finance.",
            parameters={"type": "object", "properties": {}},
        ),
        FunctionDeclaration(
            name="predict_oil_trend",
            description="Use LLM analysis to predict the short-term (48-hour) oil price trend based on news, sentiment, and current prices.",
            parameters={
                "type": "object",
                "properties": {
                    "news": {
                        "type": "string",
                        "description": "Summary of relevant geopolitical news",
                    },
                    "sentiment": {
                        "type": "string",
                        "description": "Current market sentiment data (Fear & Greed Index)",
                    },
                    "prices": {
                        "type": "string",
                        "description": "Current oil price data including price and % change",
                    },
                },
                "required": ["news", "sentiment", "prices"],
            },
        ),
        FunctionDeclaration(
            name="get_youtube_videos",
            description="Fetch recent YouTube videos related to a region's geopolitical situation.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for YouTube videos (e.g. 'Middle East conflict 2024', 'Taiwan strait tensions')",
                    }
                },
                "required": ["query"],
            },
        ),
    ]
)

TOOL_MAP = {
    "get_geopolitical_news": get_geopolitical_news,
    "get_fear_greed_index": get_fear_greed_index,
    "get_oil_prices": get_oil_prices,
    "predict_oil_trend": predict_oil_trend,
    "get_youtube_videos": get_youtube_videos,
}


class GeoIntelAgent:
    def __init__(self):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
            tools=[TOOL_DECLARATIONS],
        )

    async def run(self, region: str) -> AsyncGenerator[dict, None]:
        session_start = time.time()
        total_tokens = 0
        total_api_calls = 0
        all_urls = []
        iteration = 0

        chat = self.model.start_chat(history=[])

        system_prompt = f"""You are GeoIntel, an expert geopolitical intelligence analyst AI agent.

Your task: produce a comprehensive intelligence report for **{region}**.

You MUST call these tools (in order):
1. get_geopolitical_news("{region}") — gather recent news
2. get_fear_greed_index() — check market sentiment
3. get_oil_prices() — check crude oil prices
4. predict_oil_trend(...) — pass summaries of the above to predict oil direction
5. get_youtube_videos("{region} geopolitics 2024") — find relevant videos

After all tools have been called, write a final intelligence report with these sections:
## EXECUTIVE SUMMARY
## GEOPOLITICAL SITUATION
## ECONOMIC & ENERGY IMPACT
## OIL MARKET OUTLOOK
## RISK ASSESSMENT (rate each: LOW/MEDIUM/HIGH/CRITICAL)
## RECOMMENDATIONS

Be analytical, specific, and cite data from the tools. Do NOT call any more tools after writing the final report."""

        # First message
        yield _event("agent_start", {"region": region, "message": f"Starting GeoIntel analysis for: {region}"})

        try:
            response = await asyncio.wait_for(
                chat.send_message_async(system_prompt), timeout=60.0
            )
        except asyncio.TimeoutError:
            yield _event("error", {"message": "Gemini API timeout on initial call (60s). Check your API key / quota."})
            return
        except Exception as e:
            yield _event("error", {"message": f"Gemini API error: {e}"})
            return
        total_api_calls += 1

        while iteration < MAX_ITERATIONS:
            iteration += 1

            # Count tokens
            if response.usage_metadata:
                call_tokens = response.usage_metadata.total_token_count or 0
                total_tokens += call_tokens
            else:
                call_tokens = 0
            tracker.record_gemini_call(call_tokens)

            yield _event("token_update", {
                "iteration": iteration,
                "call_tokens": call_tokens,
                "total_tokens": total_tokens,
            })

            # Collect function calls from response
            function_calls = []
            text_parts = []
            for part in response.parts:
                if part.function_call:
                    function_calls.append(part.function_call)
                elif part.text:
                    text_parts.append(part.text)

            # Log raw LLM response
            raw_response = {
                "function_calls": [
                    {"name": fc.name, "args": dict(fc.args)} for fc in function_calls
                ],
                "text": "\n".join(text_parts) if text_parts else None,
                "finish_reason": str(response.candidates[0].finish_reason) if response.candidates else "UNKNOWN",
            }
            yield _event("llm_response", {
                "iteration": iteration,
                "raw": raw_response,
                "call_tokens": call_tokens,
                "total_tokens": total_tokens,
            })

            # No function calls → final answer
            if not function_calls:
                final_text = "\n".join(text_parts)
                yield _event("final_answer", {
                    "content": final_text,
                    "iteration": iteration,
                })
                break

            # Execute all function calls in parallel
            function_response_parts = []

            for fc in function_calls:
                yield _event("tool_call", {
                    "iteration": iteration,
                    "function": fc.name,
                    "args": dict(fc.args),
                })

            async def _run_tool(fc):
                tool_fn = TOOL_MAP.get(fc.name)
                if tool_fn is None:
                    return {"error": f"Unknown tool: {fc.name}"}
                return await tool_fn(**dict(fc.args))

            results = await asyncio.gather(*[_run_tool(fc) for fc in function_calls])

            for fc, result in zip(function_calls, results):
                fn_name = fc.name
                all_urls.append(result.get("url", fn_name))
                total_api_calls += 1

                yield _event("tool_result", {
                    "iteration": iteration,
                    "function": fn_name,
                    "url": result.get("url"),
                    "method": result.get("method"),
                    "response_time_ms": result.get("response_time_ms"),
                    "data": result.get("data"),
                    "error": result.get("error"),
                })

                function_response_parts.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=fn_name,
                            response={"result": json.dumps(result.get("data", {}), default=str)},
                        )
                    )
                )

            # Send all function results back to LLM
            try:
                response = await asyncio.wait_for(
                    chat.send_message_async(
                        genai.protos.Content(role="function", parts=function_response_parts)
                    ),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                yield _event("error", {"message": "Gemini API timeout waiting for LLM response (60s). Quota may be exhausted."})
                return
            except Exception as e:
                yield _event("error", {"message": f"Gemini API error: {e}"})
                return
            total_api_calls += 1

        total_time = round((time.time() - session_start) * 1000, 1)
        yield _event("session_summary", {
            "total_iterations": iteration,
            "total_api_calls": total_api_calls,
            "total_tokens": total_tokens,
            "total_time_ms": total_time,
            "all_urls": all_urls,
            "region": region,
        })


def _event(event_type: str, data: dict) -> dict:
    return {"type": event_type, "ts": round(time.time() * 1000), **data}
