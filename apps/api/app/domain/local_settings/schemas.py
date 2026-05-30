from typing import Literal

from pydantic import BaseModel


AnswerStyle = Literal["concise", "socratic", "exam_review", "code_tutor"]


class LocalAISettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    web_search_default_enabled: bool | None = None
    answer_style: AnswerStyle | None = None


class LocalAISettingsResponse(BaseModel):
    llm_provider: str = "deterministic"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    llm_api_key_masked: str = ""
    web_search_default_enabled: bool = False
    answer_style: AnswerStyle = "concise"


class LocalAISettings(BaseModel):
    llm_provider: str = "deterministic"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    llm_api_key: str = ""
    web_search_default_enabled: bool = False
    answer_style: AnswerStyle = "concise"

    def to_response(self) -> LocalAISettingsResponse:
        return LocalAISettingsResponse(
            llm_provider=self.llm_provider,
            llm_base_url=self.llm_base_url,
            llm_model=self.llm_model,
            llm_api_key_masked="********" if self.llm_api_key else "",
            web_search_default_enabled=self.web_search_default_enabled,
            answer_style=self.answer_style,
        )
