"""Minimal AstrBot doubles for running tests outside the host application."""

import importlib.util
import logging
import sys
from types import ModuleType


if importlib.util.find_spec("astrbot") is None:
    astrbot = ModuleType("astrbot")
    api = ModuleType("astrbot.api")
    star = ModuleType("astrbot.api.star")
    components = ModuleType("astrbot.api.message_components")
    all_api = ModuleType("astrbot.api.all")

    class Star:
        def __init__(self, context):
            self.context = context

    class Plain:
        def __init__(self, text):
            self.text = text

    api.AstrBotConfig = dict
    api.logger = logging.getLogger("astrbot-test")
    api.all = all_api
    star.Context = object
    star.Star = Star
    components.Plain = Plain
    all_api.MessageChain = list
    astrbot.api = api

    sys.modules.update({
        "astrbot": astrbot,
        "astrbot.api": api,
        "astrbot.api.star": star,
        "astrbot.api.message_components": components,
        "astrbot.api.all": all_api,
    })
