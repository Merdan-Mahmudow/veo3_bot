from __future__ import annotations
from typing import Optional, Sequence
from openai import AsyncOpenAI
from config import ENV

class PromptAI:
    """
    Генератор промптов для текст-видео. Возвращает ровно ОДИН промпт (строку).
    """
    def __init__(self):
        env = ENV()
        self.client = AsyncOpenAI(api_key=env.OPENAI_API_KEY)
        self.model = env.OPENAI_MODEL

    async def suggest_prompt(
        self,
        brief: str,
        clarifications: Optional[Sequence[str]] = None,
        attempt: int = 1,
        previous_prompt: Optional[str] = None,
        aspect_ratio: str = "16:9",
    ) -> str:
        """
        brief           — краткое описание пользователя
        clarifications  — список уточнений (каждые 2 попытки)
        attempt         — номер попытки (1..N)
        previous_prompt — последний предложенный вариант (для модификации)
        """
        clar_text = ""
        if clarifications:
            clar_text = "Уточнения пользователя: " + "; ".join(clarifications)

        system = (
            "Ты опытный Prompt Engineer для генерации коротких видеороликов в VEO 3 (text-to-video).\n"
            "Задача: составить один чёткий, сжатый и исполнимый промпт на русском. "
            "Без преамбулы, без пояснений — только сам промпт.\n"
            "Требования: укажи визуальный стиль (2–4 слова), сцену/объекты, атмосферу/эмоции, "
            "движение камеры (1–2 приёма) и временные/сеттинговые детали. "
            f"Соотношение сторон: {aspect_ratio}. Избегай упоминания брендов и копирайта."
        )

        user = (
            f"Краткое ТЗ пользователя: {brief}\n"
            f"{clar_text}\n"
            f"Номер попытки: {attempt}.\n"
        )

        if previous_prompt:
            # Просим слегка изменить, а не писать «совершенно другой» — чтобы не ускакать от запроса
            user += (
                "Предыдущий вариант промпта оказался неподходящим. "
                "Сгенерируй новый вариант, немного изменённый относительно предыдущего: "
                "измени словарь, конкретику сцены, ракурс/движение камеры или настроение, "
                "но сохрани первоначальную идею. Не больше 1–2 предложений.\n"
                f"Предыдущий промпт: {previous_prompt}\n"
            )
        else:
            user += "Сгенерируй 1 лаконичный промпт (1–2 предложения)."

        resp = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.8 if attempt > 1 else 0.6,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        # Уберём «Prompt:» и прочие префиксы, если модель добавит
        for prefix in ("Промпт:", "Prompt:", "Промпт -", "Prompt -"):
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
        return text
