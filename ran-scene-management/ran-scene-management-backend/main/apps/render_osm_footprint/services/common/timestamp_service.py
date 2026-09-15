from django.utils import timezone


class TimestampService:
    @staticmethod
    def now():
        return timezone.now()

    @staticmethod
    def get_current_timestamp():
        return timezone.now()
