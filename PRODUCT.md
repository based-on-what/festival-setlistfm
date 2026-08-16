# Product

## Register

product

## Users

Music fans planning a festival weekend or pre-gaming a concert. They arrive excited, usually in the evening, on a phone or laptop, with a list of artists in their head. The job: turn that lineup into a Spotify playlist of what those artists actually play live right now, in under two minutes. One-shot tool, no accounts, no learning curve.

## Product Purpose

Builds a private Spotify playlist from the most recent real setlists (setlist.fm) of up to 100 artists. Success: the user pastes their lineup, hits create, and gets a playlist that sounds like the festival will. The interface should feel like the event itself, not like a developer tool.

## Brand Personality

Loud, printed, anticipatory. Like holding the festival poster before the show. Three words: bold, tactile, electric. The lineup the user builds IS the festival bill; the UI treats it with poster-type reverence while the controls stay quiet and instrumental.

## Anti-references

- Neon-green-on-black "terminal hacker" aesthetic (the previous design; reads as AI-generated).
- Generic SaaS card stacks: three identical bordered cards in a column.
- Spotify clone: dark grey + green pills + rounded everything.
- Glassmorphism, gradient text, hero-metric blocks.

## Design Principles

1. The lineup is the hero. Artist names get festival-bill typography; everything else serves them.
2. Controls disappear into the task. Search, options, and buttons use quiet, standard affordances.
3. One committed color per theme, used like ink, not like glow.
4. Every state designed: loading (skeleton), empty (teaches), error (plain words), success (the payoff moment).
5. Print energy, screen discipline: poster type and rules, but product-grade motion (150-250ms, state-driven only).

## Accessibility & Inclusion

WCAG 2.1 AA. Full keyboard operation (combobox, reorder via tap-to-swap, focus-visible everywhere). `aria-live` announcements for lineup changes and build progress. `prefers-reduced-motion` honored. Contrast >= 4.5:1 for text in both themes.
