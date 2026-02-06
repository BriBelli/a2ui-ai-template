"""
A2UI Response Generator

This module generates A2UI protocol responses for chat messages.
It demonstrates how to construct declarative UI JSON that the
A2UI renderer will transform into actual UI components.
"""

import os
import json
import random
from datetime import datetime
from typing import Any, Dict, Optional

# Try to import OpenAI for AI-powered responses
try:
    import openai
    HAS_OPENAI = bool(os.getenv("OPENAI_API_KEY"))
except ImportError:
    HAS_OPENAI = False


def get_a2ui_response(message: str) -> Dict[str, Any]:
    """
    Generate an A2UI response for the given message.
    
    Returns a dict with:
    - text: Optional plain text
    - a2ui: Optional A2UI protocol JSON
    """
    lower_message = message.lower()
    
    # Route to specific handlers based on message content
    if any(word in lower_message for word in ['stock', 'trending', 'market']):
        return get_stock_response(message)
    
    if any(word in lower_message for word in ['chart', 'graph', 'visual', 'plot']):
        return get_chart_response(message)
    
    if any(word in lower_message for word in ['weather', 'forecast', 'temperature']):
        return get_weather_response(message)
    
    if any(word in lower_message for word in ['task', 'todo', 'list', 'checklist']):
        return get_task_response(message)
    
    if any(word in lower_message for word in ['help', 'what can you do', 'capabilities']):
        return get_help_response()
    
    # Compare X vs Y style queries (fallback when no provider selected or AI fails)
    if 'compare' in lower_message and (' vs ' in lower_message or ' versus ' in lower_message):
        return get_compare_response(message)
    
    # Default: try AI or return generic response
    if HAS_OPENAI:
        return get_ai_response(message)
    
    return get_default_response(message)


def get_stock_response(message: str) -> Dict[str, Any]:
    """Generate stock market data response."""
    # Simulated real-time stock data
    stocks = [
        {"symbol": "NVDA", "name": "NVIDIA Corporation", "price": f"${random.uniform(850, 920):.2f}", "change": f"+{random.uniform(2, 8):.1f}%"},
        {"symbol": "AAPL", "name": "Apple Inc.", "price": f"${random.uniform(175, 190):.2f}", "change": f"+{random.uniform(0.5, 3):.1f}%"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "price": f"${random.uniform(400, 430):.2f}", "change": f"+{random.uniform(1, 4):.1f}%"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "price": f"${random.uniform(135, 150):.2f}", "change": f"+{random.uniform(0.5, 2.5):.1f}%"},
        {"symbol": "META", "name": "Meta Platforms Inc.", "price": f"${random.uniform(470, 510):.2f}", "change": f"+{random.uniform(2, 5):.1f}%"},
    ]
    
    return {
        "text": "Here are the top 5 trending stocks right now:",
        "a2ui": {
            "version": "1.0",
            "components": [
                {
                    "id": "stocks-container",
                    "type": "container",
                    "props": {"layout": "vertical", "gap": "md"},
                    "children": [
                        {
                            "id": "stocks-table",
                            "type": "data-table",
                            "props": {
                                "columns": [
                                    {"key": "symbol", "label": "Symbol", "width": "80px"},
                                    {"key": "name", "label": "Company", "width": "auto"},
                                    {"key": "price", "label": "Price", "width": "100px", "align": "right"},
                                    {"key": "change", "label": "Change", "width": "100px", "align": "right"},
                                ],
                                "data": stocks,
                            },
                        },
                        {
                            "id": "chart-hint",
                            "type": "text",
                            "props": {
                                "content": "💡 Ask me to show a chart of these stocks!",
                                "variant": "caption",
                            },
                        },
                    ],
                },
            ],
        },
        "suggestions": ["Show NVDA stock chart", "Compare tech stocks performance"],
    }


def get_chart_response(message: str) -> Dict[str, Any]:
    """Generate chart/visualization response."""
    # Generate semi-random but realistic-looking data
    performance = [
        round(random.uniform(70, 100), 1),
        round(random.uniform(35, 50), 1),
        round(random.uniform(25, 40), 1),
        round(random.uniform(15, 30), 1),
        round(random.uniform(10, 25), 1),
    ]
    
    # Line chart trend data
    week1 = round(random.uniform(700, 750))
    trend_nvda = [week1, week1 + 40, week1 + 90, week1 + 140]
    week1_msft = round(random.uniform(380, 400))
    trend_msft = [week1_msft, week1_msft + 10, week1_msft + 18, week1_msft + 25]
    
    return {
        "text": "Here's a performance visualization for the trending stocks:",
        "a2ui": {
            "version": "1.0",
            "components": [
                {
                    "id": "chart-container",
                    "type": "container",
                    "props": {"layout": "vertical", "gap": "lg"},
                    "children": [
                        {
                            "id": "bar-chart",
                            "type": "chart",
                            "props": {
                                "chartType": "bar",
                                "title": "Stock Performance (YTD Change %)",
                                "data": {
                                    "labels": ["NVDA", "META", "MSFT", "AAPL", "GOOGL"],
                                    "datasets": [
                                        {
                                            "label": "YTD Performance %",
                                            "data": performance,
                                            "backgroundColor": [
                                                "#76b900",
                                                "#0668E1",
                                                "#00a1f1",
                                                "#555555",
                                                "#4285f4",
                                            ],
                                        },
                                    ],
                                },
                                "options": {"height": 300},
                            },
                        },
                        {
                            "id": "line-chart",
                            "type": "chart",
                            "props": {
                                "chartType": "line",
                                "title": "30-Day Price Trend",
                                "data": {
                                    "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
                                    "datasets": [
                                        {
                                            "label": "NVDA",
                                            "data": trend_nvda,
                                            "borderColor": "#76b900",
                                        },
                                        {
                                            "label": "MSFT",
                                            "data": trend_msft,
                                            "borderColor": "#00a1f1",
                                        },
                                    ],
                                },
                                "options": {"height": 250},
                            },
                        },
                    ],
                },
            ],
        },
        "suggestions": ["Show 1-year NVDA chart", "Compare AAPL vs MSFT"],
    }


def get_weather_response(message: str) -> Dict[str, Any]:
    """Generate weather forecast response."""
    cities = ["San Francisco", "New York", "Los Angeles", "Seattle", "Chicago"]
    city = random.choice(cities)
    
    today_temp = random.randint(60, 85)
    
    return {
        "text": f"Here's the weather forecast for {city}:",
        "a2ui": {
            "version": "1.0",
            "components": [
                {
                    "id": "weather-container",
                    "type": "container",
                    "props": {"layout": "horizontal", "gap": "md", "wrap": True},
                    "children": [
                        {
                            "id": "today",
                            "type": "card",
                            "props": {"title": "Today", "subtitle": city},
                            "children": [
                                {
                                    "id": "today-temp",
                                    "type": "text",
                                    "props": {"content": f"{today_temp}°F", "variant": "h1"},
                                },
                                {
                                    "id": "today-desc",
                                    "type": "text",
                                    "props": {"content": "☀️ Sunny", "variant": "body"},
                                },
                            ],
                        },
                        {
                            "id": "tomorrow",
                            "type": "card",
                            "props": {"title": "Tomorrow"},
                            "children": [
                                {
                                    "id": "tomorrow-temp",
                                    "type": "text",
                                    "props": {"content": f"{today_temp - 4}°F", "variant": "h2"},
                                },
                                {
                                    "id": "tomorrow-desc",
                                    "type": "text",
                                    "props": {"content": "⛅ Partly Cloudy", "variant": "body"},
                                },
                            ],
                        },
                        {
                            "id": "day3",
                            "type": "card",
                            "props": {"title": "Wednesday"},
                            "children": [
                                {
                                    "id": "day3-temp",
                                    "type": "text",
                                    "props": {"content": f"{today_temp - 7}°F", "variant": "h2"},
                                },
                                {
                                    "id": "day3-desc",
                                    "type": "text",
                                    "props": {"content": "🌧️ Rain", "variant": "body"},
                                },
                            ],
                        },
                    ],
                },
            ],
        },
        "suggestions": ["5-day extended forecast", "Weather in another city"],
    }


def get_task_response(message: str) -> Dict[str, Any]:
    """Generate task list response."""
    return {
        "text": "I've created a task list for you:",
        "a2ui": {
            "version": "1.0",
            "components": [
                {
                    "id": "tasks-card",
                    "type": "card",
                    "props": {"title": "📋 My Tasks"},
                    "children": [
                        {
                            "id": "task-list",
                            "type": "list",
                            "props": {
                                "items": [
                                    {"id": "1", "text": "Review Q4 financial reports", "status": "completed"},
                                    {"id": "2", "text": "Prepare presentation slides", "status": "in-progress"},
                                    {"id": "3", "text": "Schedule team sync meeting", "status": "pending"},
                                    {"id": "4", "text": "Update project documentation", "status": "pending"},
                                    {"id": "5", "text": "Send weekly status update", "status": "pending"},
                                ],
                                "variant": "checklist",
                            },
                        },
                    ],
                },
            ],
        },
        "suggestions": ["Add a new task", "Show completed tasks"],
    }


def get_compare_response(message: str) -> Dict[str, Any]:
    """Generate a comparison response (e.g. iPhone vs Android) as data-table."""
    lower = message.lower()
    # Default to iPhone vs Android; could parse message for other comparisons later
    if 'iphone' in lower or 'android' in lower or 'phone' in lower:
        return {
            "text": "Here’s a side-by-side comparison of iPhone and Android:",
            "a2ui": {
                "version": "1.0",
                "components": [
                    {
                        "id": "compare-container",
                        "type": "container",
                        "props": {"layout": "vertical", "gap": "md"},
                        "children": [
                            {
                                "id": "compare-table",
                                "type": "data-table",
                                "props": {
                                    "columns": [
                                        {"key": "feature", "label": "Feature", "width": "180px"},
                                        {"key": "iphone", "label": "iPhone", "width": "auto"},
                                        {"key": "android", "label": "Android", "width": "auto"},
                                    ],
                                    "data": [
                                        {"feature": "Ecosystem", "iphone": "Apple (iOS, Mac, Watch)", "android": "Google + many OEMs (Samsung, Pixel, etc.)"},
                                        {"feature": "App Store", "iphone": "App Store", "android": "Google Play"},
                                        {"feature": "Customization", "iphone": "Limited", "android": "High (launchers, widgets)"},
                                        {"feature": "Privacy", "iphone": "Strong (App Tracking Transparency)", "android": "Improving (Google Play Protect)"},
                                        {"feature": "Updates", "iphone": "Long support, same day", "android": "Varies by manufacturer"},
                                        {"feature": "Price range", "iphone": "Premium", "android": "Budget to flagship"},
                                    ],
                                },
                            },
                        ],
                    },
                ],
            },
            "suggestions": ["Compare Samsung vs Pixel", "Best budget phones"],
        }
    # Generic comparison placeholder
    return get_default_response(message)


def get_help_response() -> Dict[str, Any]:
    """Generate help/capabilities response."""
    return {
        "text": "Here's what I can help you with:",
        "a2ui": {
            "version": "1.0",
            "components": [
                {
                    "id": "help-container",
                    "type": "container",
                    "props": {"layout": "vertical", "gap": "md"},
                    "children": [
                        {
                            "id": "capabilities-card",
                            "type": "card",
                            "props": {"title": "🚀 My Capabilities"},
                            "children": [
                                {
                                    "id": "capabilities-list",
                                    "type": "list",
                                    "props": {
                                        "variant": "bullet",
                                        "items": [
                                            {"id": "1", "text": "📈 Stock market data and analysis"},
                                            {"id": "2", "text": "📊 Data visualization with charts"},
                                            {"id": "3", "text": "🌤️ Weather forecasts"},
                                            {"id": "4", "text": "✅ Task management and lists"},
                                            {"id": "5", "text": "💬 General questions and conversation"},
                                        ],
                                    },
                                },
                            ],
                        },
                        {
                            "id": "tips-text",
                            "type": "text",
                            "props": {
                                "content": "Try asking: 'Show me trending stocks' or 'Create a chart of stock performance'",
                                "variant": "caption",
                            },
                        },
                    ],
                },
            ],
        },
        "suggestions": ["Show trending stocks", "Create a chart", "What's the weather?"],
    }


def get_ai_response(message: str) -> Dict[str, Any]:
    """Generate AI-powered response (when OpenAI is available)."""
    try:
        client = openai.OpenAI()
        
        # System prompt to guide AI to generate A2UI-compatible responses
        system_prompt = """You are an AI assistant that responds to user queries.
        Provide helpful, concise responses. Your responses will be displayed
        in a chat interface with rich UI capabilities."""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            max_tokens=500
        )
        
        return {
            "text": response.choices[0].message.content.strip(),
        }
    except Exception as e:
        return get_default_response(message)


def get_default_response(message: str) -> Dict[str, Any]:
    """Generate default response when no specific handler matches."""
    return {
        "text": f"""I understand you're asking about "{message}". 

I can help you with:
• Stock market data and charts
• Weather forecasts  
• Task management
• Data analysis and visualization

Try asking about "trending stocks" or "show me a chart"!""",
        "suggestions": ["Top 5 trending stocks", "Show weather forecast"],
    }
