from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    """Phase 3: validation for student registration (password hashing, dup-email check)."""

    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=200)
    password = serializers.CharField(min_length=8, write_only=True)
    programme = serializers.CharField(required=False, allow_blank=True, default="")
    year_of_study = serializers.IntegerField(required=False, min_value=1, max_value=6)


class ProfileSerializer(serializers.Serializer):
    """Phase 3: read/update serialisation of StudentProfile documents."""

    email = serializers.EmailField(read_only=True)
    full_name = serializers.CharField()
    programme = serializers.CharField(required=False, allow_blank=True)
    year_of_study = serializers.IntegerField(required=False, min_value=1, max_value=6)
