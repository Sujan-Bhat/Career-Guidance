import os
import requests
from django.core.management.base import BaseCommand
from apps.courses.models import CodingProblem

LIST_QUERY = """
query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
  problemsetQuestionList: questionList(
    categorySlug: $categorySlug
    limit: $limit
    skip: $skip
    filters: $filters
  ) {
    questions: data {
      frontendQuestionId: questionFrontendId
      title
      titleSlug
      difficulty
      paidOnly: isPaidOnly
      topicTags { name }
    }
  }
}
"""


class Command(BaseCommand):
    help = "Fast-import all free LeetCode problem headers into MongoDB"

    def add_arguments(self, parser):
        parser.add_argument("--max", type=int, default=0, help="Max problems to import (0 = all)")

    def handle(self, *args, **options):
        url = os.getenv("LEETCODE_GRAPHQL_URL", "https://leetcode.com/graphql")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://leetcode.com",
        }
        max_items = options["max"]
        skip = 0
        imported = 0

        while True:
            res = requests.post(
                url,
                json={"query": LIST_QUERY, "variables": {"categorySlug": "", "skip": skip, "limit": 100, "filters": {}}},
                headers=headers,
                timeout=15,
            )
            res.raise_for_status()
            questions = res.json()["data"]["problemsetQuestionList"]["questions"]
            if not questions:
                break

            for q in questions:
                if q["paidOnly"]:
                    continue
                CodingProblem.objects(slug=q["titleSlug"]).update_one(
                    set__question_id=q["frontendQuestionId"],
                    set__title=q["title"],
                    set__difficulty=q["difficulty"],
                    set__topic_tags=[t["name"] for t in q["topicTags"]],
                    upsert=True,
                )
                imported += 1
                if max_items and imported >= max_items:
                    self.stdout.write(self.style.SUCCESS(f"Imported {imported} problems."))
                    return

            skip += 100

        self.stdout.write(self.style.SUCCESS(f"Imported {imported} problems."))