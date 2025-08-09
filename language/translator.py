import json
import os

class Translator:
    def __init__(self, lang="English"):
        self.lang = lang.lower()
        self.translations = {}
        self.load_language()

    def load_language(self):
        path = os.path.join(os.path.dirname(__file__), f"{self.lang}.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.translations = json.load(f)
        except FileNotFoundError:
            self.translations = {}

    def translate(self, text):
        return self.translations.get(text, text)  # fallback to original if not found
