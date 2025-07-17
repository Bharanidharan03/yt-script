import requests
import feedparser
import google.generativeai as genai
import praw
import time
from flask import Flask, request, render_template
import os
from dotenv import load_dotenv

load_dotenv()  # Loads the .env file

# ─── API KEYS (Directly Embedded - USE WITH CAUTION) ───────────────
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# ─── INITIAL SETUP ──────────────────────────────────────────
if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
    print("Warning: Please replace 'YOUR_GEMINI_API_KEY' with your actual API key.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

reddit = None
if REDDIT_CLIENT_ID == "YOUR_REDDIT_CLIENT_ID" or REDDIT_CLIENT_SECRET == "YOUR_REDDIT_CLIENT_SECRET":
    print("Warning: Please replace 'YOUR_REDDIT_CLIENT_ID' and 'YOUR_REDDIT_CLIENT_SECRET' with your actual API keys.")
else:
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent="TrendingScriptGenerator"
        )
    except Exception as e:
        print(f"Error connecting to Reddit: {e}")

REGION_CODE = "IN"

# ─── YOUTUBE TRENDING FUNCTIONS ─────────────────────────────
def get_youtube_categories():
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "YOUR_YOUTUBE_API_KEY":
        print("Error: YOUTUBE_API_KEY is missing.")
        return {}
    url = f"https://www.googleapis.com/youtube/v3/videoCategories?part=snippet&regionCode={REGION_CODE}&key={YOUTUBE_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        return {item["id"]: item["snippet"]["title"] for item in data.get("items", [])}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching YouTube categories: {e}")
        return {}

def get_trending_videos(category_id, max_results=5):
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "YOUR_YOUTUBE_API_KEY":
        print("Error: YOUTUBE_API_KEY is missing.")
        return []
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet",
        "chart": "mostPopular",
        "regionCode": REGION_CODE,
        "videoCategoryId": category_id,
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return [(video["id"], video["snippet"]["title"]) for video in data.get("items", [])]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching trending YouTube videos: {e}")
        return []

# ─── OTHER SOURCES ──────────────────────────────────────────
def get_google_news(max_results=5):
    try:
        feed = feedparser.parse(f"https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en")
        return [entry.title for entry in feed.entries[:max_results]]
    except Exception as e:
        print(f"Error fetching Google News: {e}")
        return []

def get_reddit_trending(max_results=5):
    if reddit:
        try:
            return [post.title for post in reddit.subreddit("all").hot(limit=max_results)]
        except Exception as e:
            print(f"Error fetching trending posts from Reddit: {e}")
            return []
    else:
        print("Warning: Reddit client not initialized. Cannot fetch trending topics.")
        return []

# ─── GEMINI SCRIPT GENERATOR WITH TONE & LANGUAGE ─────────────
def build_prompt(topic, tone, length, language):
    prompt = f"Generate a YouTube script on the topic '{topic}'"

    # Add tone
    tone_mapping = {
        "informative": "in an informative and educational tone.",
        "funny": "with humor, witty remarks, and a light tone.",
        "serious": "in a serious and analytical tone.",
        "inspirational": "in an inspirational and motivational tone.",
        "casual": "in a casual, fun, and engaging tone.",
        "professional": "in a professional and informative tone.",
        "dramatic": "with dramatic flair, emotion, and storytelling."
    }
    prompt += f" {tone_mapping.get(tone.lower(), 'in a neutral tone.')}"

    # Add length
    length_mapping = {
        "short": "Keep it concise, around 1-2 minutes in spoken duration.",
        "medium": "Make it a moderate length, around 3-5 minutes long.",
        "long": "Make it a detailed and comprehensive script, around 7-10 minutes or longer."
    }
    prompt += f" The approximate spoken duration should be {length_mapping.get(length.lower(), 'a medium length.')}"

    # Add language
    language_mapping = {
        "hindi": " The script should be primarily in Hindi.",
        "tamil": " The script should be primarily in Tamil.",
        "english-hindi": " Mix English and Hindi naturally in a conversational style.",
        "english-tamil": " Mix English and Tamil naturally in a conversational style."
    }
    prompt += f"{language_mapping.get(language.lower(), '')}"

    return prompt

def generate_script(topic, tone="informative", length="medium", language="english", max_retries=3, initial_delay=5):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        print("Error: GEMINI_API_KEY is missing. Cannot generate script.")
        return ""
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = build_prompt(topic, tone, length, language)
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            if "429" in str(e):
                retry_delay = initial_delay * (2 ** attempt) # Exponential backoff
                print(f"Rate limit hit for '{topic}'. Retrying in {retry_delay} seconds (attempt {attempt + 1}/{max_retries}).")
                time.sleep(retry_delay)
            else:
                print(f"Error generating script for '{topic}': {e}")
                return ""
    print(f"Failed to generate script for '{topic}' after {max_retries} retries.")
    return ""

# ─── FETCH TRENDING TOPICS (Unified Function) ──────────────────
def fetch_trending_topics(source="youtube", domain=None, max_topics=5):
    topics = []
    if source.lower() == "youtube":
        if domain and domain.lower() != "all":
            categories = get_youtube_categories()
            category_id = None
            for id, name in categories.items():
                if domain.lower() in name.lower():
                    category_id = id
                    break
            if category_id:
                trending_videos = get_trending_videos(category_id, max_topics)
                topics = [title for _, title in trending_videos]
            else:
                print(f"Warning: Category '{domain}' not found on YouTube.")
        elif source.lower() == "youtube" and (domain is None or domain.lower() == "all"):
            # Fetching general trending if no specific domain or "all" is selected
            general_trending = get_trending_videos(0, max_topics) # Category 0 might be general trending, needs verification
            topics = [title for _, title in general_trending]
    elif source.lower() == "reddit":
        topics = get_reddit_trending(max_topics)
    elif source.lower() == "google_news":
        topics = get_google_news(max_topics)
    elif source.lower() == "fallback":
        reddit_topics = get_reddit_trending(max_topics // 2)
        google_news_topics = get_google_news(max_topics - len(reddit_topics))
        topics = reddit_topics + google_news_topics
    else:
        print(f"Error: Invalid trending source '{source}'.")
    return topics

# ─── GENERATE MULTIPLE SCRIPTS (Adjusted for Topic List) ──────
def generate_scripts(topics, length, language, tone):
    scripts = []
    for i, topic in enumerate(topics):
        script_content = generate_script(topic, tone, length, language)
        scripts.append({"title": f"{topic.capitalize()}", "content": script_content})
    return scripts

if __name__ == "__main__":
    # Example usage (for testing pakka.py independently)
    trending_on_tech = fetch_trending_topics(source="youtube", domain="Technology", max_topics=3)
    print("Trending on Technology (YouTube):", trending_on_tech)

    trending_on_reddit = fetch_trending_topics(source="reddit", max_topics=3)
    print("Trending on Reddit:", trending_on_reddit)

    google_news_headlines = fetch_trending_topics(source="google_news", max_topics=3)
    print("Google News Headlines:", google_news_headlines)

    if trending_on_tech:
        generated_scripts = generate_scripts(trending_on_tech, "medium", "english", "informative")
        print("\nGenerated Scripts:")
        for script in generated_scripts:
            print(f"\n--- {script['title']} ---\n{script['content']}")