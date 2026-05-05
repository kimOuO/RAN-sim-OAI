from django.apps import AppConfig


class RanSignalConfig(AppConfig):
    name = "main.apps.ran_signal"
    label = "ran_signal"

    def ready(self):
        # Sionna engine 啟動時讀 scene_config.json，暫不在此觸發；交由第一次 compute 請求延遲初始化，
        # 避免 Django management command (migrate / shell) 也拖 GPU。
        return
