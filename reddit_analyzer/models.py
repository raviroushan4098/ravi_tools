from django.db import models

class AnalysisResult(models.Model):
    title = models.CharField(max_length=500)
    url = models.URLField(db_index=True)  # Add db_index=True here
    upvotes = models.IntegerField(default=0)
    comments_count = models.IntegerField(default=0)
    positive_sentiment_count = models.IntegerField(default=0)
    negative_sentiment_count = models.IntegerField(default=0)
    neutral_sentiment_count = models.IntegerField(default=0)
    total_comments_analyzed = models.IntegerField(default=0)
    analysis_timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title