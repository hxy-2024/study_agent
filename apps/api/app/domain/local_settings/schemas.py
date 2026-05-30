from typing import Literal

from pydantic import BaseModel, Field


AnswerStyle = Literal["concise", "socratic", "exam_review", "code_tutor"]
WebSearchProvider = Literal["duckduckgo", "tavily"]
Locale = Literal["en-US", "zh-CN"]


class LocalAISettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    available_models: list[str] | None = None
    llm_api_key: str | None = None
    web_search_default_enabled: bool | None = None
    web_search_provider: WebSearchProvider | None = None
    tavily_api_key: str | None = None
    answer_style: AnswerStyle | None = None
    locale: Locale | None = None
    main_agent_system_prompt: str | None = None
    session_tutor_system_prompt: str | None = None
    chapter_mentor_system_prompt: str | None = None


class LocalAISettingsResponse(BaseModel):
    llm_provider: str = "deterministic"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    available_models: list[str] = Field(default_factory=list)
    llm_api_key: str = ""
    llm_api_key_masked: str = ""
    web_search_default_enabled: bool = False
    web_search_provider: WebSearchProvider = "duckduckgo"
    tavily_api_key: str = ""
    tavily_api_key_masked: str = ""
    answer_style: AnswerStyle = "concise"
    locale: Locale = "zh-CN"
    main_agent_system_prompt: str = ""
    session_tutor_system_prompt: str = ""
    chapter_mentor_system_prompt: str = ""


class LocalAISettings(BaseModel):
    llm_provider: str = "deterministic"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    available_models: list[str] = Field(default_factory=list)
    llm_api_key: str = ""
    web_search_default_enabled: bool = False
    web_search_provider: WebSearchProvider = "duckduckgo"
    tavily_api_key: str = ""
    answer_style: AnswerStyle = "concise"
    locale: Locale = "zh-CN"
    main_agent_system_prompt: str = ""
    session_tutor_system_prompt: str = ""
    chapter_mentor_system_prompt: str = ""

    def to_response(self) -> LocalAISettingsResponse:
        return LocalAISettingsResponse(
            llm_provider=self.llm_provider,
            llm_base_url=self.llm_base_url,
            llm_model=self.llm_model,
            available_models=self.available_models,
            llm_api_key=self.llm_api_key,
            llm_api_key_masked="********" if self.llm_api_key else "",
            web_search_default_enabled=self.web_search_default_enabled,
            web_search_provider=self.web_search_provider,
            tavily_api_key=self.tavily_api_key,
            tavily_api_key_masked="********" if self.tavily_api_key else "",
            answer_style=self.answer_style,
            locale=self.locale,
            main_agent_system_prompt=self.main_agent_system_prompt,
            session_tutor_system_prompt=self.session_tutor_system_prompt,
            chapter_mentor_system_prompt=self.chapter_mentor_system_prompt,
        )


class LocalAIModelsResponse(BaseModel):
    models: list[str] = Field(default_factory=list)
    selected_model: str = ""
