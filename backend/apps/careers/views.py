from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CareerPathway


class PathwayListView(APIView):
    """Career pathway catalogue (knowledge-graph nodes), Phase 1.

    Public (AllowAny): the catalogue is non-personalised reference data used
    by the frontend and by Stage 1 of the recommendation cascade (Phase 4).
    """

    permission_classes = [AllowAny]

    def get(self, request):
        pathways = [
            {
                "id": p.external_id,
                "name": p.name,
                "category": p.category,
                "description": p.description,
                "prerequisites": [
                    {"skill": r.skill, "min_level": r.min_level} for r in p.prerequisites
                ],
                "typical_courses": p.typical_courses,
            }
            for p in CareerPathway.objects.order_by("external_id")
        ]
        return Response({"count": len(pathways), "pathways": pathways})


class CareerPredictionView(APIView):
    """Phase 5: ensemble prediction — probability distribution + top features."""

    def get(self, request):
        return Response({"detail": "Not implemented (Phase 5)"}, status=501)
