"""The generator: world -> documents (+ optional labeled flaws) -> Corpus."""
from __future__ import annotations

from dataclasses import dataclass, field

from .world import build_world
from .render import render_all
from .inject import apply_injects


@dataclass
class Corpus:
    docs: dict                       # {name: text}
    manifest: dict                   # {seed, world, flaws} -- manifest["world"] is a plain
                                      # World.summary() dict (display data, not a World instance);
                                      # pass the Corpus, manifest, or manifest["world"] directly to
                                      # check_consistency() to re-score safely (see README).


def generate(seed: int = 20260704, injects=None) -> Corpus:
    world = build_world(seed)
    docs = render_all(world)
    flaws = []
    if injects:
        docs, flaws = apply_injects(docs, world, injects)
    manifest = {"seed": seed, "world": world.summary(), "flaws": flaws}
    return Corpus(docs=docs, manifest=manifest)
