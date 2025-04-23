import requests
import pandas as pd
import re
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
import os
import csv
from transformers import pipeline

# Load the HuggingFace sentiment analysis model
sentiment_pipeline = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")


def preprocess(text):
    text = text.lower()
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    return text


def is_lpu_related(comment):
    comment = preprocess(comment)
    return "lpu" in comment or "lovely professional" in comment or "lovely professional university" in comment


def get_sentiment_transformer(comment):
    """
    Analyzes sentiment using HuggingFace transformers.
    """
    try:
        result = sentiment_pipeline(comment[:512])[0]
        label = result['label'].upper()
        if label == "POSITIVE":
            return "POSITIVE"
        elif label == "NEGATIVE":
            return "NEGATIVE"
        else:
            return "NEUTRAL"
    except Exception as e:
        print(f"[ERROR in HuggingFace Sentiment] {e}")
        return "NEUTRAL"


def extract_comments(comment_data, all_comments):
    for comment in comment_data:
        if "body" in comment["data"]:
            all_comments.append(comment["data"]["body"])
        if "replies" in comment["data"] and isinstance(comment["data"]["replies"], dict):
            extract_comments(comment["data"]["replies"]["data"]["children"], all_comments)


def analyze_comments(data):
    comments_data = data[1]["data"]["children"]
    all_comments = []
    extract_comments(comments_data, all_comments)

    positive_comments = []
    negative_comments = []
    neutral_comments = []

    for comment_text in all_comments:
        if is_lpu_related(comment_text):
            sentiment = get_sentiment_transformer(comment_text)
            if sentiment == "POSITIVE":
                positive_comments.append(comment_text)
            elif sentiment == "NEGATIVE":
                negative_comments.append(comment_text)
            else:
                neutral_comments.append(comment_text)

    return positive_comments, negative_comments, neutral_comments, len(all_comments)


def analyze_reddit_post(request):
    if request.method != "POST":
        return render(request, "index.html")

    if "post_file" not in request.FILES:
        return JsonResponse({"error": "Please upload a CSV file."}, status=400)

    post_file = request.FILES["post_file"]
    if not post_file.name.endswith(".csv"):
        return JsonResponse({"error": "Please upload a CSV file."}, status=400)

    try:
        decoded_file = post_file.read().decode('utf-8').splitlines()
        reader = csv.reader(decoded_file)
        header = next(reader, None)
        if header:
            try:
                post_url_index = header.index("post_url")
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
                all_analysis_results.append({"error": f"Failed to analyze {post_url}: {e}"})

        request.session["analyzed_data"] = all_analysis_results
        request.session.modified = True

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
    analyzed_data = request.session.get("analyzed_data", [])
    if not analyzed_data:
        return redirect("/")

    filtered_data = [item for item in analyzed_data if "error" not in item]
    if not filtered_data:
        return HttpResponse("No valid data to export.", content_type="text/plain")

    df = pd.DataFrame(filtered_data)
    filename = request.GET.get("filename", "reddit_analysis") + ".xlsx"

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    df.to_excel(response, index=False)
    return response
