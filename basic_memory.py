######################
# Agente Basico De I #
# Memoria            #
######################

# Importacion para el manejo de la memoria en formato fifo # 
from collections import deque

class BasicMemory:
    
    def __init__(self, max_messages:int=10):
        self.history = deque(maxlen=max_messages)
        
    def add(self, role:str, text:str):
        self.history.append({"role": role, "content": text})
    
    def messages(self):
        return list(self.history)