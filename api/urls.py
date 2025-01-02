from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FormQuestionViewSet, FormResponseViewSet

router = DefaultRouter()
router.register('question', FormQuestionViewSet)
router.register('response', FormResponseViewSet)

urlpatterns = [
    
    path('', include(router.urls)),
    
]