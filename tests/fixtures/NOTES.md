# Public fixture artifacts

Confirmed with HTTP HEAD / Wikimedia API on 2026-09-06. Do not invent replacements without fetching.

## Clean occupancy (Fixture A)

Same URL for move-in and move-out:

`https://upload.wikimedia.org/wikipedia/commons/1/15/Hotel_room.jpg`

Source: Wikimedia Commons `File:Hotel room.jpg` (HTTP 200, JPEG).

## Chargeable line (Fixture B)

Move-out:

`https://upload.wikimedia.org/wikipedia/commons/6/67/Broken_glass.jpg`

Source: Wikimedia Commons `File:Broken glass.jpg` (HTTP 200, JPEG).

Alternate:

`https://upload.wikimedia.org/wikipedia/commons/5/5d/Broken_window.jpg`

## Insufficient (Fixture C)

`https://upload.wikimedia.org/wikipedia/commons/does-not-exist-wearsettle-404.jpg`

Confirmed HTTP 404.

## Why screenshot-of-URL

Live GenLayer docs: `gl.nondet.web.render(url, mode='screenshot')` then pass the result as one of at most two `exec_prompt` images. Direct image URLs still render as a visual. Contact-sheet pages are the fork path for extra angles.
