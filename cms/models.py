from django.conf import settings
from django.db import models
from django.utils import timezone


class PublishedContent(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180, unique=True, allow_unicode=True)
    content = models.TextField()
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True
        ordering = ["-published_at", "pk"]

    def __str__(self):
        return self.title


class Page(PublishedContent):
    pass


class BlogLabel(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, allow_unicode=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class BlogCategory(BlogLabel):
    pass

class BlogTag(BlogLabel):
    pass


class BlogPost(PublishedContent):
    category = models.ForeignKey(BlogCategory, on_delete=models.PROTECT)
    tags = models.ManyToManyField(BlogTag, blank=True)


class FAQCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class FAQ(models.Model):
    category = models.ForeignKey(FAQCategory, on_delete=models.PROTECT)
    question = models.CharField(max_length=250)
    answer = models.TextField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.question
