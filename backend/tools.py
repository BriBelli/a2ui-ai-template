"""
AI Tools Module

Provides tool integrations for enhanced AI capabilities:
- Web search via Tavily API
- More tools can be added here
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WebSearchTool:
    """Web search using Tavily API for real-time information."""
    
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
    
    def is_available(self) -> bool:
        """Check if Tavily API key is configured."""
        return bool(self.api_key)
    
    async def search(
        self, 
        query: str, 
        max_results: int = 5,
        search_depth: str = "basic"
    ) -> Dict[str, Any]:
        """
        Perform a web search using Tavily API with graceful error handling.
        
        Args:
            query: Search query
            max_results: Maximum number of results (default 5)
            search_depth: "basic" or "advanced" (advanced is slower but more thorough)
        
        Returns:
            Dict with 'results' list, optional 'answer' summary, and 'success' flag
        """
        if not self.is_available():
            logger.warning("Web search: No API key configured")
            return {
                "success": False,
                "error": "not_configured",
                "error_message": "Web search not configured",
                "results": []
            }
        
        try:
            from tavily import TavilyClient
            
            client = TavilyClient(api_key=self.api_key)
            
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_answer=True,
                include_images=True,
            )
            
            # Format results
            results = []
            for item in response.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score", 0),
                })
            
            # Collect image URLs returned by Tavily
            images = response.get("images", [])
            # Tavily returns images as list of strings (URLs) or dicts
            image_urls = []
            for img in images:
                if isinstance(img, str):
                    image_urls.append(img)
                elif isinstance(img, dict) and img.get("url"):
                    image_urls.append(img["url"])
            
            return {
                "success": True,
                "query": query,
                "answer": response.get("answer"),
                "results": results,
                "images": image_urls[:6],  # Cap at 6 images
            }
            
        except ImportError:
            logger.warning("Web search: Tavily package not installed")
            return {
                "success": False,
                "error": "package_missing",
                "error_message": "Tavily package not installed",
                "results": []
            }
        except Exception as e:
            error_msg = str(e).lower()
            
            # Detect common error types
            if "rate limit" in error_msg or "429" in error_msg:
                logger.warning("Web search: Rate limit exceeded")
                return {
                    "success": False,
                    "error": "rate_limit",
                    "error_message": "Search rate limit exceeded. Try again later.",
                    "results": []
                }
            elif "401" in error_msg or "unauthorized" in error_msg or "invalid" in error_msg:
                logger.warning("Web search: Invalid API key")
                return {
                    "success": False,
                    "error": "invalid_key",
                    "error_message": "Invalid search API key",
                    "results": []
                }
            elif "timeout" in error_msg:
                logger.warning("Web search: Timeout - %s", e)
                return {
                    "success": False,
                    "error": "timeout",
                    "error_message": "Search request timed out",
                    "results": []
                }
            else:
                logger.warning("Web search failed: %s", e)
                return {
                    "success": False,
                    "error": "unknown",
                    "error_message": f"Search failed: {str(e)}",
                    "results": []
                }
    
    def format_for_context(self, search_results: Dict[str, Any]) -> Optional[str]:
        """
        Format search results as context for the LLM.
        
        Returns a string that can be prepended to the user's message,
        or None if search failed (so the query continues without search context).
        """
        if not search_results.get("success"):
            # Return None to indicate search failed - don't add any context
            # LLM will answer based on its training data instead
            return None
        
        results = search_results.get("results", [])
        if not results:
            # No results but search succeeded - inform LLM
            return "[Web search found no relevant results]"
        
        context_parts = ["[Web Search Results — REAL, CURRENT data. Use these facts in your answer.]"]
        
        if search_results.get("answer"):
            context_parts.append(f"Direct answer: {search_results['answer']}")
        
        for i, result in enumerate(results[:5], 1):
            context_parts.append(
                f"\n{i}. {result['title']}\n"
                f"   URL: {result['url']}\n"
                f"   {result['content'][:400]}"
            )
        
        # Include image URLs if available
        images = search_results.get("images", [])
        if images:
            context_parts.append("\n[Available Images]")
            for i, url in enumerate(images, 1):
                context_parts.append(f"  {i}. {url}")
            context_parts.append("[End of Available Images]")
        
        context_parts.append("\n[End of Search Results]\n")
        
        return "\n".join(context_parts)


# Tool instances
web_search = WebSearchTool()


async def llm_rewrite_query(
    message: str,
    location: str = "",
    history: Optional[list] = None,
) -> Optional[str]:
    """
    Use a fast LLM (nano) to rewrite a conversational prompt into an
    optimised web-search query. Returns None on any failure so the caller
    can fall back to rule-based rewriting.

    The LLM handles:
      - Typo correction
      - Semantic intent extraction
      - Context resolution from conversation history
      - Temporal anchoring (adds current date)
      - Filler stripping
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    from datetime import datetime

    now = datetime.now()
    date_str = now.strftime("%B %d, %Y")  # "February 09, 2026"

    # Build a minimal conversation context (last 2 exchanges max)
    context_lines = ""
    if history:
        recent = history[-4:]  # last 2 user+assistant pairs
        for msg in recent:
            role = msg.get("role", "")
            text = msg.get("content", "")[:200]
            context_lines += f"  {role}: {text}\n"

    system = (
        "You are a search-query optimizer. Given a user's chat message, "
        "rewrite it into a concise web search query that a search engine "
        "would return the best results for.\n\n"
        "Rules:\n"
        "- Fix any typos or misspellings\n"
        "- Strip conversational filler (show me, can you, please, etc.)\n"
        "- Add specificity: dates, full names, locations when relevant\n"
        "- For weather queries: search for CURRENT/TODAY weather, not monthly overviews. "
        "Example: 'current weather Glastonbury CT today' NOT 'weather February 2026'\n"
        "- For local queries (restaurants, events), include the user's location\n"
        "- For time-sensitive queries (stocks, news), include today's date\n"
        "- Keep it short — a search engine query, NOT a sentence\n"
        "- Return ONLY the search query string, nothing else\n"
        f"\nToday's date: {date_str}"
        + (f"\nUser location: {location}" if location else "")
    )

    user_prompt = message
    if context_lines:
        user_prompt = f"Recent conversation:\n{context_lines}\nCurrent message: {message}"

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=80,
            temperature=0.0,
        )

        query = response.choices[0].message.content.strip()

        # Sanity check: reject empty or overly long rewrites
        if not query or len(query) > 200:
            return None

        # Strip quotes if the LLM wrapped it
        if query.startswith('"') and query.endswith('"'):
            query = query[1:-1]

        return query
    except Exception as e:
        logger.warning("LLM query rewrite failed (falling back to rule-based): %s", e)
        return None


def rewrite_search_query(
    message: str,
    location: str = "",
    current_date: str = "",
) -> str:
    """
    Rewrite a conversational user prompt into an optimized search query.

    Strips filler, adds context (date, location for local queries),
    and reformulates for better search engine results.

    Examples:
        "Show weather forecast"  →  "weather forecast Glastonbury CT February 2026"
        "What's the DOW doing?"  →  "Dow Jones Industrial Average current value"
        "Compare iPhone vs Android"  →  "iPhone vs Android comparison 2026"
        "Show me cool artwork"   →  "trending contemporary artwork 2026"
    """
    import re
    from datetime import datetime

    if not current_date:
        now = datetime.now()
        current_date = now.strftime("%B %Y")  # e.g. "February 2026"

    msg = message.strip()

    # ── 1. Strip conversational filler ──────────────────────
    filler_prefixes = [
        r"^(can you |could you |please |hey |hi |ok |okay |)",
        r"(show me |tell me |give me |find me |get me |look up |search for |search |display |pull up |let me see |i want to see |i want |i need )",
        r"(what is |what are |what's |whats )",
    ]
    cleaned = msg
    for pattern in filler_prefixes:
        cleaned = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE).strip()

    # If stripping removed everything, keep original
    if len(cleaned) < 3:
        cleaned = msg

    # ── 2. Detect if query is local ─────────────────────────
    local_indicators = [
        "weather", "forecast", "temperature", "near me", "nearby",
        "local", "restaurant", "food", "store", "event", "concert",
        "traffic", "commute", "directions", "open now",
    ]
    is_local = any(ind in cleaned.lower() for ind in local_indicators)

    # ── 3. Detect if query is time-sensitive ────────────────
    time_indicators = [
        "current", "latest", "today", "now", "recent", "this week",
        "this month", "this year", "trending", "popular", "new",
        "price", "stock", "dow", "nasdaq", "s&p", "bitcoin",
        "crypto", "market", "score", "standings", "news",
    ]
    is_time_sensitive = any(ind in cleaned.lower() for ind in time_indicators)

    # ── 3b. Detect if query is weather-specific ───────────
    weather_indicators = ["weather", "forecast", "temperature"]
    is_weather = any(ind in cleaned.lower() for ind in weather_indicators)

    # ── 4. Build optimized query ────────────────────────────
    parts = []

    # Weather gets special treatment: "current weather [location] today"
    if is_weather:
        parts.append(f"current {cleaned}")
        if location:
            parts.append(location)
        parts.append("today")
    else:
        parts.append(cleaned)
        # Append location for local queries
        if is_local and location:
            parts.append(location)
        # Append date for time-sensitive queries
        if is_time_sensitive:
            parts.append(current_date)

    query = " ".join(parts)

    # ── 5. Clean up whitespace ──────────────────────────────
    query = re.sub(r"\s+", " ", query).strip()

    return query


def should_search(message: str) -> bool:
    """
    Determine if a message would benefit from web search.
    
    Looks for indicators of real-time information needs:
    - Temporal cues (current, today, latest, etc.)
    - Financial/market terms (stock, dow, nasdaq, crypto, etc.)
    - Data queries (weather, sports, news, etc.)
    - Direct questions that imply factual lookup
    """
    search_indicators = [
        # Temporal cues
        "current", "latest", "today", "now", "recent", "right now",
        "this week", "this month", "this year", "yesterday",
        "these days", "nowadays", "trending", "popular",
        "getting noticed", "going viral", "buzzing",
        # Financial / markets
        "price", "stock", "market", "trading", "index", "fund",
        "dow", "djia", "nasdaq", "s&p", "sp500", "s&p500",
        "nyse", "russell", "ftse", "nikkei", "hang seng",
        "bitcoin", "btc", "eth", "ethereum", "crypto",
        "forex", "bond", "treasury", "yield", "earnings",
        "ipo", "dividend", "market cap",
        # Ticker patterns — 1-5 uppercase letters common in follow-ups
        "ticker", "share", "shares",
        # Real-time data
        "weather", "forecast", "temperature",
        "news", "headlines", "breaking",
        "score", "game", "match", "standings",
        # Direct questions
        "what is the", "how much", "who won", "who is",
        "where is", "when is", "is it",
        "compare", "vs", "versus",
        "result", "update", "status",
        # Visual / discovery — benefit from image search
        "show me", "pictures of", "photos of", "images of",
        "what does", "look like", "artwork", "art",
        "design", "architecture", "fashion",
        # Year references
        "2024", "2025", "2026",
    ]
    
    message_lower = message.lower()
    return any(indicator in message_lower for indicator in search_indicators)
    