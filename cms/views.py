from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from frontend.views import limited_auth
from support.models import ContactMessage
from core.models import SiteSetting
from .models import BlogPost, FAQ, Page


def published(model):
    return model.objects.filter(published=True, published_at__lte=timezone.now())


def blog_posts(params):
    rows = published(BlogPost).select_related("category").prefetch_related("tags")
    if params.get("category"):
        rows = rows.filter(category__slug=params["category"])
    if params.get("tag"):
        rows = rows.filter(tags__slug=params["tag"])
    return rows


def blog(request):
    page = Paginator(blog_posts(request.GET), 12).get_page(request.GET.get("page"))
    return render(request, "cms/blog.html", {"page": page})


def article(request, slug, model=BlogPost):
    item = get_object_or_404(published(model), slug=slug)
    return render(request, "cms/article.html", {"item": item, "blog": model is BlogPost})


def faq(request):
    return render(request, "cms/faq.html", {"entries": FAQ.objects.filter(active=True).select_related("category")
                  .order_by("category__name", "pk")})


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ("name", "email", "subject", "message")
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}


@limited_auth
def contact(request):
    form = ContactForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        form.save()
        messages.success(request, "Your message has been received.")
        return redirect("contact")
    intro = SiteSetting.objects.filter(key="contact_intro").values_list("value", flat=True).first()
    return render(request, "cms/contact.html", {"form": form, "intro": intro})
