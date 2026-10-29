"""Chat ID normalisation (accepts Green-API style ids too)."""


def normalize(chat_id: str) -> str:
    cid = str(chat_id).strip()
    if cid.endswith("@c.us"):
        cid = cid[:-5] + "@s.whatsapp.net"
    if "@" in cid:
        return cid
    digits = "".join(ch for ch in cid if ch.isdigit())
    if not digits:
        raise ValueError(f"invalid chat id: {chat_id!r}")
    return f"{digits}@s.whatsapp.net"


if __name__ == "__main__":
    assert normalize("+31 6 12345678") == "31612345678@s.whatsapp.net"
    assert normalize("31612345678@c.us") == "31612345678@s.whatsapp.net"
    assert normalize("120363@g.us") == "120363@g.us"
    try:
        normalize("abc")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    print("ok")
