"""RAG orchestration layer that builds prompts and queries the local LLM."""

from langchain_ollama import ChatOllama

from backend.components.RetrieverService.service import RetrieverService


class RAGApplication:
    """Answers user questions using retrieved context from indexed documents."""

    def __init__(
        self,
        retriever_service: RetrieverService,
        model_name: str = "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0",
        base_url: str | None = None,
    ) -> None:
        """Initializes retrieval dependency and chat model client.

        Args:
            retriever_service: Service used to fetch context chunks.
            model_name: Name of the Ollama chat model.
            base_url: Optional Ollama endpoint override.
        """
        self.retriever_service = retriever_service
        self.model_name = model_name
        self.base_url = base_url
        kwargs = {"model": model_name}
        if base_url:
            kwargs["base_url"] = base_url
        self.llm = ChatOllama(**kwargs)

    def ask(self, question: str, k: int | None = None) -> str:
        """Retrieves context for a question and generates an answer.

        Args:
            question: User question in natural language.
            k: Optional retrieval size override.

        Returns:
            Generated answer text.
        """
        self._validate_question(question)
        context = self.retriever_service.retrieve_context(query=question, k=k)
        return self.ask_with_context(question=question, context=context)

    def ask_with_context(self, question: str, context: str, context_kind: str = "raw") -> str:
        """Generates an answer from a precomputed context string.

        Args:
            question: User question in natural language.
            context: Prepared context string for the model prompt.
            context_kind: Context strategy label influencing prompt template.

        Returns:
            Generated answer text or fallback response when context is empty.
        """
        self._validate_question(question)
        if not context.strip():
            return "Nie wiem. Nie znalazlem odpowiedzi w dostepnych dokumentach."

        prompt = self._build_prompt(
            question=question,
            context=context,
            context_kind=context_kind,
        )
        response = self.llm.invoke(prompt)
        return response.content.strip()

    def _build_prompt(self, question: str, context: str, context_kind: str = "raw") -> str:
        # Buduje prompt, ktory ogranicza odpowiedz modelu do podanego kontekstu.
        if context_kind == "structured":
            return self._build_structured_prompt(question=question, context=context)

        if context_kind == "hybrid":
            return self._build_hybrid_prompt(question=question, context=context)

        return f"""
Jestes asystentem RAG. Odpowiadaj w jezyku polskim.

Zasady:
- Odpowiadaj wylacznie na podstawie sekcji KONTEKST.
- Jesli w KONTEKSCIE nie ma odpowiedzi, napisz: "Nie wiem. Nie znalazlem odpowiedzi w dostepnych dokumentach."
- Nie wymyslaj faktow spoza dokumentow.
- Odpowiedz ma byc krotka, konkretna i czytelna.

KONTEKST:
{context}

PYTANIE:
{question}

ODPOWIEDZ:
""".strip()

    def _build_structured_prompt(self, question: str, context: str) -> str:
        # Prompt specjalizowany do odpowiedzi opartych o fakty i relacje.
        return f"""
Jestes asystentem RAG dla dokumentacji testowej. Odpowiadaj po polsku.

Zasady:
- Odpowiadaj tylko na podstawie sekcji KONTEKST.
- Traktuj [FACTS_JSON] jako glowne zrodlo danych faktograficznych.
- Traktuj [RELATIONSHIPS_JSON] jako mapy do przechodzenia relacji Bug -> Krok -> Test.
- Jesli brak danych, napisz: "Nie wiem. Nie znalazlem odpowiedzi w dostepnych dokumentach."
- Nie wymyslaj informacji spoza kontekstu.
- Odpowiedz ma byc krotka, konkretna i czytelna.

KONTEKST:
{context}

PYTANIE:
{question}

ODPOWIEDZ:
""".strip()

    def _build_hybrid_prompt(self, question: str, context: str) -> str:
        # Prompt hybrydowy: fakty sa pierwsze, surowe fragmenty to fallback.
        return f"""
Jestes asystentem RAG dla dokumentacji testowej. Odpowiadaj po polsku.

Zasady:
- Odpowiadaj tylko na podstawie sekcji KONTEKST.
- W pierwszej kolejnosci uzywaj [FACTS_JSON] i [RELATIONSHIPS_JSON].
- [RAW_SNIPPETS] traktuj jako zrodlo pomocnicze, gdy fakt nie jest kompletny.
- Jesli brak danych, napisz: "Nie wiem. Nie znalazlem odpowiedzi w dostepnych dokumentach."
- Nie wymyslaj informacji spoza kontekstu.
- Odpowiedz ma byc krotka, konkretna i czytelna.

KONTEKST:
{context}

PYTANIE:
{question}

ODPOWIEDZ:
""".strip()

    def _validate_question(self, question: str) -> None:
        # Sprawdza, czy pytanie uzytkownika nie jest puste.
        if not question or not question.strip():
            raise ValueError("Pytanie nie moze byc puste")
