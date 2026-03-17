from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions

from .models import Recommendation
from .serializers import RecommendationSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["recommendations"],
        responses={
            200: RecommendationSerializer(many=True),
            401: OpenApiResponse(description="Unauthorized"),
        },
    ),
)
class RecommendationListView(generics.ListAPIView):
    serializer_class = RecommendationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Recommendation.objects.filter(user=self.request.user)
