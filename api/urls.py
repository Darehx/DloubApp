from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FormResponseViewSet

router = DefaultRouter()
router.register('response', FormResponseViewSet)

urlpatterns = [
    
    path('', include(router.urls)),
   path('response/bulk_create/', FormResponseViewSet.as_view({'post': 'bulk_create'}), name='bulk-create-response'), 
]