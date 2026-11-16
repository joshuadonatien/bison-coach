"""Delivery layer. ConsoleSender prints; TwilioSender sends real SMS when configured."""
import os
from typing import Protocol

from .models import Message


class Sender(Protocol):
    def send(self, msg: Message) -> None: ...


class ConsoleSender:
    def __init__(self) -> None:
        self.sent: list[Message] = []

    def send(self, msg: Message) -> None:
        self.sent.append(msg)
        print(f"[SMS to {msg.to}] {msg.body}")


class TwilioSender:
    def __init__(self) -> None:
        from twilio.rest import Client  # optional dependency

        self.client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        self.from_number = os.environ["TWILIO_FROM_NUMBER"]

    def send(self, msg: Message) -> None:
        self.client.messages.create(to=msg.to, from_=self.from_number, body=msg.body)


def default_sender() -> Sender:
    if all(os.getenv(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER")):
        return TwilioSender()
    return ConsoleSender()
