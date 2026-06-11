class KnowledgeBaseService:
    def __init__(self):
        self.data = {
            "who was einstein": (
                "Albert Einstein was a theoretical physicist best known "
                "for developing the theory of relativity."
            ),
            "what is python": (
                "Python is a high-level, interpreted programming language "
                "known for readability and versatility."
            ),
            "what is artificial intelligence": (
                "Artificial intelligence is the simulation of human intelligence "
                "in machines."
            ),
            "who invented the telephone": (
                "Alexander Graham Bell is commonly credited with inventing the telephone."
            )
        }

    def answer(self, question: str):
        question = question.lower().strip()
        return self.data.get(question)