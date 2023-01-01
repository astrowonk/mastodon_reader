from cryptography.fernet import Fernet
from config import key

# we will be encrypting the below string.

# Instance the Fernet class with the key

key = key.encode()
fernet = Fernet(key)


# then use the Fernet class instance
# to encrypt the string string must
# be encoded to byte string before encryption
def encode(message):
    encMessage = fernet.encrypt(message.encode()).decode()
    return encMessage


def decode(encMessage):
    decMessage = fernet.decrypt(encMessage.encode()).decode()
    return decMessage
