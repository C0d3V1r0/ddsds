# - Реагирование на обнаруженные угрозы: решение о блокировке или логировании
class Responder:
    def __init__(self, auto_block: bool = True):
        self.auto_block = auto_block

    def decide(self, event: dict) -> dict:
        """- Принимает решение на основе severity и наличия IP"""
        severity = event.get("severity", "low")
        source_ip = event.get("source_ip", "")

        # - Блокируем только high/critical при включённом auto_block и наличии IP
        if severity in ("high", "critical") and self.auto_block and source_ip:
            return {
                "action": "block",
                "ip": source_ip,
                "highlight": severity == "critical",
            }

        return {"action": "log"}
