"""Thin proxy endpoints delegating to the careermind_llm package (Part A, NFR07)."""
from rest_framework.response import Response
from rest_framework.views import APIView


class ChatView(APIView):
    """Phase 7: conversational career guidance. Delegates to
    careermind_llm.chat.GuidanceChat with student context (FES, profile,
    current recommendations) as grounding."""

    def post(self, request):
        return Response({"detail": "Not implemented (Phase 7)"}, status=501)


class QuizGenerateView(APIView):
    """Phase 7: LLM-generated self-assessment quiz items per skill domain."""

    def post(self, request):
        return Response({"detail": "Not implemented (Phase 7)"}, status=501)
