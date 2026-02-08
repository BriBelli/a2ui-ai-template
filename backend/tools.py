"""
AI Tools Module

Provides tool integrations for enhanced AI capabilities:
- Web search via Tavily API
- More tools can be added here
"""

import os
from typing import Any, Dict, List, Optional


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
            print("⚠️  Web search: No API key configured")
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
            print("⚠️  Web search: Tavily package not installed")
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
                print("⚠️  Web search: Rate limit exceeded")
                return {
                    "success": False,
                    "error": "rate_limit",
                    "error_message": "Search rate limit exceeded. Try again later.",
                    "results": []
                }
            elif "401" in error_msg or "unauthorized" in error_msg or "invalid" in error_msg:
                print("⚠️  Web search: Invalid API key")
                return {
                    "success": False,
                    "error": "invalid_key",
                    "error_message": "Invalid search API key",
                    "results": []
                }
            elif "timeout" in error_msg:
                print(f"⚠️  Web search: Timeout - {e}")
                return {
                    "success": False,
                    "error": "timeout",
                    "error_message": "Search request timed out",
                    "results": []
                }
            else:
                print(f"⚠️  Web search failed: {e}")
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
        
        context_parts = ["[Web Search Results]"]
        
        if search_results.get("answer"):
            context_parts.append(f"Summary: {search_results['answer']}")
        
        for i, result in enumerate(results[:3], 1):
            context_parts.append(
                f"\n{i}. {result['title']}\n"
                f"   URL: {result['url']}\n"
                f"   {result['content'][:300]}..."
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
