from common.chatbi.xpack_stub import chatbi_decrypt_impl, chatbi_encrypt_impl

async def chatbi_decrypt(text: str) -> str:
    return await chatbi_decrypt_impl(text)

async def chatbi_encrypt(text: str) -> str:
    return await chatbi_encrypt_impl(text)

