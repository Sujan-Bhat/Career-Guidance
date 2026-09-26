from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=200)
    password = serializers.CharField(min_length=8, write_only=True)
    programme = serializers.CharField(required=False, allow_blank=True, default="")
    year_of_study = serializers.IntegerField(required=False, min_value=1, max_value=6, default=3)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ProfileSerializer(serializers.Serializer):
    """Read/update serialisation of StudentProfile documents."""

    email = serializers.EmailField(read_only=True)
    full_name = serializers.CharField(required=False)
    programme = serializers.CharField(required=False, allow_blank=True)
    year_of_study = serializers.IntegerField(required=False, min_value=1, max_value=6)
    academic_records = serializers.SerializerMethodField()
    skill_assessments = serializers.SerializerMethodField()
    career_preferences = serializers.SerializerMethodField()

    def _embedded(self, obj, field):
        return [
            {k: v for k, v in item.to_mongo().to_dict().items() if k != "_id"}
            for item in getattr(obj, field)
        ]

    def get_academic_records(self, obj):
        return self._embedded(obj, "academic_records")

    def get_skill_assessments(self, obj):
        return self._embedded(obj, "skill_assessments")

    def get_career_preferences(self, obj):
        return self._embedded(obj, "career_preferences")
