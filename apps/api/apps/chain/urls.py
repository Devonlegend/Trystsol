from django.urls import path

from . import views

app_name = "chain"

urlpatterns = [
    path("intents/pending/", views.PendingIntentsView.as_view(), name="pending-intents"),
    path("intents/<uuid:intent_id>/confirm/", views.ConfirmIntentView.as_view(), name="confirm-intent"),
    path("indexer/ingest/", views.IndexerIngestView.as_view(), name="indexer-ingest"),
    path("indexer/state/", views.IndexerStateView.as_view(), name="indexer-state"),
]
