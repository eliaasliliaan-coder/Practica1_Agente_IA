#######################
# Agente Basico De IA #
# Agente              #
#######################

from dotenv import load_dotenv
from groq import Groq
import os
from basic_memory import BasicMemory

load_dotenv()

MEMORY_MAX_MESSAGES = 10

api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key)
memory = BasicMemory(max_messages=MEMORY_MAX_MESSAGES)

print("Agente IA")

while True:

    user_text = input("Tú: ").strip()
    
    if not user_text:
        continue

    if user_text.lower() in ("exit","salir"):
        print("Hasta luego!")
        break

    # Obtener memoria
    messages = memory.messages()
    
    messages.append({"role": "user", "content": user_text})

    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages
    )

    msg = resp.choices[0].message
    assistant_text = msg.content or ""
    print(f"Agente: {assistant_text}")

    # Actualizar la memoria
    memory.add("user",user_text)
    memory.add("assistant", assistant_text)