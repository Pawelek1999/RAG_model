from langchain_ollama import ChatOllama

from backend.components.retriever_service import RetrieverService


# Klasa RAGApplication laczy retriever, prompt i lokalny model LLM.
# Jej zadaniem jest odpowiedziec na pytanie uzytkownika tylko na podstawie
# kontekstu znalezionego w dokumentach zapisanych w bazie wektorowej.
class RAGApplication:
    def __init__(
        self,
        retriever_service: RetrieverService,
        model_name: str = "qwen2.5:7b",
    ) -> None:
        # Ustawia retriever oraz lokalny model Ollama uzywany do odpowiedzi.
        self.retriever_service = retriever_service
        self.model_name = model_name
        self.llm = ChatOllama(model=model_name)

    def ask(self, question: str, k: int | None = None) -> str:
        # Pobiera kontekst z dokumentow i zwraca odpowiedz modelu.
        self._validate_question(question)
        context = self.retriever_service.retrieve_context(query=question, k=k)
        return self.ask_with_context(question=question, context=context)

    def ask_with_context(self, question: str, context: str) -> str:
        # Tworzy odpowiedz z gotowego kontekstu, bez ponownego retrievalu.
        self._validate_question(question)
        if not context.strip():
            return "Nie wiem. Nie znalazlem odpowiedzi w dostepnych dokumentach."

        prompt = self._build_prompt(question=question, context=context)
        response = self.llm.invoke(prompt)
        return response.content.strip()

    def _build_prompt(self, question: str, context: str) -> str:
        # Buduje prompt, ktory ogranicza odpowiedz modelu do podanego kontekstu.
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

    def _validate_question(self, question: str) -> None:
        # Sprawdza, czy pytanie uzytkownika nie jest puste.
        if not question or not question.strip():
            raise ValueError("Pytanie nie moze byc puste")
