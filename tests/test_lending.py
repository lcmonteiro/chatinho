"""HookSample and HookCredential: what the frontend lends to whoever answers."""

import pytest

from chatinho import (
    ChatSession,
    CredentialUnavailable,
    HookCredential,
    HookServeCredential,
    HookSample,
    HookServeSample,
    MessageID,
    SamplingUnavailable,
    Secret,
    connector,
    frontend,
    require,
)
from conftest import driven


@connector("pensador")
@require(HookSample)
@require(HookCredential)
class _Pensador:
    pass


@frontend("lender")
@require(HookServeSample)
@require(HookServeCredential)
class _Lender:
    def __init__(self):
        self.calls = []
        self.lent  = {}

    async def serve_sample(self, msg_id, messages, max_tokens, system):
        self.calls.append((msg_id, messages, max_tokens, system))
        return "completed"

    async def serve_credential(self, msg_id, name):
        try:
            return self.lent[msg_id][name].reveal()
        except KeyError:
            raise CredentialUnavailable(name) from None


async def test_the_frontend_serves_the_sample():
    lender, peer = _Lender(), _Pensador()
    session = ChatSession(frontend=lender, connectors=[peer])
    await session.start()
    msg_id  = MessageID.new()
    text    = await peer.sample(msg_id, [{"role": "user", "content": "hi"}], max_tokens=5)
    assert text == "completed"
    assert lender.calls == [(msg_id, [{"role": "user", "content": "hi"}], 5, None)]
    await session.close()


async def test_nobody_serves_samples():
    peer = _Pensador()
    session, _ = await driven(connectors=[peer])
    with pytest.raises(SamplingUnavailable):
        await peer.sample(MessageID.new(), [{"role": "user", "content": "hi"}])
    await session.close()


async def test_a_lent_credential_is_served_for_its_message_only():
    lender, peer = _Lender(), _Pensador()
    session = ChatSession(frontend=lender, connectors=[peer])
    await session.start()
    msg_id = MessageID.new()
    lender.lent[msg_id] = {"llm": Secret("sk-test")}
    assert await peer.credential(msg_id, "llm") == "sk-test"
    with pytest.raises(CredentialUnavailable):
        await peer.credential(MessageID.new(), "llm")
    await session.close()


async def test_nobody_lends_credentials():
    peer = _Pensador()
    session, _ = await driven(connectors=[peer])
    with pytest.raises(CredentialUnavailable):
        await peer.credential(MessageID.new(), "llm")
    await session.close()


def test_a_secret_never_shows_itself():
    secret = Secret("sk-test")
    assert "sk-test" not in repr(secret) and "sk-test" not in str(secret)
    assert "sk-test" not in "%s %r" % (secret, secret)
    assert secret.reveal() == "sk-test"
