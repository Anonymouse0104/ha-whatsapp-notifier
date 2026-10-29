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


def accepts(chat: str, only_replies: bool, m: dict) -> bool:
    """Should a chat's Last message sensor take this incoming message?"""
    return normalize(m["chat_id"]) == chat and (not only_replies or bool(m.get("quoted_from_me")))


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
    m = {"chat_id": "120363@g.us", "quoted_from_me": False}
    assert accepts("120363@g.us", False, m)
    assert not accepts("120363@g.us", True, m)
    assert accepts("120363@g.us", True, {**m, "quoted_from_me": True})
    assert not accepts("999@g.us", False, m)
    print("ok")
