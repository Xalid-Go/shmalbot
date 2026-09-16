# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import logging
import os

logger = logging.getLogger(__name__)

# Fallback neutral prompt for public repository visibility
DEFAULT_DIGITAL_TWIN_PROMPT = (
    "Ты — личный помощник в Telegram. Отвечай коротко, по-человечески, 1-2 предложениями, "
    "без канцелярита и без точек на конце последнего предложения. Будь дружелюбным и естественным. "
    "Если просят нарисовать: отвечай 'ща нарисую' или 'напиши нарисуй [что] и сделаю'. "
    "Никогда не пиши системных фраз вроде 'вы вошли в систему' или 'я языковая модель'."
)

DEFAULT_INLINE_PROMPT_EXTRA = (
    "Ты выдаёшь быстрый, остроумный и меткий ответ в чате (1 короткая строка без точки в конце)."
)

DEFAULT_GIRLFRIEND_PROMPT = DEFAULT_DIGITAL_TWIN_PROMPT
DEFAULT_GIRLFRIEND_USERNAME = ""

# Encrypted payload containing private personas and triggers (protected with AES/HMAC-SHA256)
SECURE_PROMPTS_BUNDLE = "7QWu0G3eYwU9Cqb7pAjSE6DIYBr8/Kdxl9JUsMvpf6xkDSnlv9eWGMn2p++YufZdBX0DpAIeA/Q4/8irkZbC+vwLJ13V3d1Pfc2Qa2sueSOMn9HPz3PcWkrq5HHS3GxamGLu6dblgJHI80bnlXfmnNyWLgJXVybOBL8O9QFsu5UoaUMV7oBPTbVa/0TT3ZHTbN7jppM6/bcV0wqAKIgykFZKi0lRWcV3dwYtZF1Ywr+MdsJ63mdDDhJmtt3EipUIPj/I0KiIlUQyqx8E/xoqjF5UNagC0zQJkcIxwK76Bwctb4We6McMCVC0KfXnJm8SIG0PWSEDnJZCbKnxmMXbf/zvkP3FWtobyFCIz3OV1CPl+gHACJy0sgMfU009cuRLQZhQ3f+otxK5eY1GAP+xDc9FSLb4hpdziLLkQUZfiA8Rgk4oaUWM7IVDB1/i9rphxLpVxrmEnYOWBA+bHoGNCY/oomAabTsutTJwdiz/MnuJJ0UM/w+czKYKRNSJtR53w9wNLOvoMNOsKfhRG1yVN7U3z5Zv0GxhTFhJzi57jAOLBcE8U/Lyls1oD6kgoyOqlwGOIAuCZrpHSNhTfPec24UpAmcnjIB3+mRgtzXSExpseaQEHCDBL76DTvy3ESvkJOifwC1zEerh3UA4l3CKk/vQ67UaH5WL1X8T1tvwniXcFIUCmqkxj7n57uNcealUjWU1YyWIGlb/egAUAchieitUDQDLAT4iOIsMBtP57f0Dq35C3sit5M1NMpoG1Jxze52MSrx/Jx2h6VrMOPz8rijv/1VHdOO6nidPFleHLmKwnS7dsPJykckKTKLAS1K3r9dJLvuJ48rFu+zo1oPMdKzmWHUR4UbjqMY0gesTxQvyomxrqKkaok+MLL3sB1NFBs3C1GDSR2lmIO1I6s1DTIP8VHnv2PqODmY4L6T9SfVZGAmGL4dIXMd8+do4SjBNxzbWLlxaNlcYrHx7+u3VqN3sej8/d7orB1qSOIQFIuf2IggdqiW/6b5o2x5jNJjPm3qNHfP76is+UMwO0vlqwZJ7hJi1wC13WXS+oY9LzyLW8wBJ6hMuOoWUn3KfKhonWzVo77ri18CU/3aOf12Tu/za8H5pf2/5sEKYcoJ6XjxcQL1vzpTw5JGNKYPdk/28WuxIoZORzim2qKy74feyxjKytSxtl5rwSg14IucfOinzCvQQWIUIMk/VinD4RSwil+wphWwMO8CgRASL8Ag4pmbex7X9g/xJcki+beUdldMNzOw6idoNONvMYXRyqzSZx5JRMbeqI46p5POS3p7JKX+FjMvb1PPKpYO4eYQr3v9jedejDKw21gTHKJUVFSKyzVKdOrya4WhgcIdtjMetZSE2GvW8onziXdnf7FnWMxljXB59Kpg4+HN3QHLbVmQiprF4hsjn2TOgKRKtoBg5FVl6+6tcHbMnmsd38UGrDEl1daljpN69mNVNG5obMhDj48WO3sv5PdcljjNVny8b/Ruumm2JeytXULr9afLPbawzIrP8bzybbZTsxSj/Zzj1clgFoFknanqxvHWF6kxnDwrlwHpXSfC/YfMaHKYm/bnnmKVU4X+b6EzQFV2rbjqXwMtUpc7aaNui6uk6T4Uwdb+/LSTn7UB9HznxDEPVi7qILpLAcMw1PLLf3mshyO5ThXQEfTPZueSSRCrf6ysYVE3lgYHdnGIMHGBsQwX3WTWh52AnnwPOfY8vGgl7fuj+fI0SxjlCtLJ5F9oTYGSzO5sF+Iy8p1quUT4WnPwA2JzXmfqiyTws/fq9Jme7eSfaf+oUklaFmYPEM684Y+AiJRVuhnMMr/QDEGjwNkJObRIUzc6UE7Lb6Wdo49ACK2Jzwz3nX84eeO35aWkZeRdl9RcaxJC8aymF4vZ74/tcrTCVBiGlSM0EBZCropLKZ8IA1jYbjBRO4KmgDwxeDEWG9AdYHqUYw3aMBpono4cSK+TYRAGNlvztvNNK/+VK7egRRctvF7G37SBpcCngUcJA4DcYg/ojqpNkS830CqBR7zVIq1UkHN4wj/66oM9pzz7bXhx20YP6WTQFsqrdxlosGi+UyeqCuXPJC7vegj+HxNr8xpH6uXTOZc+oyONdM5QB+YSCweKZtvZ1FESDPoYDEuMTJUHjNzpO+CKIjaypzk2pPn3ICTymy5HUZzQnQi1MXTCklbOB71rmRrCFnzmhdXMNlhxHSfZSRg0m9d6zl6t6FZbs1bbaaw22+/SW0YkADviKtpplorEkLL4kw/bzuuESqtFkFGgrLaxPUJpmhnjdhqKP38PPfERtN+frjJRNvLaShx99Vbl1Hh8shz/Mmnskzr4kLuefBmhuIThe4lWK1zAGCqVFJ/ojVa7wTRsaBYuQtZIKjC4CgesEY44b/ytvSaDFkCtDzJhxioSpZV7CDik2HlR5AInqcDL7JXOCPIOYF5R65CiQVxIC1isgIRmouRM3pz1OjFSxrgg7f89znCvcZMSostBhElyOmdKuajeHxzhSSo0pXVbvLrG1aUTKUd+24IAhqKfW9lWmyB/AUBU/bDUmz52q2/HF6HO8Fojw3RvdWyDzzwV6r3DPFaSXV1G+dQa/zEeeCHIqq8NkrkzJ1D7c5BLrW+b++gxn8BVISdB+QKnH5UAGEvJ+qz8/ZTydaJaMDdgFbslp0t1GTaBJrh+pil9WAIzf5RQ3FXRJz4Lqlxy9RXTyzJb6uEgooUk/cF+Q/9VXDeXTutDrBOEzlShqOrrmw6+t9FlkMK93B0KsV6mRk0+B2jaTNkldFoqdPu//3afiBK/VkCgCDOWSdJPbQYhvj3OxgzjFlLKNrefGY8pep++pJqGkvFoQ36F9MZk4I9LkLld47xp+LoVttWI9/VNOyydYQnjj8RutDBOCYbOLeKbvM03sh64/ntI3bxylUBegap6ZCF55pN9iYacWkOBNLF69FhCBICDZzOf1VpTR/IpFu6gf77OV9vRkntClqHvG8xnpfWb3Qp9PryxcAicnUAXflos+g8UR6m9yAKp2IOJpi8FET6cnXN5HsFgm/yUTPA2FGPoIba9jdlwAYDQweofwMyWje02tdicTe5HNOPOsjZYc+6XThY+vd8Yt0E+n5XzDEFS21Fmn006tSLPnM9NKVH9EXZofrmpYwIMkgayAl2JQEJ6Iac2gZi3yxhvcwrltOQmMNLPP/QcawQ/kbh7Wi9Dp7cdP24o3M+OjN0HCW9rHMS19jFQ/zSEpa9/M5nfqyBF1g7npo/g7FcFbzOCiP/xaN3TAYzuNOKIjywy1qUlB+61c3KB4jKZZ+lKRaZKDiyQ89Zo+Pi6wsCZPX/baO4InPyN47TQyS9AzVdY+ejkXn+PQD0mkTRJMZ9oQr1KvA3L9JHaqN7+TgJNPxWw+d+Zf+A608n6YjRoeKd3PRhlBfQOkAKUECds4cE673u36BgwsQqcETxC19OBkP+kRFkp+GWJVQ+uL8FEEDrykYiO5DS4/r8WNmEN2Kr4edwkPojhNI9xZpMGAGVE5skL5xWA+naZt5b4P6zdN16+laaFjoWdy82aMGwuXlMmRwfxfKaAwD6QZGq5L+7C1C6fAfG9YiOoyUD0KU/ErcQW/q1+X/zAh2hm1kC/uYqfK2HCoO4+OJ5AJgg4SXDFFIkRy3bIJysm1XmhyJD68oDV+VftUgEh1MBUq8Vo2d+iHx1tHyUQNBryur2FANolM2Pd/ByUOHyKuSziua9lI99TDeipKcr2WU3VwS91m4Q/aq90Sy+Fn8gpA9unsr5So+StTZeMtw2Lh8hjmnkNhxJT6fabs4MD6pYYkzcEsyAJ720mbPsafn0x1uiTagZSwsZruimg01Xf/aWCmeK0gdOE3bw9Ky97TinPa/psv6lpXFZ+kFT9y7Mx+ebS9ZV/dgV1y2F5406c9/aWlupY2PkImn6ynYd56Hn+UimoR02elyn/6SeEUtY/56SvAmrmJ85gElNoSZOW8B2BTTgq+0ClhQDp4kYyvE2BiUe/fnE+dN/N3Os821f+DLxxLgjXA8SG3fTRxXr6Yzlw2NfeE7Ss4nc07IY9q3/LJmc9/WehOlKdSd3MvgXakN4pbKHhHuDv6IDscT7sr1oaqp9IPmFsSKK9WNtMhbBDB4XhFi4GgENA9apMQBDaTjpUz0SYHcdwgDUn1VPRZnNdMCAChrxPo5MKL8htiHsN5ExRa3Bl65VLRKXyIaZ/DXBDXRJLr7D1PaUl3o2vZPCIs7CjTazMZSjPtfMKskZGxH7rXey3PEn/x7tpUO7jGVM1X7TJPaA41fKSWTqsvDP4Jw0Tbd63LuDjFUSRLkH/3ebbLQ6K+lmRnLKVzKsn6swml7vGMCMzwENp0oBU2ExSC8hzdlDI7hM1y90JhmYFv9IqKtx8fuSP9vf/8J8UU5fvvQ/FwI/92dB4i96OwyaU+lkRgv54FGPYTDDeJiiBEAdzEF1Dkcdo4mmEjw3CC1vXGqsSnPGsJYNlGWBSRNGD3LiHSz1r8BHG5smBeqD8iUCKY0AKA0/kbB7k9FMw4xxUNwd/kJrP1vD6VSnCh3X0NkCEp3tI4d0y1QPbqZtwaft5r4YCvn8ih7RqT8jC8kGRxz7DAxJz+5lehuNbBWX/LNX5H7Jiu8NgKq5rGg063Zvk7Q2ZEbunf66LeAerx9tOik735udWXrBW3NZIlnLh9w2eNS20t5zG9/iOVUJ3fYifTAu8a0Pl4hMMvh+PVGzcnLNyE11pHtB1+6aLmTvWSXBJGYEjcvtZJ0cbzHGk252b7KLX8LKp3r/HjUSJDSnK0NWAQISPVF/kzL9CZ40+sbipABBdwSI3L9i0iRzgt4/h8f384xUFztrV8eCDnKeTKx5caKFHDhDrVrL4PzFQJnTlDm1nm8LO6x74FKUEcQMqDEtnIpneTxw4cWOUNk6g9Hl+jdwpgbrpF2vhOrtK1Ybeh7Hnoum4q9/tTR+vkjqWHR+CTb5dMdxlgHOspBif87K1JII267HCuYHXO1UcMi/9QHz/Klr6oyHW7D1Fk+YXHM1LxZqxXzQlIGGEECEQ/G8JJ9G52sxnzyqV1jtyjw9XI+ddZbQkw8LR68ilzyFNQBuiSqjpjprR5ymzfQyGd1aRAapVL0DxVQnOCmLIZeb4lVSmeWLb9iS+HVzq8qP0k2YyCxcdKoF2Wher8TRh7RmR7n/zzB+bzW3mgZAGKcrd5ZoQZsaYS+gE4ZbOBOoNI1kAIl1EQk7hFIipZlWZtlGK3c5mziLb44ZVXRhbZYmeej0Bpz6TmtQla+DyPfTGWTc2dbhfR8vA20kQXItOlk6jj/FIMlfkDUW4nNLk8mS75IE8gI+Ue39lkReyiPxR1thIQq2cTX9GdNoDGYNsXJYS214J9a+n5Z1RzxOa66Z5Gxm7/EsFm4gCEfTSSJpaLNBncxrXZ//1O0YzWN1LXP1kU0G50rPKMOiS0TtGEu1vx7AjkiprZds8rsOnQM5wDX4WyI+c0CDT6h78O9277VVdRgEtLbIQJpmI2vY95E2tSQol8J7A4vwcRdhUIlXyLXy/nf+vnDO4ywpbMf/x29CLvAKpIqOaWRIiJ0Xtxfm6coM3l8El1z6IEnU/J0P6MVAz+TcM20sfPNvQAc/QMKmP+aeb+7lAdufZ4BwKJGoA/D6I9wOJXnCah/InXvOq186cqke1mnWOVn+I6DLNJAafB4LMYgdm6ybygbUS2weLAX2IliWjnjemsIAIJbBUI0s9wxh2v9jEXbYLnX85410BwZygHTRSlJVVP8P/6l35vbKOLqth4/MI088wbPVQLwv50KONQCH2N+tC0pdfkE4NqRIk4t17mBwIfUYjh0OxVRHFlvLR6n3l/Sxf63/LkqQ2gpK09EPeyZWKr5uPfTb5GL6VnY8v1cIMB9hmvbJ/MeBHVsFS8Zg8Er400bQdTu7nHxugPWTnFq0lVl2jqkeiVr59mctUzjgBEv3kUGmWUWOnHTge3GxGIv/btiBp6vO/LlXlA+WsMbpkceeH6y+A/cL87SM0SJGQhIbRkcX+JpTDxzq7mVeBP8IOkXsGDNUl9+K80HyK5tlhINlMVat46PCZlHpzzBCxWfCtnoZG5lQJ83WOzUXPN79GF+7BtT4wePt1++h5GuzelrGLUjnoeCT0gWKgWDncUPsHkOPA0hlpeTGWEtebsHZDZGJPg7R2tOWKFOEtv6stC7R/1ldFtGhjJb0hZtEUhzRteJjHe6owev7ymod7KNi/jAtH+6SyiGSWXmV5FwaK72e+T0lpeksiAjI1gXfJ4AHyjoE4T7mOq8wO0V4MLwUc0t+zYbl2m3tiDfdfnU5x4vK2sp6XwM+REpZohJdJomQT4jWPZ8VTOI2r4DOtVRyo84pjDD0k7SE29zXFCz8or4LRKVNh1Ow/sT1qgtjiShwgBlwlgnnOSYOq6jnP3pogQbQyT37mXazrCsn0JmYN5kpoxesZ/RIh/0h+Y/HxywdQnF93gTiIZe7p/kg1R746fhg/nfU09kto2kYEKyk6zioPhWriQZdSLli9lB+D/kxS2GMbIWu6lZHiHt9jIqcL0f7iwpC69MzGEqbeFB9DmTHzyywMO54/ywBAy67lvY/OvrhKzak9m7NA6eR65tKy2A7m4/LvK6LzUhwJMU272nh3Bz9Vgyic3+13ygVD2JNrzRKnWlLjkM2H5e7Xm2pFEfxSkJNh122LQwNAmhUewSAQlSTm7cXz96sB8NbmmZC3bCJt9/A4DexeO5PeJgaKH+4qzf3so/1nJ4wowQg+hknHHcbBFAg1OA9/+Gr6s4eLMkSuKC3yRliGUG+2v0+XXfsODrFLh097bOgnTB8vqRwsBzK3R3OczuzJrWQy6aibgNBBd7RfmhKqfYqDD3O3lFbRP9hPQNAgbE9UQcnjIAe9jx2Z2PW3+BM7uhaFNNKtGmDBU5xdf4wKBeduDs4tHl6g/GploK+u00dXsi124PfRguBVEh3+zaBKij0WfMpty2VUUO4GE94gxlmkq/UbiYGIewubwVSsBKeRqJ4jjhiNg5eeFSnNHH84zLrn24COR7rsAgQ3fx6oJ40EElgiFyArvkS/Wcox05BexYKd+O0Y9gFS9BMh0lt3TH6JXoyWQvXs4SCZ+60hKmfyRn90R4+VDlFXdQEILVd+1xVhYa7oViP7BJ5XBs584lxGPi1xAWRoF+LC4MV74ryvdiaVFBETFCqIIoW87p+5XviCKDV3FoJdDIqBimgwG6NlKO/88KKMItK3GhnjAGhewsH5LClKiMeE5lH40I9j7bCO6gBfJS3vYygJNQDzd5zY3bVXhS6o4hh0oDlM5OyfMJHccDydv+/msEOzwqfa4RKYNdiY1dNKlbL3ap2QKsths3A=="


def _decrypt_bundle(token_b64: str, password: str) -> dict:
    bundle = base64.b64decode(token_b64.encode("utf-8"))
    salt = bundle[:16]
    auth_tag = bundle[16:48]
    ciphertext = bundle[48:]

    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000, dklen=32)
    expected_tag = hmac.new(key, salt + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(auth_tag, expected_tag):
        raise ValueError("Invalid secret key or corrupted data")

    keystream = bytearray()
    counter = 0
    while len(keystream) < len(ciphertext):
        block = hmac.new(key, counter.to_bytes(4, "big"), hashlib.sha256).digest()
        keystream.extend(block)
        counter += 1

    plaintext = bytes(c ^ k for c, k in zip(ciphertext, keystream[:len(ciphertext)]))
    return json.loads(plaintext.decode("utf-8"))


def _load_prompts():
    secret_key = os.getenv("APP_SECRET_KEY", "").strip()
    decrypted = {}

    if secret_key:
        try:
            decrypted = _decrypt_bundle(SECURE_PROMPTS_BUNDLE, secret_key)
            logger.info("Secure persona prompts decrypted and loaded")
        except Exception as e:
            logger.warning("Could not decrypt secure prompts bundle: %s. Using default/env prompts.", e)

    # Environment variables take top precedence, followed by decrypted bundle, then defaults
    twin = os.getenv("DIGITAL_TWIN_PROMPT") or decrypted.get("DIGITAL_TWIN_PROMPT") or DEFAULT_DIGITAL_TWIN_PROMPT
    inline = os.getenv("INLINE_PROMPT_EXTRA") or decrypted.get("INLINE_PROMPT_EXTRA") or DEFAULT_INLINE_PROMPT_EXTRA
    gf_username = (
        os.getenv("GIRLFRIEND_USERNAME")
        or decrypted.get("GIRLFRIEND_USERNAME")
        or DEFAULT_GIRLFRIEND_USERNAME
    ).lower().lstrip("@")
    gf_prompt = os.getenv("GIRLFRIEND_PROMPT") or decrypted.get("GIRLFRIEND_PROMPT") or DEFAULT_GIRLFRIEND_PROMPT

    return twin, inline, gf_username, gf_prompt


DIGITAL_TWIN_PROMPT, INLINE_PROMPT_EXTRA, GIRLFRIEND_USERNAME, GIRLFRIEND_PROMPT = _load_prompts()
