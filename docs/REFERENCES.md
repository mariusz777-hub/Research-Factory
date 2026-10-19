# Referencje implementacyjne

Adaptery i formaty żądań zweryfikowano względem oficjalnych dokumentacji:

- OpenAI Chat Completions: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
- Gemini generateContent: https://ai.google.dev/api/generate-content
- DeepSeek Chat Completions: https://api-docs.deepseek.com/api/create-chat-completion/
- GitHub REST API: https://docs.github.com/en/rest

Nazwy modeli są konfigurowalne. Przed wdrożeniem należy potwierdzić modele dostępne na konkretnych kontach i wykonać smoke test live.

- GitHub repository search: https://docs.github.com/en/rest/search/search#search-repositories
- Reddit search listing: https://www.reddit.com/dev/api/#GET_search
- Python dynamic module loading: https://docs.python.org/3/library/importlib.html
