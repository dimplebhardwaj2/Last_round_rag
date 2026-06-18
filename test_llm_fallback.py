"""Offline tests for Groq API key fallback behavior."""

from engine.llm import FallbackChatGroq


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def invoke(self, *args, **kwargs):
        self.calls += 1
        if self.error:
            raise RuntimeError(self.error)
        return self.result

    def bind(self, **kwargs):
        return self

    def with_structured_output(self, schema):
        return self


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" :: {detail}" if detail else ""))
    if not condition:
        raise AssertionError(name)


def test_falls_back_after_rate_limit() -> None:
    first = FakeClient(error="rate limit exceeded")
    second = FakeClient(result="ok")
    llm = FallbackChatGroq([first, second], ["key1", "key2"])
    check("fallback returns second key result", llm.invoke("hello") == "ok")
    check("first key was tried", first.calls == 1)
    check("second key was tried", second.calls == 1)


def test_stops_on_non_fallback_error() -> None:
    first = FakeClient(error="prompt formatting failed")
    second = FakeClient(result="ok")
    llm = FallbackChatGroq([first, second], ["key1", "key2"])
    try:
        llm.invoke("hello")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")
    check("non-provider error does not try next key", second.calls == 0)


def main() -> None:
    test_falls_back_after_rate_limit()
    test_stops_on_non_fallback_error()
    print("\nALL OFFLINE LLM FALLBACK CHECKS PASSED")


if __name__ == "__main__":
    main()
