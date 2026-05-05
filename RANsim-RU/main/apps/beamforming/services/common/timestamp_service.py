from django.utils import timezone


class TimestampService:
    @staticmethod
    def get_current_timestamp():
        return timezone.now()
