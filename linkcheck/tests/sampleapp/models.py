from django.db import models


class Book(models.Model):
    title       = models.CharField(max_length=50)
    description = models.TextField()

    def get_absolute_url(self):
        return "/book/%s/" % self.id


class Author(models.Model):
    # This model has purposefully no get_absolute_url
    name = models.CharField(max_length=50)
    website = models.URLField(blank=True)
