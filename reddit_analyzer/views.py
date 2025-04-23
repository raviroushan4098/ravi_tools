import requests
import pandas as pd
import re
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
import os
from dotenv import load_dotenv
import time
load_dotenv()
import google.generativeai as genai
import csv  # Import the csv module

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

genai.configure(api_key=GEMINI_API_KEY)

def preprocess(text):
    """
    Preprocesses the input text by converting it to lowercase and removing non-alphanumeric characters.

    Args:
        text (str): The text to preprocess.

    Returns:
        str: The preprocessed text.
    """
    text = text.lower()
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    return text



def is_lpu_related(comment):
    """
    Checks if a comment is related to Lovely Professional University (LPU).

    Args:
        comment (str): The comment to check.

    Returns:
        bool: True if the comment is LPU-related, False otherwise.
    """
    comment = preprocess(comment)
    return "lpu" in comment or "lovely professional" in comment or "lovely professional university" in comment



def get_sentiment_gemini(comment):
    """
    Analyzes the sentiment of a comment using the Gemini API.  Handles potential errors and retries.

    Args:
        comment (str): The comment to analyze.

    Returns:
        str: The sentiment of the comment (POSITIVE, NEGATIVE, NEUTRAL), or "NEUTRAL" on error.
    """
    max_retries = 3
    retry_delay = 2  # Start with 2 seconds

    for attempt in range(max_retries):
        try:
            # Initialize the Gemini client
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
            # Specify the model to use.
            model = genai.GenerativeModel('gemini-1.5-flash')
            # Construct the prompt
            prompt = f"""
            Analyze the sentiment of the following comment about Lovely Professional University (LPU). Respond with one of the following sentiments: POSITIVE, NEGATIVE, or NEUTRAL. Do not provide explanations or additional text.

            Comment: "{comment}"
            Sentiment:
            """
            response = model.generate_content(prompt)
            # Extract and normalize sentiment
            sentiment = response.text.strip().upper()
            print(f"[Gemini Response] {sentiment}")
            # Validate the sentiment
            if sentiment in ["POSITIVE", "NEGATIVE", "NEUTRAL"]:
                return sentiment
            else:
                return "NEUTRAL"

        except Exception as e:
            print(f"[ERROR in Gemini API call] {e}")
            if attempt < max_retries - 1:  # Only retry if not the last attempt
                if "429" in str(e):  # Check for rate limit error
                    print(f"Rate limit exceeded. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    return "NEUTRAL" # Return default for other errors
            else:
                return "NEUTRAL" #Ran out of retries.



def extract_comments(comment_data, all_comments):
    """
    Extracts comments from the Reddit comment data, including replies.

    Args:
        comment_data (list): A list of comment data from the Reddit API response.
        all_comments (list): A list to store the extracted comments.
    """
    for comment in comment_data:
        if "body" in comment["data"]:
            comment_text = comment["data"]["body"]
            all_comments.append(comment_text)

        if "replies" in comment["data"] and isinstance(comment["data"]["replies"], dict):
            extract_comments(comment["data"]["replies"]["data"]["children"], all_comments)



def analyze_comments(data):
    """
    Analyzes the sentiment of the extracted comments and categorizes them.

    Args:
        data (dict): The Reddit API response containing the comments.

    Returns:
        tuple: A tuple containing lists of positive, negative, and neutral comments, and the total number of comments.
    """
    comments_data = data[1]["data"]["children"]
    all_comments = []
    extract_comments(comments_data, all_comments)

    positive_comments = []
    negative_comments = []
    neutral_comments = []

    for comment_text in all_comments:
        if is_lpu_related(comment_text):
            sentiment = get_sentiment_gemini(comment_text)
            if sentiment == "POSITIVE":
                positive_comments.append(comment_text)
            elif sentiment == "NEGATIVE":
                negative_comments.append(comment_text)
            else:
                neutral_comments.append(comment_text)

    return positive_comments, negative_comments, neutral_comments, len(all_comments)



def analyze_reddit_post(request):
    """
    Handles the analysis of Reddit posts from a CSV file upload.

    Args:
        request (HttpRequest): The Django HTTP request object.

    Returns:
        JsonResponse: A JSON response containing the analysis results.
    """
    if request.method != "POST":
        return render(request, "index.html")  # Handle GET requests

    if "post_file" not in request.FILES:
        return JsonResponse({"error": "Please upload a CSV file."}, status=400)

    post_file = request.FILES["post_file"]
    if not post_file.name.endswith(".csv"):
        return JsonResponse({"error": "Please upload a CSV file."}, status=400)

    try:
        decoded_file = post_file.read().decode('utf-8').splitlines()
        reader = csv.reader(decoded_file)
        header = next(reader, None)  # Read the first row as the header
        if header:
            try:
                post_url_index = header.index("post_url")  # Find the index of the 'post_url' column
            except ValueError:
                return JsonResponse({"error": "CSV file must contain a column named 'post_url'"}, status=400)
        else:
            return JsonResponse({"error": "CSV file is empty"}, status=400)

        links = [row[post_url_index] for row in reader if row]


        all_analysis_results = []
        for post_url in links:
            if not post_url.strip():
                continue

            json_url = post_url.rstrip("/") + ".json"
            headers = {"User-Agent": "Mozilla/5.0"}
            try:
                response = requests.get(json_url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                post_data = data[0]["data"]["children"][0]["data"]

                title = post_data["title"]
                upvotes = post_data["ups"]
                comments_count = post_data["num_comments"]

                positive_comments, negative_comments, neutral_comments, total_comments = analyze_comments(data)

                analysis_result = {
                    "Title": title,
                    "URL": post_url,
                    "Upvotes": upvotes,
                    "Comments Count": comments_count,
                    "Positive Sentiments": len(positive_comments),
                    "Negative Sentiments": len(negative_comments),
                    "Neutral Sentiments": len(neutral_comments),
                    "Positive Comments": positive_comments,
                    "Negative Comments": negative_comments,
                }
                all_analysis_results.append(analysis_result)

            except requests.RequestException as e:
                print(f"Failed to fetch or analyze {post_url}: {e}")
                all_analysis_results.append({"error": f"Failed to analyze {post_url}: {e}"}) # Store error if analysis fails

        request.session["analyzed_data"] = all_analysis_results
        request.session.modified = True
        # Prepare the data for JSON response.  Include total counts.
        total_posts = len(all_analysis_results)
        positive_sentiments = sum(item.get("Positive Sentiments", 0) for item in all_analysis_results)
        negative_sentiments = sum(item.get("Negative Sentiments", 0) for item in all_analysis_results)
        neutral_sentiments = sum(item.get("Neutral Sentiments", 0) for item in all_analysis_results)
        return JsonResponse({
            "message": f"Analyzed {total_posts} posts.",
            "total_posts": total_posts,
            "positive_sentiments": positive_sentiments,
            "negative_sentiments": negative_sentiments,
            "neutral_sentiments": neutral_sentiments,
        })
    except Exception as e:
        return JsonResponse({"error": f"An error occurred: {e}"}, status=500)

def export_to_excel(request):
    """
    Exports the analyzed Reddit post data to an Excel file.

    Args:
        request (HttpRequest): The Django HTTP request object.

    Returns:
        HttpResponse: An HTTP response containing the Excel file.
    """
    analyzed_data = request.session.get("analyzed_data", [])
    if not analyzed_data:
        return redirect("/")  # Redirect to the main page if no data

    # Filter out any error entries before creating the DataFrame
    filtered_data = [
        item for item in analyzed_data if "error" not in item
    ]

    if not filtered_data:
        return HttpResponse("No valid data to export.", content_type="text/plain")

    df = pd.DataFrame(filtered_data)
    filename = request.GET.get("filename", "reddit_analysis") + ".xlsx"

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    df.to_excel(response, index=False)
    return response
